"""Offline tests for exact-release previews and lossless isolated FLAC tagging."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar import metadata_staging as metadata
from oscar.api import app

JOB = "f41806152a614b1a9006b10456b9bbd4"
RELEASE = "4a8cbc25-21a0-4a24-8bb8-2f388164d544"
DISC = "ROkQlooU5tDdgVZOkfXXTy.S4oU-"
TOKEN = "0123456789abcdef0123456789abcdef"


def medium_payload():
    return {
        "release_id": RELEASE, "release_title": "Water Music / Music for the Royal Fireworks",
        "album_artist": "Jordi Savall", "date": "1999",
        "country": "NL", "barcode": "00123456789",
        "label_info": [{"name": "Astrée Auvidis", "catalog_number": "ES 99220"}],
        "total_media": 1, "status": "exact_disc_id_and_track_count",
        "matched_media": [{
            "disc_id_attached": True, "track_count": 2, "position": 1,
            "tracks": [
                {"position": 1, "title": "Water Music, movement 1",
                 "artist_credit": "Jordi Savall", "recording_id": "rec-1",
                 "release_track_id": "track-1",
                 "composers": [{"name": "George Frideric Handel", "artist_id": "composer-1"}],
                 "performers": [{"name": "Jordi Savall", "role": "conductor"},
                                {"name": "Le Concert des Nations", "role": "performing orchestra"}],
                 "work_details": [{"id": "work-1", "title": "Allegro",
                                   "parents": [{"id": "parent-1", "title": "Water Music"}]}]},
                {"position": 2, "title": "Water Music, movement 2",
                 "artist_credit": "Jordi Savall", "recording_id": "rec-2",
                 "composers": [], "performers": [], "work_details": []},
            ]
        }]
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root=tmp_path/"stage";root.mkdir()
    directory=root/("oscar-"+JOB);directory.mkdir()
    audio=directory/"audio";audio.mkdir()
    hashes={}
    for number in (1,2):
        path=audio/f"{number:02d} - Unknown track.flac"
        path.write_bytes(b"fLaC" + str(number).encode())
        hashes["audio/"+path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/"state.json").write_text(json.dumps({"id":JOB,"status":"needs_verification",
        "returncode":0,"disc_id":DISC,"files_sha256":hashes}))
    (directory/"plan.json").write_text(json.dumps({"track_count":2,"disc_id":DISC}))
    (directory/"verification-report.json").write_text(json.dumps({
       "job_id":JOB,"status":"checks_passed","expected_tracks":2,
       "tracks":[{"checks_passed":True},{"checks_passed":True}]}))
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(root))
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN",TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ","1")
    return directory


def lookup(release, disc, count):
    assert (release,disc,count)==(RELEASE,DISC,2)
    return medium_payload()


def test_preview_exact_medium_and_classical_roles(setup):
    plan=metadata.preview(JOB,RELEASE,lookup=lookup)
    assert plan["requires_review"] and not plan["approved"]
    assert plan["album"]["catalog_numbers"] == ["ES 99220"]
    first=plan["tracks"][0]["tags"]
    assert first["TITLE"]=="Water Music, movement 1"
    assert first["MUSICBRAINZ_ALBUMID"]==RELEASE
    assert first["COMPOSER"]==["George Frideric Handel"]
    assert first["CONDUCTOR"]==["Jordi Savall"]
    assert first["ORCHESTRA"]==["Le Concert des Nations"]
    assert first["WORK"]==["Allegro"]
    assert first["GROUPING"]==["Water Music"]
    assert first["MUSICBRAINZ_TRACKID"]=="rec-1"
    assert first["MUSICBRAINZ_RELEASETRACKID"]=="track-1"
    assert len(plan["fingerprint"])==64
    assert not list(setup.glob("metadata-copy-*"))


def test_reject_ambiguous_release(setup):
    info=medium_payload()
    info["status"]="review_disc_id_or_count_ambiguity"
    with pytest.raises(metadata.MetadataError,match="exact Disc ID"):
        metadata.build_preview(info,JOB,DISC,2)


def test_reject_incomplete_tracklist(setup):
    info=medium_payload();info["matched_media"][0]["tracks"].pop()
    with pytest.raises(metadata.MetadataError,match="incomplete"):
        metadata.build_preview(info,JOB,DISC,2)


def test_reject_before_rip_verification(setup):
    report=setup/"verification-report.json"
    report.write_text(json.dumps({"job_id":JOB,"status":"review_required"}))
    with pytest.raises(metadata.MetadataError,match="checks must pass"):
        metadata.preview(JOB,RELEASE,lookup=lookup)


class FakeFLAC:
    """Injectable Mutagen stand-in; appends tags only to an isolated copy."""
    def __init__(self,path):
        self.path=Path(path)
        self.info=SimpleNamespace(md5_signature=bytes.fromhex("a1"*16))
        self.tags={}
    def clear(self):
        self.tags={}
    def __setitem__(self,key,val):
        self.tags[key]=val
    def save(self):
        with self.path.open("ab") as stream:
            stream.write(b"[tags-saved]")


def fake_runner(args,**kwargs):
    assert args[:3] == ["flac","-t","--silent"]
    return SimpleNamespace(returncode=0)


def test_tagging_creates_new_copy_without_touching_originals(setup):
    before={p.name:p.read_bytes() for p in (setup/"audio").iterdir()}
    preview=metadata.preview(JOB,RELEASE,lookup=lookup)
    output=metadata._tagged_copy(JOB,RELEASE,preview["fingerprint"],"a"*32,
                                 lookup=lookup,flac_factory=FakeFLAC,runner=fake_runner)
    assert output["status"]=="tagged_copy_ready_for_review"
    folder=setup/("metadata-copy-"+"a"*32)
    assert len(list((folder/"audio").glob("*.flac")))==2
    assert (folder/"metadata-preview.json").is_file()
    assert (folder/"metadata-manifest.json").is_file()
    assert before=={p.name:p.read_bytes() for p in (setup/"audio").iterdir()}
    assert all("[tags-saved]" in p.read_text() for p in (folder/"audio").glob("*.flac"))
    with pytest.raises(metadata.MetadataError,match="already exists"):
        metadata._tagged_copy(JOB,RELEASE,preview["fingerprint"],"a"*32,
                              lookup=lookup,flac_factory=FakeFLAC,runner=fake_runner)


def test_fingerprint_prevents_stale_release_data(setup):
    current=metadata.preview(JOB,RELEASE,lookup=lookup)
    def changed(*args):
        info=medium_payload()
        info["release_title"]="Other release title"
        return info
    with pytest.raises(metadata.MetadataError,match="preview changed"):
        metadata._tagged_copy(JOB,RELEASE,current["fingerprint"],"b"*32,
                              lookup=changed,flac_factory=FakeFLAC,runner=fake_runner)


def test_source_modified_after_rip_is_not_copied(setup):
    current=metadata.preview(JOB,RELEASE,lookup=lookup)
    (setup/"audio"/"01 - Unknown track.flac").write_bytes(b"modified")
    with pytest.raises(metadata.MetadataError,match="SHA-256 changed"):
        metadata._tagged_copy(JOB,RELEASE,current["fingerprint"],"c"*32,
                              lookup=lookup,flac_factory=FakeFLAC,runner=fake_runner)


def test_preview_api_requires_token(setup):
    client=TestClient(app)
    path=f"/api/rip/jobs/{JOB}/metadata/preview"
    assert client.post(path,json={"release_id":RELEASE}).status_code==403


def test_copy_api_requires_confirmation(setup):
    client=TestClient(app)
    path=f"/api/rip/jobs/{JOB}/metadata/copy"
    assert client.post(path,headers={"X-OSCAR-RIP-TOKEN":TOKEN},
       json={"release_id":RELEASE,"fingerprint":"f"*64,"confirmation":"NO"}).status_code==409


def test_browser_has_metadata_preview_and_copy_button(setup):
    html=TestClient(app).get("/").text
    assert "Preview MusicBrainz tags" in html
    assert "COPY_TAGGED_TO_STAGING" in html
