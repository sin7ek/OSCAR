"""Staging-independent, read-only archive metadata scans with durable decisions.

Only published, fully hashed OSCAR archive leaves are eligible. Scan writes
proposals ONLY to /config/catalog.sqlite3, never to the archive, FLAC or CUE.
Accept is an approval for a future migration, not application to audio.
"""
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from mutagen.flac import FLAC

from oscar import collection_catalog as catalog, musicbrainz
from oscar.boxsets import lookup_release_medium, RELEASE_ID, DISC_ID

CLASSICAL_PROFILE_SOURCE = "archive-profile:classical"

_ID = re.compile(r"[a-f0-9]{64}\Z")
_MAX_ALBUMS = 20
_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata_proposals (
 fingerprint TEXT PRIMARY KEY,
 archive_path TEXT NOT NULL,
 publish_id TEXT NOT NULL,
 release_id TEXT NOT NULL,
 scope TEXT NOT NULL,
 track INTEGER NOT NULL,
 field TEXT NOT NULL,
 before_json TEXT NOT NULL,
 after_json TEXT NOT NULL,
 source_url TEXT NOT NULL DEFAULT '',
 archive_revision TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 first_seen TEXT NOT NULL,
 last_seen TEXT NOT NULL,
 decided_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_metadata_proposal_archive
 ON metadata_proposals(archive_path,status);
CREATE TABLE IF NOT EXISTS metadata_decision_events (
 id INTEGER PRIMARY KEY,
 fingerprint TEXT NOT NULL,
 decision TEXT NOT NULL,
 happened_at TEXT NOT NULL,
 archive_revision TEXT NOT NULL
);
"""


class ScanError(ValueError):
    pass


def _canonical(value):
    if isinstance(value, list):
        return sorted(set(str(v).strip() for v in value if str(v).strip()))
    return str(value or "").strip()


def _stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _archive_snapshot(archive_path):
    root = catalog.archive_root()
    album = Path(archive_path)
    if (not album.is_absolute() or not album.is_relative_to(root)
            or album == root or album.is_symlink() or not album.is_dir()):
        raise ScanError("Invalid published archive leaf")
    relative = album.relative_to(root)
    if len(relative.parts) not in (2, 3):
        raise ScanError("Unsupported archive path depth")
    curr = root
    for part in relative.parts:
        curr /= part
        if curr.is_symlink():
            raise ScanError("Unsafe archive path")
    manifest_path = album / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 3_000_000:
        raise ScanError("Missing or unsafe published manifest")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("status") != "published_verified":
        raise ScanError("Not a published OSCAR manifest")
    release = manifest.get("release_id")
    publish_id = manifest.get("publish_id")
    if (not isinstance(release, str) or not RELEASE_ID.fullmatch(release)
            or not isinstance(publish_id, str) or not re.fullmatch(r"[a-f0-9]{32}", publish_id)):
        raise ScanError("Published release and publication identity required")
    # Validate existing naming and release-short; do not rely on staging state.
    catalog._metadata_from_path(album, manifest)
    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 150:
        raise ScanError("Invalid archive track manifest")
    tracks = []
    seen = set()
    disc_ids = set()
    for item in files:
        if not isinstance(item, dict):
            raise ScanError("Malformed FLAC manifest entry")
        name, expected = item.get("filename"), item.get("sha256")
        if (not isinstance(name, str) or Path(name).name != name
                or name in seen or name in (".", "..")
                or not name.lower().endswith(".flac")
                or not isinstance(expected, str) or not _ID.fullmatch(expected)):
            raise ScanError("Unsafe or invalid FLAC manifest")
        seen.add(name)
        path = album / name
        if path.is_symlink() or not path.is_file() or _digest(path) != expected:
            raise ScanError("Archived FLAC is missing or SHA-256 differs from published manifest")
        actual = FLAC(str(path))
        if not isinstance(actual, FLAC):
            raise ScanError("Could not inspect FLAC")
        tags = {k.upper(): list(v) for k, v in actual.items()}
        release_ids = tags.get("MUSICBRAINZ_ALBUMID", [])
        if len(release_ids) != 1 or release_ids[0].lower() != release.lower():
            raise ScanError("Archived FLAC MusicBrainz release identity mismatch")
        disc = tags.get("MUSICBRAINZ_DISCID", [])
        if len(disc) != 1 or not DISC_ID.fullmatch(disc[0]):
            raise ScanError("Archived FLAC has no validated MusicBrainz Disc ID")
        disc_ids.add(disc[0])
        tracks.append({"tags": tags, "number": item.get("track")})
    if len(disc_ids) != 1 or [t["number"] for t in tracks] != list(range(1, len(tracks)+1)):
        raise ScanError("Archive has inconsistent Disc IDs or track ordering")
    return {
        "path": str(album), "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "publish_id": publish_id, "release_id": release,
        "disc_id": next(iter(disc_ids)), "tracks": tracks,
        "profile": manifest.get("profile"),
        "disc_number": manifest.get("disc_number", 1),
        "disc_total": manifest.get("disc_total", 1),
    }


def _existing_label_values(tags):
    """LABEL is canonical; RECORDLABEL is a legacy alias, not a new entity.

    A physical release may already carry an equivalent RECORDLABEL tag. Treat
    it as present rather than repeatedly proposing a missing LABEL. Distinct
    values in both tags are conflicting provenance and require manual review.
    """
    standard = _canonical(tags.get("LABEL", []))
    legacy = _canonical(tags.get("RECORDLABEL", []))
    if standard and legacy and standard != legacy:
        raise ScanError("Conflicting LABEL and RECORDLABEL FLAC tags; review before scanning")
    return standard or legacy


def _release_year(value):
    """Return the year of a valid full or partial MusicBrainz release date."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2}){0,2}", value):
        return ""
    try:
        date.fromisoformat(value + "-01" * (2 - value.count("-")))
    except ValueError:
        return ""
    return value[:4]


def _fresh_values(snapshot, lookup, *, allow_discogs=False):
    result = lookup(snapshot["release_id"], snapshot["disc_id"], len(snapshot["tracks"]))
    if result.get("release_id", "").lower() != snapshot["release_id"].lower():
        raise ScanError("Unexpected MusicBrainz release identity")
    media = [m for m in result.get("matched_media", [])
             if m.get("disc_id_attached") is True
             and m.get("track_count_matches") is True
             and m.get("position") == snapshot["disc_number"]
             and m.get("format") == "CD"]
    if len(media) != 1 or result.get("status") != "exact_disc_id_and_track_count":
        raise ScanError("MusicBrainz Disc ID/CD medium ambiguous; review physical release")
    tracks = media[0].get("tracks") or []
    if len(tracks) != len(snapshot["tracks"]):
        raise ScanError("MusicBrainz returned incomplete tracklist")
    labels = result.get("label_info") or []
    numbers = sorted(set(str(x.get("catalog_number")).strip()
                         for x in labels if isinstance(x, dict) and x.get("catalog_number")))
    label_names = sorted(set(str(x.get("name")).strip()
                             for x in labels if isinstance(x, dict) and x.get("name")))
    # Release-scope genres must be consistent across the archived CD before
    # proposing a change. Never silently overwrite conflicting per-track styles.
    genre_values = [_canonical(track["tags"].get("GENRE", [])) for track in snapshot["tracks"]]
    if any(values != genre_values[0] for values in genre_values[1:]):
        raise ScanError("Inconsistent GENRE tags across archived tracks; manual review required")
    provider_genres = result.get("genres") or []
    if provider_genres:
        from oscar.archive_genres import normalize_genres
        provider_genres = normalize_genres(provider_genres)
    genre_source_url = ""
    if allow_discogs and snapshot["disc_total"] == 1 and not genre_values[0] and not provider_genres:
        from oscar.genre_evidence import discogs_fallback
        provider_genres, genre_source_url = discogs_fallback(result)
    if (not provider_genres and not result.get("genre_lookup_incomplete")
            and snapshot.get("profile") == "classical"
            and genre_values[0] in ([], ["Classical"])):
        provider_genres = ["Classical"]
        genre_source_url = CLASSICAL_PROFILE_SOURCE
    candidates = [
        ("release", 0, "CATALOGNUMBER", snapshot["tracks"][0]["tags"].get("CATALOGNUMBER", []), numbers),
        ("release", 0, "LABEL", _existing_label_values(snapshot["tracks"][0]["tags"]), label_names),
        ("release", 0, "BARCODE", snapshot["tracks"][0]["tags"].get("BARCODE", []),
         [result["barcode"]] if result.get("barcode") else []),
        ("release", 0, "GENRE", genre_values[0], provider_genres),
    ]
    release_date, country = result.get("date"), result.get("country")
    for field, value in (
        ("DATE", release_date if _release_year(release_date) else None),
        ("RELEASECOUNTRY", country if isinstance(country, str) and re.fullmatch(r"[A-Z]{2}", country) else None),
    ):
        if value is None:
            continue
        existing = [_canonical(track["tags"].get(field, [])) for track in snapshot["tracks"]]
        if any(values != existing[0] for values in existing[1:]):
            raise ScanError(f"Inconsistent {field} tags across archived tracks; manual review required")
        candidates.append(("release", 0, field, existing[0], [value]))
    for index, (archived, external) in enumerate(zip(snapshot["tracks"], tracks), 1):
        if external.get("position") != index:
            raise ScanError("MusicBrainz track position mismatch")
        tags = archived["tags"]
        record = tags.get("MUSICBRAINZ_TRACKID", [])
        if len(record) != 1 or record[0] != external.get("recording_id"):
            raise ScanError("Recording identities changed; explicit edition review required")
        candidates.append(("track", index, "TITLE", tags.get("TITLE", []),
                           [external["title"]] if external.get("title") else []))
        candidates.append(("track", index, "ARTIST", tags.get("ARTIST", []),
                           [external["artist_credit"]] if external.get("artist_credit") else []))
    return candidates, genre_source_url


def _db():
    connection = catalog._connect()
    connection.executescript(_SCHEMA)
    if "source_url" not in {row[1] for row in connection.execute("PRAGMA table_info(metadata_proposals)")}:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if "source_url" not in {row[1] for row in connection.execute("PRAGMA table_info(metadata_proposals)")}:
                connection.execute("ALTER TABLE metadata_proposals ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")
    return connection


def _fingerprint(snapshot, scope, track, field, before, after, source_url):
    payload = [snapshot["publish_id"], snapshot["release_id"],
               snapshot["manifest_sha256"], scope, track, field, before, after, source_url or "musicbrainz"]
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _as_dict(row):
    d = dict(row)
    d["before"] = json.loads(d.pop("before_json"))
    d["after"] = json.loads(d.pop("after_json"))
    if d["source_url"] == CLASSICAL_PROFILE_SOURCE:
        d["source"] = "archive_profile"
    else:
        d["source"] = "discogs" if d["source_url"] else "musicbrainz"
    d["source_url"] = d["source_url"] or ("https://musicbrainz.org/release/" + d["release_id"])
    return d


def scan(mode, archive_path, *, lookup=None):
    """Scan one archive leaf. Decisions survive repeated scans and restarts."""
    if mode not in {"additions", "changes"}:
        raise ScanError("Select additions or changes")
    if not musicbrainz.lookup_enabled() and lookup is None:
        raise ScanError("MusicBrainz lookups are disabled")
    snapshot = _archive_snapshot(archive_path)
    values, genre_source_url = _fresh_values(snapshot, lookup or lookup_release_medium,
                                              allow_discogs=mode == "additions")
    now = datetime.now(timezone.utc).isoformat()
    observed = []
    with _db() as db:
        for scope, track, field, existing, incoming in values:
            before, after = _canonical(existing), _canonical(incoming)
            if not after or before == after:
                continue  # Never turn an absent/partial provider field into a deletion.
            kind = "additions" if not before else "changes"
            if mode != kind:
                continue
            source_url = genre_source_url if field == "GENRE" else ""
            fp = _fingerprint(snapshot, scope, track, field, before, after, source_url)
            before_json, after_json = _stable_json(before), _stable_json(after)
            db.execute("""INSERT OR IGNORE INTO metadata_proposals
                (fingerprint,archive_path,publish_id,release_id,scope,track,field,
                 before_json,after_json,source_url,archive_revision,first_seen,last_seen)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (fp, snapshot["path"], snapshot["publish_id"], snapshot["release_id"],
                 scope, track, field, before_json, after_json, source_url,
                 snapshot["manifest_sha256"], now, now))
            db.execute("UPDATE metadata_proposals SET last_seen=? WHERE fingerprint=?", (now, fp))
            observed.append(fp)
        rows = [_as_dict(db.execute("SELECT * FROM metadata_proposals WHERE fingerprint=?", (fp,)).fetchone())
                for fp in observed]
    return {
        "mode": mode, "archive_path": snapshot["path"],
        "publish_id": snapshot["publish_id"],
        "status": "scanned", "detected": len(rows),
        "pending": [x for x in rows if x["status"] == "pending"],
        "suppressed": sum(x["status"] != "pending" for x in rows),
        "note": ("No staging files required. Scanned archive verified against published hashes. "
                 "Only config database proposals changed; archive untouched."),
    }


def list_proposals(*, include_decided=False, limit=200):
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM metadata_proposals " +
            ("" if include_decided else "WHERE status='pending' ") +
            "ORDER BY first_seen DESC LIMIT ?", (min(500, max(1, limit)),)).fetchall()
    return {"items": [_as_dict(r) for r in rows], "count": len(rows)}


def _matches_proposal(candidate, row, genre_source_url):
    scope, track, field, before, after = candidate
    source_url = genre_source_url if field == "GENRE" else ""
    return (
        (scope, track, field) == (row["scope"], row["track"], row["field"])
        and source_url == row["source_url"]
        and _canonical(before) == json.loads(row["before_json"])
        and _canonical(after) == json.loads(row["after_json"])
    )


def decide(fingerprint, choice, *, lookup=None):
    if not _ID.fullmatch(fingerprint) or choice not in {"accept", "ignore"}:
        raise ScanError("Invalid metadata proposal decision")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM metadata_proposals WHERE fingerprint=?", (fingerprint,)).fetchone()
        if row is None or row["status"] != "pending":
            raise ScanError("Proposal not pending; refresh Collection")
        archived = _archive_snapshot(row["archive_path"])
        if (archived["manifest_sha256"] != row["archive_revision"]
                or archived["publish_id"] != row["publish_id"]):
            raise ScanError("Archive changed since proposal; rescan before deciding")
        # Ensure external value remains current before accepting/ignoring an old result.
        candidates, genre_source_url = _fresh_values(
            archived, lookup or lookup_release_medium, allow_discogs=bool(row["source_url"]))
        matches = [entry for entry in candidates if _matches_proposal(entry, row, genre_source_url)]
        if len(matches) != 1:
            raise ScanError("Provider value changed; rescan before deciding")
        now = datetime.now(timezone.utc).isoformat()
        status = "accepted" if choice == "accept" else "ignored"
        db.execute("UPDATE metadata_proposals SET status=?, decided_at=? WHERE fingerprint=?",
                   (status, now, fingerprint))
        db.execute("INSERT INTO metadata_decision_events (fingerprint,decision,happened_at,archive_revision) VALUES (?,?,?,?)",
                   (fingerprint, status, now, archived["manifest_sha256"]))
        return {"fingerprint": fingerprint, "status": status,
                "applied": False,
                "note": ("Decision recorded in persistent SQLite. Accept means approved "
                         "for a future separate archive migration; archive and FLACs untouched.")}



def reopen_decision(fingerprint, *, lookup=None):
    """Reopen an ignored/accepted proposal, preserving immutable decision history.

    A previous decision is NOT erased. The same archived revision and latest
    provider value must still support the proposal before it becomes pending.
    No archive or FLAC files are modified.
    """
    if not isinstance(fingerprint, str) or not _ID.fullmatch(fingerprint):
        raise ScanError("Invalid metadata proposal fingerprint")
    if not musicbrainz.lookup_enabled() and lookup is None:
        raise ScanError("MusicBrainz lookups are disabled")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM metadata_proposals WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if row is None or row["status"] not in {"ignored", "accepted"}:
            raise ScanError("Only an accepted or ignored proposal can be reopened")
        archived = _archive_snapshot(row["archive_path"])
        if (archived["manifest_sha256"] != row["archive_revision"]
                or archived["publish_id"] != row["publish_id"]
                or archived["release_id"] != row["release_id"]):
            raise ScanError("Published archive revision changed; rescan before reopening")
        candidates, genre_source_url = _fresh_values(
            archived, lookup or lookup_release_medium, allow_discogs=bool(row["source_url"]))
        matches = [entry for entry in candidates if _matches_proposal(entry, row, genre_source_url)]
        if len(matches) != 1:
            source = _as_dict(row)["source"]
            label = {"archive_profile": "Archive profile", "discogs": "Discogs",
                     "musicbrainz": "MusicBrainz"}[source]
            raise ScanError(f"{label} data changed; rescan instead of reopening stale proposal")
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE metadata_proposals SET status='pending', decided_at='' WHERE fingerprint=? AND status IN ('ignored','accepted')",
            (fingerprint,),
        )
        db.execute(
            "INSERT INTO metadata_decision_events "
            "(fingerprint,decision,happened_at,archive_revision) VALUES (?,?,?,?)",
            (fingerprint, "reopened", now, archived["manifest_sha256"]),
        )
    return {
        "fingerprint": fingerprint, "status": "pending", "applied": False,
        "note": "Decision reopened; previous Ignore/Accept remains in history. Archive unchanged.",
    }


def decision_history(limit=200):
    with _db() as db:
        rows = db.execute("""SELECT e.id,e.fingerprint,e.decision,e.happened_at,
                             p.archive_path,p.field,p.scope,p.track,
                             p.status AS current_status,
                             CASE WHEN e.id = (
                                 SELECT MAX(recent.id) FROM metadata_decision_events recent
                                 WHERE recent.fingerprint=e.fingerprint
                             ) THEN 1 ELSE 0 END AS latest_event
                             FROM metadata_decision_events e
                             JOIN metadata_proposals p ON p.fingerprint=e.fingerprint
                             ORDER BY e.id DESC LIMIT ?""", (min(500,max(1,limit)),)).fetchall()
    return {"events": [dict(x) for x in rows]}
