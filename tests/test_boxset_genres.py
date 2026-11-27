"""Coordinated, opt-in GENRE revisions without bypassing earlier LABEL safeguards."""
import array
import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from oscar import archive_metadata_scan as scan
from oscar import archive_revision_boxset as boxset
from oscar import archive_revision_boxset_apply as group
from oscar import archive_revision_boxset_verify as integrity
from oscar.api import app

from test_archive_revision_boxset import prepared, RELEASE, DISCS


def genre_lookup(existing):
    def lookup(release, disc_id, count):
        response = existing(release, disc_id, count)
        response["genres"] = ["Classical", "Baroque"]
        response["genre_source"] = "musicbrainz_release_group"
        return response
    return lookup


def test_explicit_genre_group_review_never_inherits_label_approval(prepared, monkeypatch):
    paths, originals, lookup = prepared
    provider = genre_lookup(lookup)
    for leaf in paths.values():
        proposals = scan.scan("additions", str(leaf), lookup=provider)["pending"]
        genre = next(p for p in proposals if p["field"] == "GENRE")
        scan.decide(genre["fingerprint"], "accept", lookup=provider)
    review = boxset.preview(RELEASE, lookup=provider, field="GENRE")
    assert review["field"] == "GENRE"
    assert review["reviewed_genres"] == ["Baroque", "Classical"]
    assert [x["genre_status"] for x in review["disc_reviews"]] == [
        "approved_for_review", "approved_for_review"
    ]
    assert review["apply_supported"] is False
    monkeypatch.setenv("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS", "1")
    assert boxset.preview(RELEASE, lookup=provider, field="GENRE")["apply_supported"]
    assert not boxset.preview(RELEASE, lookup=lookup)["apply_supported"]
    for n, leaf in paths.items():
        assert ((leaf / "01 - Track.flac").read_bytes(),
                (leaf / "manifest.json").read_bytes()) == originals[n]


def test_genre_integrity_diff_allowlist_rejects_unapproved_work_or_label(monkeypatch, tmp_path):
    original, revised = tmp_path / "old", tmp_path / "new"
    fields = {
        str(original): {"GENRE": [], "LABEL": ["Original Label"], "WORK": ["Some Work"]},
        str(revised): {"GENRE": ["Baroque", "Classical"],
                       "LABEL": ["Wrong Label"], "WORK": ["Different Work"]},
    }
    class FakeFlac:
        def __init__(self, path):
            self.tags = fields[str(path)]
    monkeypatch.setattr(integrity, "FLAC", FakeFlac)
    diff = integrity.compare_tags(original, revised, ["Classical", "Baroque"], field="GENRE")
    assert set(diff) == {"LABEL", "WORK"}
    fields[str(revised)]["LABEL"] = ["Original Label"]
    fields[str(revised)]["WORK"] = ["Some Work"]
    assert integrity.compare_tags(original, revised, ["Classical", "Baroque"], field="GENRE") == {}


def test_boxset_genre_api_auth_and_field_rejection(prepared, monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    payload = {"release_id": RELEASE, "field": "GENRE"}
    assert client.post("/api/collection/archive-revisions/boxset-preview", json=payload).status_code == 403
    assert client.post("/api/collection/archive-revisions/boxset-preview",
                       json={"release_id": RELEASE, "field": "UNSUPPORTED"},
                       headers={"X-OSCAR-RIP-TOKEN": "0123456789abcdef0123456789abcdef"}).status_code == 422
    html = client.get("/").text
    assert "Preview coordinated multidisc metadata update (read-only)" in html


def test_real_flac_boxset_genre_apply_preserves_evidence_audio_and_history(prepared, monkeypatch, tmp_path):
    from mutagen.flac import FLAC
    encoder = shutil.which("flac")
    if not encoder:
        pytest.skip("flac CLI not available")
    paths, originals, lookup = prepared
    provider = genre_lookup(lookup)
    wav = tmp_path / "input.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(array.array("h", [600, -600] * 4410).tobytes())
    hashes, original_evidence = {}, {}
    for disc, leaf in paths.items():
        audio = leaf / "01 - Track.flac"
        subprocess.run([encoder, "-f", "--silent", "-o", str(audio), str(wav)], check=True)
        tags = FLAC(str(audio))
        for key, value in {
            "MUSICBRAINZ_ALBUMID": RELEASE, "MUSICBRAINZ_DISCID": DISCS[disc],
            "MUSICBRAINZ_TRACKID": f"record-{disc}", "TITLE": "Track",
            "ARTIST": "Stravinsky; Pierre Boulez", "WORK": "Original Work",
            "LABEL": "Deutsche Grammophon",
        }.items():
            tags[key] = [value]
        tags.save()
        hashes[disc] = format(FLAC(str(audio)).info.md5_signature, "032x")
        evidence = leaf / "album.cue"
        evidence.write_text('FILE "01 - Track.flac" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')
        original_evidence[disc] = evidence.read_bytes()
        manifest_path = leaf / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][0]["sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
        manifest["files"][0]["streaminfo_audio_md5"] = hashes[disc]
        manifest["cue"] = {"filename": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
        manifest["source_evidence"] = []
        manifest["profile"] = "classical"
        manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(scan, "FLAC", FLAC)
    for leaf in paths.values():
        proposals = scan.scan("additions", str(leaf), lookup=provider)["pending"]
        genres = [p for p in proposals if p["field"] == "GENRE"]
        assert len(genres) == 1
        scan.decide(genres[0]["fingerprint"], "accept", lookup=provider)
    monkeypatch.setenv("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS", "1")
    preview = boxset.preview(RELEASE, lookup=provider, field="GENRE")
    assert preview["apply_supported"]
    done = group.apply(RELEASE, preview["fingerprint"],
                       "APPLY_COORDINATED_BOXSET_REVISION",
                       lookup=provider, field="GENRE")
    assert done["status"] == "completed" and done["discs"] == [4, 6]
    for disc, leaf in paths.items():
        tagged = FLAC(str(leaf / "01 - Track.flac"))
        assert sorted(tagged["GENRE"]) == ["Baroque", "Classical"]
        assert tagged["WORK"] == ["Original Work"]
        assert tagged["LABEL"] == ["Deutsche Grammophon"]
        assert format(tagged.info.md5_signature, "032x") == hashes[disc]
        assert (leaf / "album.cue").read_bytes() == original_evidence[disc]
    for history in done["originals_retained"]:
        assert "GENRE" not in FLAC(str(Path(history) / "01 - Track.flac"))
    with group._db() as db:
        rows = db.execute("SELECT genres,library_section FROM archive_items ORDER BY disc_number").fetchall()
        assert [x["genres"] for x in rows] == ["Classical; Baroque"] * 2
        assert [x["library_section"] for x in rows] == ["Classical"] * 2
    verification = integrity.verify(done["operation_id"])
    assert verification["status"] == "pass"
    assert len(verification["verified_discs"]) == 2
