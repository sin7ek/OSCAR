"""Local OSCAR archive catalog: SQLite + ODS/CSV export, no Discogs writes.

Only imports OSCAR-generated published manifests on the configured archive root.
Source archives are opened read-only and never changed. Local operator data is
kept separate from provider metadata and credentials.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sqlite3
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

_COLUMNS = ("artist", "title", "year", "label", "catalog_number", "musicbrainz_release_id",
            "composer", "conductor", "orchestra", "soloists", "performers", "works",
            "archive_path", "track_count", "disc_number", "disc_total", "archive_status", "identification_status",
            "media_condition", "sleeve_condition", "folder", "notes", "label_provenance")
_ENRICHED = ("label", "composer", "conductor", "orchestra", "soloists", "performers", "works")
_SORT = frozenset(_COLUMNS)
_MAX_MANIFEST = 3_000_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_items (
  id INTEGER PRIMARY KEY,
  archive_path TEXT NOT NULL UNIQUE,
  artist TEXT NOT NULL,
  title TEXT NOT NULL,
  year TEXT NOT NULL DEFAULT '',
  catalog_number TEXT NOT NULL DEFAULT '',
  musicbrainz_release_id TEXT NOT NULL,
  track_count INTEGER NOT NULL,
  disc_number INTEGER NOT NULL DEFAULT 1,
  disc_total INTEGER NOT NULL DEFAULT 1,
  archive_status TEXT NOT NULL,
  identification_status TEXT NOT NULL DEFAULT 'HUMAN_REVIEWED',
  media_condition TEXT NOT NULL DEFAULT '',
  sleeve_condition TEXT NOT NULL DEFAULT '',
  folder TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  imported_at TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  composer TEXT NOT NULL DEFAULT '',
  conductor TEXT NOT NULL DEFAULT '',
  orchestra TEXT NOT NULL DEFAULT '',
  soloists TEXT NOT NULL DEFAULT '',
  performers TEXT NOT NULL DEFAULT '',
  works TEXT NOT NULL DEFAULT '',
  label_provenance TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_archive_artist ON archive_items(artist, title);
"""


class CatalogError(RuntimeError):
    pass


def database_path() -> Path:
    path = Path(os.environ.get("OSCAR_CATALOG_DB", "/config/catalog.sqlite3"))
    if not path.is_absolute() or path.name != "catalog.sqlite3" or path.is_symlink():
        raise CatalogError("Catalog database must be an absolute catalog.sqlite3 path")
    return path


def archive_root() -> Path:
    raw = os.environ.get("OSCAR_ARCHIVE_ROOT", "").strip()
    path = Path(raw)
    if not raw or not path.is_absolute() or path == Path("/") or path.is_symlink() or not path.is_dir():
        raise CatalogError("Configured OSCAR_ARCHIVE_ROOT is missing or unsafe")
    return path


def _connect() -> sqlite3.Connection:
    path = database_path()
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise CatalogError("Persistent database directory must exist and not be a symlink")
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    existing = {row[1] for row in db.execute("PRAGMA table_info(archive_items)")}
    for name in (*_ENRICHED, "label_provenance", "disc_number", "disc_total"):
        if name not in existing:
            if name in {"disc_number", "disc_total"}:
                db.execute(f"ALTER TABLE archive_items ADD COLUMN {name} INTEGER NOT NULL DEFAULT 1")
            else:
                db.execute(f"ALTER TABLE archive_items ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    return db


def _read_manifest(album: Path) -> dict | None:
    path = album / "manifest.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_MANIFEST:
        return None
    with path.open("r", encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict) or document.get("status") != "published_verified":
        return None
    if not isinstance(document.get("release_id"), str) or not re.fullmatch(
            r"[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}", document["release_id"]):
        return None
    if not isinstance(document.get("files"), list) or not document["files"]:
        return None
    return document


_ALBUM_DIR = re.compile(r"\\[([^\\]]+)\\] (.+) \\((\\d{4})\\) \\[([a-f0-9]{8})\\]")
_DISC_DIR = re.compile(r"Disc (0[1-9]|[1-9][0-9])")


def _metadata_from_path(album: Path, manifest: dict) -> dict:
    """Recognize only /artist/album[/Disc NN]; never guess from arbitrary depth."""
    relative = album.relative_to(archive_root())
    parts = relative.parts
    if len(parts) == 3 and _DISC_DIR.fullmatch(parts[-1]):
        artist, album_dir, _ = parts
        disc_number = int(_DISC_DIR.fullmatch(parts[-1]).group(1))
    elif len(parts) == 2:
        artist, album_dir = parts
        disc_number = 1
    else:
        raise CatalogError("Unsupported archive folder structure")
    matched = _ALBUM_DIR.fullmatch(album_dir)
    if not matched:
        raise CatalogError("Archive album folder does not match OSCAR naming convention")
    catalog, title, year, release_short = matched.groups()
    if not manifest["release_id"].lower().startswith(release_short):
        raise CatalogError("Archive path release ID differs from manifest")
    raw_disc = manifest.get("disc_number", disc_number)
    raw_total = manifest.get("disc_total", 1)
    if type(raw_disc) is not int or type(raw_total) is not int or not 1 <= raw_disc <= raw_total <= 99:
        raise CatalogError("Invalid archive disc metadata")
    if raw_disc != disc_number or (len(parts) == 3 and raw_total == 1):
        raise CatalogError("Archive folder disc number differs from manifest")
    if len(parts) == 2 and raw_total > 1 and raw_disc != 1:
        raise CatalogError("Missing multidisc directory")
    if not artist or not title:
        raise CatalogError("Invalid archive artist/album")
    return {"artist": artist, "title": title, "year": year,
            "catalog_number": catalog, "musicbrainz_release_id": manifest["release_id"],
            "archive_path": str(album), "track_count": len(manifest["files"]),
            "disc_number": disc_number, "disc_total": raw_total,
            "archive_status": manifest["status"]}


def _identification_status(manifest):
    """Edition provenance is distinct from integrity-checked publication."""
    accepted = {"INFERRED_OPERATOR_ACCEPTED", "INFERRED_NOT_PHYSICALLY_VERIFIED",
                "PHYSICAL_EDITION_VERIFIED", "EDITION_NOT_VERIFIED"}
    value = manifest.get("release_match_status")
    return value if value in accepted else "EDITION_NOT_VERIFIED"


def _legacy_bad_multidisc_row(row, album: Path) -> bool:
    """Repair only the exact old path-parser output, never edited values."""
    return (row["artist"] == album.parent.name
            and row["title"] == album.name
            and row["year"] == "" and row["catalog_number"] == ""
            and row["identification_status"] == "HUMAN_REVIEWED")



def _archive_tag_metadata(album: Path, manifest: dict) -> dict:
    """Read actual archived FLAC Vorbis comments; never infer absent artists."""
    from mutagen.flac import FLAC
    groups = {key: [] for key in (*_ENRICHED, "legacy_soloists")}
    seen = {key: set() for key in groups}
    # The publishing profile is an explicit reviewed metadata decision.
    # A GENRE=Classical tag is also explicit evidence, unlike a guessed
    # music style from title, artist or presence of vocal/instrument credits.
    classical = manifest.get("profile") == "classical"
    def add(key, value):
        v = str(value or "").strip()
        if v and v.casefold() not in seen[key] and len(groups[key]) < 120:
            seen[key].add(v.casefold())
            groups[key].append(v[:500])
    labels = manifest.get("label_info") or []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict):
                add("label", label.get("name"))
    for record in manifest.get("files") or []:
        if not isinstance(record, dict):
            continue
        name = record.get("filename")
        if not isinstance(name, str) or "/" in name or "\\" in name or not name.lower().endswith(".flac"):
            continue
        path = album / name
        if path.is_symlink() or not path.is_file():
            continue
        try:
            tags = FLAC(str(path))
        except (OSError, ValueError):
            continue
        if any(str(value).strip().casefold() in {"classical", "classical music"}
               for value in tags.get("GENRE", [])):
            classical = True
        for dest, tag in (("composer", "COMPOSER"), ("conductor", "CONDUCTOR"),
                          ("orchestra", "ORCHESTRA"), ("works", "WORK"),
                          ("performers", "PERFORMER"), ("label", "LABEL")):
            for value in tags.get(tag, []):
                add(dest, value)
        for value in tags.get("PERFORMER", []):
            # Reconstruct the historical (incorrectly broad) computed value,
            # so a re-import can safely clear the original Anastacia row.
            # Never overwrite a local value that differs from that signature.
            if re.search(r"\((?:solo|soloist|violin|cello|piano|soprano|tenor|mezzo-soprano|bass|baritone|flute|clarinet|harp|voice|vocal)\)", value, re.I):
                add("legacy_soloists", value)
            # A vocalist, violinist, pianist or soprano is *not* necessarily
            # a soloist. Require an explicit solo/soloist role declaration.
            role = re.search(r"\(([^()]*)\)\s*$", value)
            if role and re.search(r"\bsolo(?:ist)?\b", role.group(1), re.I):
                add("soloists", value)
    result = {key: "; ".join(groups[key]) for key in _ENRICHED}
    if not classical:
        result["soloists"] = ""
    result["legacy_soloists"] = "; ".join(groups["legacy_soloists"])
    return result


def import_published(*, only_path: Path | None = None) -> dict:
    """Idempotently import verified manifests and safely repair legacy multidisc rows.

    only_path allows the publisher to index exactly the newly promoted leaf.
    No external archive, FLAC or user-editable catalog field is overwritten.
    """
    root = archive_root()
    inserted = 0
    skipped = 0
    with _connect() as db:
        manifests = ([only_path / "manifest.json"] if only_path is not None
                     else sorted(root.rglob("manifest.json")))
        if only_path is not None and (only_path.is_symlink()
                or not only_path.is_relative_to(root) or
                not only_path.is_dir()):
            raise CatalogError("Unsafe specific archive import path")
        repaired = 0
        for manifest_file in manifests:
            album = manifest_file.parent
            relative = album.relative_to(root)
            if any(part in {"ExtractionEvidence", "Verification", "FailedAttempts"}
                   or part.startswith(".oscar-unpublished-") for part in relative.parts):
                continue
            if album.is_symlink() or manifest_file.is_symlink():
                continue
            try:
                data = _read_manifest(album)
                if data is None:
                    skipped += 1
                    continue
                fields = {**_metadata_from_path(album, data),
                          **_archive_tag_metadata(album, data)}
                fields["label_provenance"] = ("archive_manifest_label_info" if data.get("label_info") and fields["label"] else
                                               "archived_flac_label_tag" if fields["label"] else "")
                fields["identification_status"] = _identification_status(data)
            except (OSError, ValueError, json.JSONDecodeError, CatalogError):
                skipped += 1
                continue
            before = db.total_changes
            db.execute("""INSERT OR IGNORE INTO archive_items
              (archive_path, artist, title, year, catalog_number, musicbrainz_release_id,
               track_count, disc_number, disc_total, archive_status, imported_at, label, composer, conductor,
               orchestra, soloists, performers, works, label_provenance, identification_status,
               media_condition, sleeve_condition, folder, notes)
              VALUES (:archive_path,:artist,:title,:year,:catalog_number,:musicbrainz_release_id,
                      :track_count,:disc_number,:disc_total,:archive_status,:imported_at,:label,:composer,:conductor,
                      :orchestra,:soloists,:performers,:works,:label_provenance,:identification_status,'','','','')""",
                       {**fields, "imported_at": datetime.now(timezone.utc).isoformat()})
            inserted += db.total_changes - before
            # Older catalog rows can gain *missing* sourced metadata from
            # actual archive tags, but never overwrite operator-entered values.
            if db.total_changes == before:
                previous = db.execute(
                    "SELECT artist,title,year,catalog_number,identification_status "
                    "FROM archive_items WHERE archive_path=?", (fields["archive_path"],)
                ).fetchone()
                # The old importer misread /artist/album/Disc 06 as
                # artist=album-folder and title=Disc 06. Migrate exactly
                # that signature, leave all other curated fields alone.
                if (previous is not None and album.name.startswith("Disc ")
                        and _legacy_bad_multidisc_row(previous, album)):
                    db.execute("""UPDATE archive_items SET
                        artist=:artist,title=:title,year=:year,catalog_number=:catalog_number,
                        disc_number=:disc_number,disc_total=:disc_total,
                        identification_status=:identification_status
                        WHERE archive_path=:archive_path""", fields)
                    repaired += 1
                db.execute("""UPDATE archive_items SET
                   label=CASE WHEN label='' THEN :label ELSE label END,
                   label_provenance=CASE WHEN label_provenance='' THEN :label_provenance ELSE label_provenance END,
                   composer=CASE WHEN composer='' THEN :composer ELSE composer END,
                   conductor=CASE WHEN conductor='' THEN :conductor ELSE conductor END,
                   orchestra=CASE WHEN orchestra='' THEN :orchestra ELSE orchestra END,
                   soloists=CASE WHEN soloists='' OR soloists=:legacy_soloists
                                 THEN :soloists ELSE soloists END,
                   performers=CASE WHEN performers='' THEN :performers ELSE performers END,
                   works=CASE WHEN works='' THEN :works ELSE works END
                   WHERE archive_path=:archive_path""", fields)
    return {"imported": inserted, "repaired": repaired,
            "already_present_or_skipped": skipped,
            "note": "Local catalog only; source archives unchanged. No Discogs sync."}


def list_items(*, search: str = "", sort_by: str = "artist", descending: bool = False,
               limit: int = 250, offset: int = 0) -> dict:
    if sort_by not in _SORT or len(search) > 150 or not 1 <= limit <= 1000 or not 0 <= offset <= 1000000:
        raise CatalogError("Invalid catalog search or sort request")
    with _connect() as db:
        search_keys = ("artist", "title", "label", "catalog_number", "composer",
                       "conductor", "orchestra", "soloists", "performers", "works")
        where = " WHERE " + " OR ".join(k + " LIKE ?" for k in search_keys) if search else ""
        args = (f"%{search}%",) * len(search_keys) if search else ()
        total = db.execute("SELECT count(*) FROM archive_items" + where, args).fetchone()[0]
        order = "DESC" if descending else "ASC"
        rows = db.execute("SELECT " + ", ".join(_COLUMNS) + " FROM archive_items" +
                          where + f" ORDER BY {sort_by} {order}, archive_path ASC LIMIT ? OFFSET ?",
                          (*args, limit, offset)).fetchall()
    return {"total": total, "items": [dict(row) for row in rows],
            "sort_by": sort_by, "descending": descending, "limit": limit, "offset": offset}


def _safe_spreadsheet_text(value: object) -> str:
    text = str(value if value is not None else "")
    # Defend against formula execution in CSV and clients importing ODS as text.
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def export_csv() -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(_COLUMNS)
    for item in _all_rows():
        writer.writerow([_safe_spreadsheet_text(item[k]) for k in _COLUMNS])
    return output.getvalue().encode("utf-8-sig")


def _all_rows() -> list[dict]:
    with _connect() as db:
        return [dict(x) for x in db.execute(
            "SELECT " + ", ".join(_COLUMNS) + " FROM archive_items ORDER BY artist, title, archive_path")]


def _ods_cell(text: str) -> str:
    return '<table:table-cell office:value-type="string"><text:p>' + escape(text) + '</text:p></table:table-cell>'


def _ods_row(values) -> str:
    return "<table:table-row>" + "".join(_ods_cell(_safe_spreadsheet_text(v)) for v in values) + "</table:table-row>"


def export_ods() -> bytes:
    """Minimal conforming ODF 1.2 spreadsheet with a frozen export snapshot."""
    rows = _all_rows()
    timestamp = datetime.now(timezone.utc).isoformat()
    def table(name, data):
        return "<table:table table:name=" + quoteattr(name) + ">" + "".join(_ods_row(r) for r in data) + "</table:table>"
    collection = table("Collection", [_COLUMNS, *([item[k] for k in _COLUMNS] for item in rows)])
    metadata = table("Export Metadata", [
        ("Field", "Value"),
        ("Generated UTC", timestamp),
        ("Source", "OSCAR local collection database, not live Discogs"),
        ("Row count", str(len(rows))),
        ("Release verification", "Only OSCAR published manifest evidence; not independent AccurateRip/CTDB"),
    ])
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
           'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
           'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">'
           '<office:body><office:spreadsheet>' + collection + metadata +
           '</office:spreadsheet></office:body></office:document-content>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
                'manifest:version="1.2"><manifest:file-entry manifest:full-path="/" '
                'manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>')
    buf = io.BytesIO()
    with ZipFile(buf, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet", compress_type=ZIP_STORED)
        archive.writestr("content.xml", xml.encode("utf-8"), compress_type=ZIP_DEFLATED)
        archive.writestr("META-INF/manifest.xml", manifest.encode("utf-8"), compress_type=ZIP_DEFLATED)
    return buf.getvalue()

def export_xlsx() -> bytes:
    """Portable OOXML workbook with sortable AutoFilter and explicit text cells.

    No formulas, scripts or external references. Uses stdlib only and places
    external text in inlineStr cells to prevent spreadsheet injection.
    """
    from xml.sax.saxutils import quoteattr
    rows = _all_rows()
    sheet_rows = [_COLUMNS, *([item[k] for k in _COLUMNS] for item in rows)]
    def column(n):
        out = ""
        while n:
            n, digit = divmod(n - 1, 26)
            out = chr(65 + digit) + out
        return out
    def cell(value, row, col):
        address = f"{column(col)}{row}"
        safe = escape(_safe_spreadsheet_text(value))
        return f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{safe}</t></is></c>'
    sheet = "".join('<row r="' + str(i) + '">' +
                    "".join(cell(value, i, j) for j, value in enumerate(values, 1)) +
                    '</row>' for i, values in enumerate(sheet_rows, 1))
    last = f"{column(len(_COLUMNS))}{max(1,len(sheet_rows))}"
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
           'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
           '<sheetData>' + sheet + '</sheetData><autoFilter ref="A1:' + last + '"/>'
           '</worksheet>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Collection" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>')
    package_rels = ('<?xml version="1.0" encoding="UTF-8"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                    'Target="xl/workbook.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
             '</Types>')
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, payload in (
            ("[Content_Types].xml", types), ("_rels/.rels", package_rels),
            ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", rels),
            ("xl/worksheets/sheet1.xml", xml),
        ):
            archive.writestr(name, payload.encode("utf-8"))
    return output.getvalue()
