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

_COLUMNS = ("artist", "title", "year", "catalog_number", "musicbrainz_release_id",
            "archive_path", "track_count", "archive_status", "identification_status",
            "media_condition", "sleeve_condition", "folder", "notes")
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
  archive_status TEXT NOT NULL,
  identification_status TEXT NOT NULL DEFAULT 'HUMAN_REVIEWED',
  media_condition TEXT NOT NULL DEFAULT '',
  sleeve_condition TEXT NOT NULL DEFAULT '',
  folder TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  imported_at TEXT NOT NULL
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


def _metadata_from_path(album: Path, manifest: dict) -> dict:
    # Naming convention: /archive/artist/[catalog] album (year) [release-short]
    leaf = album.name
    artist = album.parent.name
    matched = re.fullmatch(r"\[([^\]]+)\] (.+) \((\d{4})\) \[([a-f0-9]{8})\]", leaf)
    if matched:
        catalog, title, year, release_short = matched.groups()
        if not manifest["release_id"].lower().startswith(release_short):
            raise CatalogError("Archive path release ID differs from manifest")
    else:
        catalog, title, year = "", leaf, ""
    if not artist or album == archive_root():
        raise CatalogError("Invalid archive folder structure")
    return {"artist": artist, "title": title, "year": year,
            "catalog_number": catalog, "musicbrainz_release_id": manifest["release_id"],
            "archive_path": str(album), "track_count": len(manifest["files"]),
            "archive_status": manifest["status"]}


def import_published() -> dict:
    """Explicit operator-triggered, insert-only import; never rewrite local edits."""
    root = archive_root()
    inserted = 0
    skipped = 0
    with _connect() as db:
        for manifest_file in sorted(root.rglob("manifest.json")):
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
                fields = _metadata_from_path(album, data)
            except (OSError, ValueError, json.JSONDecodeError, CatalogError):
                skipped += 1
                continue
            before = db.total_changes
            db.execute("""INSERT OR IGNORE INTO archive_items
              (archive_path, artist, title, year, catalog_number, musicbrainz_release_id,
               track_count, archive_status, imported_at)
              VALUES (:archive_path,:artist,:title,:year,:catalog_number,:musicbrainz_release_id,
                      :track_count,:archive_status,:imported_at)""",
                       {**fields, "imported_at": datetime.now(timezone.utc).isoformat()})
            inserted += db.total_changes - before
    return {"imported": inserted, "already_present_or_skipped": skipped,
            "note": "Only local database rows added; archives unchanged. No Discogs sync."}


def list_items(*, search: str = "", sort_by: str = "artist", descending: bool = False,
               limit: int = 250, offset: int = 0) -> dict:
    if sort_by not in _SORT or len(search) > 150 or not 1 <= limit <= 1000 or not 0 <= offset <= 1000000:
        raise CatalogError("Invalid catalog search or sort request")
    with _connect() as db:
        where = " WHERE artist LIKE ? OR title LIKE ? OR catalog_number LIKE ? " if search else ""
        args = (f"%{search}%",) * 3 if search else ()
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
