"""Per-track OSCAR catalog index, sourced only from immutable archived FLAC tags.

No inferred Works, performers, role identities, release IDs or version links.
Each row records the originating FLAC and archive manifest SHA-256.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

from oscar import collection_catalog as catalog

_TRACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_tracks (
  id INTEGER PRIMARY KEY,
  archive_path TEXT NOT NULL,
  track_number INTEGER NOT NULL,
  filename TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  recording_id TEXT NOT NULL DEFAULT '',
  release_track_id TEXT NOT NULL DEFAULT '',
  file_sha256 TEXT NOT NULL DEFAULT '',
  metadata_source TEXT NOT NULL DEFAULT 'archived_flac_vorbis',
  UNIQUE(archive_path, track_number)
);
CREATE TABLE IF NOT EXISTS track_credits (
  track_id INTEGER NOT NULL REFERENCES archive_tracks(id) ON DELETE CASCADE,
  credit_role TEXT NOT NULL,
  person_name TEXT NOT NULL,
  role_detail TEXT NOT NULL DEFAULT '',
  source_tag TEXT NOT NULL,
  UNIQUE(track_id, credit_role, person_name, role_detail, source_tag)
);
CREATE TABLE IF NOT EXISTS track_works (
  track_id INTEGER NOT NULL REFERENCES archive_tracks(id) ON DELETE CASCADE,
  work_title TEXT NOT NULL,
  musicbrainz_work_id TEXT NOT NULL DEFAULT '',
  relationship TEXT NOT NULL DEFAULT 'work',
  source_tag TEXT NOT NULL,
  UNIQUE(track_id, work_title, musicbrainz_work_id, relationship)
);
CREATE INDEX IF NOT EXISTS idx_track_release ON archive_tracks(archive_path);
CREATE INDEX IF NOT EXISTS idx_track_people ON track_credits(person_name, credit_role);
CREATE INDEX IF NOT EXISTS idx_track_work ON track_works(work_title);
"""


class TrackIndexError(RuntimeError):
    pass


def _single(tags, field):
    values = tags.get(field, [])
    return str(values[0])[:500] if values else ""


def _safe_tags(path: Path) -> dict[str, list[str]]:
    from mutagen.flac import FLAC
    file = FLAC(str(path))
    return {str(k).upper(): [str(value)[:500] for value in values[:100]]
            for k, values in file.items()}


def _credits(tags):
    people = set()
    for field, role in (("COMPOSER", "composer"), ("CONDUCTOR", "conductor"),
                        ("ORCHESTRA", "orchestra")):
        for value in tags.get(field, []):
            if value.strip():
                people.add((role, value.strip(), "", field))
    for full in tags.get("PERFORMER", []):
        match = re.fullmatch(r"(.+?) \(([^()]+)\)", full.strip())
        name, detail = (match.group(1).strip(), match.group(2).strip()) if match else (full.strip(), "")
        if name:
            people.add(("performer", name, detail, "PERFORMER"))
            # Only an explicit role of solo/soloist means soloist. A violin,
            # pianist, soprano or tenor credit alone is *not* proof of soloist.
            if re.search(r"\bsolo(?:ist)?\b", detail, re.I):
                people.add(("soloist", name, detail, "PERFORMER"))
    return sorted(people)


def _works(tags):
    records = set()
    for prefix, relation in (("", "work"), ("PARENT", "parent_work")):
        if relation == "work":
            names = tags.get("WORK", [])
            ids = tags.get("MUSICBRAINZ_WORKID", [])
            name_field = "WORK"
        else:
            names = tags.get("WORK_PARENT", [])
            ids = tags.get("MUSICBRAINZ_WORKPARENTID", [])
            name_field = "WORK_PARENT"
        # The only safe name-to-ID link is equal-length, aligned tag values.
        # Otherwise retain titles and IDs without asserting correspondence.
        aligned = len(names) == len(ids)
        for index, title in enumerate(names):
            if title.strip():
                records.add((title.strip(), ids[index] if aligned else "", relation, name_field))
        if not names:
            for value in ids:
                if value.strip():
                    records.add(("", value.strip(), relation, name_field))
    return sorted(records)


def index_published_tracks() -> dict:
    """Import all existing valid OSCAR published manifests (explicit opt-in).

    Per-album transactions replace only *derived* track rows from the current
    archived FLAC comments. No modifications to source album or user annotations.
    """
    import json

    root = catalog.archive_root()
    imported = 0
    skipped = 0
    with catalog._connect() as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(_TRACK_SCHEMA)
        for manifest_file in sorted(root.rglob("manifest.json")):
            album = manifest_file.parent
            relative = album.relative_to(root)
            if any(part.startswith(".oscar-unpublished-") or part in
                   {"ExtractionEvidence", "FailedAttempts", "Verification"} for part in relative.parts):
                continue
            if album.is_symlink() or manifest_file.is_symlink():
                continue
            try:
                manifest = catalog._read_manifest(album)
                if not manifest:
                    continue
                if not db.execute("SELECT 1 FROM archive_items WHERE archive_path=?",
                                  (str(album),)).fetchone():
                    skipped += 1
                    continue
                records = manifest["files"]
                if not isinstance(records, list) or not 1 <= len(records) <= 99:
                    raise TrackIndexError("Invalid manifest track list")
                rows = []
                for order, entry in enumerate(records, 1):
                    if not isinstance(entry, dict):
                        raise TrackIndexError("Malformed track entry")
                    number = entry.get("track")
                    filename = entry.get("filename")
                    if (number != order or not isinstance(filename, str)
                            or not re.fullmatch(r"[^/\\\x00-\x1f]+\.flac", filename, re.I)
                            or filename.startswith(".")):
                        raise TrackIndexError("Untrusted track number or filename")
                    audio = album / filename
                    if audio.is_symlink() or not audio.is_file():
                        raise TrackIndexError("Missing archived track")
                    expected = entry.get("sha256", "")
                    if expected and (not re.fullmatch(r"[a-f0-9]{64}", expected)
                                     or catalog._sha256(audio) != expected):
                        raise TrackIndexError("Archive track hash failed; do not index")
                    tags = _safe_tags(audio)
                    if (_single(tags, "MUSICBRAINZ_ALBUMID") and
                            _single(tags, "MUSICBRAINZ_ALBUMID").lower() != manifest["release_id"].lower()):
                        raise TrackIndexError("FLAC release ID conflicts with manifest")
                    tracknum = _single(tags, "TRACKNUMBER")
                    if tracknum and (not tracknum.isdecimal() or int(tracknum) != order):
                        raise TrackIndexError("FLAC track number conflicts with manifest")
                    rows.append((order, filename, expected, tags))
                # All files are checked before any replacement for this album.
                with db:
                    db.execute("""DELETE FROM track_credits WHERE track_id IN
                        (SELECT id FROM archive_tracks WHERE archive_path=?)""", (str(album),))
                    db.execute("""DELETE FROM track_works WHERE track_id IN
                        (SELECT id FROM archive_tracks WHERE archive_path=?)""", (str(album),))
                    db.execute("DELETE FROM archive_tracks WHERE archive_path=?", (str(album),))
                    for number, filename, sha, tags in rows:
                        cur = db.execute("""INSERT INTO archive_tracks
                            (archive_path,track_number,filename,title,recording_id,release_track_id,file_sha256)
                            VALUES (?,?,?,?,?,?,?)""", (str(album), number, filename,
                            _single(tags, "TITLE"), _single(tags, "MUSICBRAINZ_TRACKID"),
                            _single(tags, "MUSICBRAINZ_RELEASETRACKID"), sha))
                        tid = cur.lastrowid
                        db.executemany("""INSERT INTO track_credits
                            (track_id,credit_role,person_name,role_detail,source_tag)
                            VALUES (?,?,?,?,?)""", ((tid,*x) for x in _credits(tags)))
                        db.executemany("""INSERT INTO track_works
                            (track_id,work_title,musicbrainz_work_id,relationship,source_tag)
                            VALUES (?,?,?,?,?)""", ((tid,*x) for x in _works(tags)))
                imported += len(rows)
            except (TrackIndexError, OSError, ValueError, TypeError, json.JSONDecodeError):
                skipped += 1
    return {"tracks_indexed": imported, "albums_skipped": skipped,
            "source": "archived FLAC Vorbis comments; no missing metadata inferred",
            "archive_modified": False}


def find_tracks(*, search: str = "", role: str = "", limit: int = 150, offset: int = 0) -> dict:
    if not isinstance(search, str) or len(search) > 150 or not 1 <= limit <= 500 or offset < 0:
        raise TrackIndexError("Invalid track search")
    if role not in {"", "composer", "conductor", "orchestra", "performer", "soloist"}:
        raise TrackIndexError("Unknown contributor role")
    with catalog._connect() as db:
        db.executescript(_TRACK_SCHEMA)
        args = []
        conditions = []
        if search:
            pattern = "%" + search + "%"
            conditions.append("""(t.title LIKE ? OR t.recording_id LIKE ?
                OR EXISTS (SELECT 1 FROM track_credits c WHERE c.track_id=t.id AND c.person_name LIKE ?)
                OR EXISTS (SELECT 1 FROM track_works w WHERE w.track_id=t.id AND w.work_title LIKE ?)
                OR EXISTS (SELECT 1 FROM archive_items a WHERE a.archive_path=t.archive_path AND
                    (a.title LIKE ? OR a.artist LIKE ? OR a.label LIKE ?)))""")
            args.extend([pattern]*7)
        if role:
            conditions.append("EXISTS (SELECT 1 FROM track_credits c WHERE c.track_id=t.id AND c.credit_role=?)")
            args.append(role)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        total = db.execute("SELECT COUNT(*) FROM archive_tracks t" + where, args).fetchone()[0]
        rows = db.execute("""SELECT t.archive_path, t.track_number, t.filename, t.title,
            t.recording_id, t.release_track_id, a.artist, a.title AS album, a.label
            FROM archive_tracks t JOIN archive_items a ON a.archive_path=t.archive_path""" +
            where + " ORDER BY a.artist,t.archive_path,t.track_number LIMIT ? OFFSET ?",
            (*args,limit,offset)).fetchall()
        output = []
        for row in rows:
            row = dict(row)
            tid = db.execute("SELECT id FROM archive_tracks WHERE archive_path=? AND track_number=?",
                             (row["archive_path"], row["track_number"])).fetchone()[0]
            row["credits"] = [dict(x) for x in db.execute(
                "SELECT credit_role,person_name,role_detail,source_tag FROM track_credits WHERE track_id=? "
                "ORDER BY credit_role,person_name", (tid,))]
            row["works"] = [dict(x) for x in db.execute(
                "SELECT relationship,work_title,musicbrainz_work_id,source_tag FROM track_works "
                "WHERE track_id=? ORDER BY relationship,work_title", (tid,))]
            row["metadata_source"] = "archived_flac_vorbis"
            output.append(row)
    return {"total": total, "tracks": output, "limit": limit, "offset": offset}
