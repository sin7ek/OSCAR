"""Classical v2 separation of physical issue order and MB work hierarchy."""
import hashlib
import json
import shutil
import struct
import subprocess
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

from oscar import classical_v2 as v2
from oscar.api import app
from oscar.metadata_staging import _streaminfo_md5_hex

JOB = "f41806152a614b1a9006b10456b9bbd4"
COPY = "3ac951bdd5b74ad8b484aaea955eb757"
TOKEN = "0123456789abcdef0123456789abcdef"
RELEASE = "4a8cbc25-21a0-4a24-8bb8-2f388164d544"


@pytest.fixture
def source(tmp_path, monkeypatch):
    if shutil.which("flac") is None:
        pytest.skip("flac executable missing")
    stage = tmp_path / "stage"; stage.mkdir()
    job = stage / ("oscar-" + JOB); job.mkdir()
    original = job / ("metadata-copy-" + COPY); original.mkdir()
    audio = original / "audio"; audio.mkdir()
    wavefile = tmp_path / "sample.wav"
    with wave.open(str(wavefile), "wb") as handle:
        handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(44100)
        handle.writeframes(struct.pack("<3000h", *([0]*3000)))
    tracks, files = [], {}
    for n, title in [(1, "Water Music, Suite I: Menuet I"),
                     (2, "Water Music, Suite I: Menuet II"),
                     (3, "Music for the Royal Fireworks: Ouverture")]:
        path = audio / f"{n:02d} - Unknown track.flac"
        subprocess.run(["flac", "--silent", "-f", "-o", str(path), str(wavefile)], check=True)
        obj = FLAC(str(path))
        obj["TITLE"] = [title]
        obj["WORK"] = ["19. Minuet"]
        obj["MUSICBRAINZ_WORKID"] = ["work-id"]
        obj["GROUPING"] = ["Water Music Suite no. 3, HWV 350"]
        obj["COMPOSER"] = ["George Frideric Handel"]
        obj.save()
        tags = {"TITLE":title,"WORK":["19. Minuet"],
                "MUSICBRAINZ_WORKID":["work-id"],
                "GROUPING":["Water Music Suite no. 3, HWV 350"],
                "COMPOSER":["George Frideric Handel"]}
        tracks.append({"number":n,"original_file":"audio/"+path.name,"tags":tags,
            "composers":[{"artist_id":"not-a-valid-uuid","name":"George Frideric Handel"}],
            "performers":[],
            "works":[{"id":"work-id","title":"19. Minuet",
                      "parents":[{"id":"parent-work","title":"Water Music Suite no. 3, HWV 350"}]}]})
        files["audio/"+path.name] = {
            "tagged_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "audio_streaminfo_md5":_streaminfo_md5_hex(FLAC(str(path)).info.md5_signature)}
    (original/"metadata-preview.json").write_text(json.dumps({
        "job_id":JOB,"release_id":RELEASE,"fingerprint":"f"*64,
        "tracks":tracks}))
    (original/"metadata-manifest.json").write_text(json.dumps({
        "job_id":JOB,"copy_id":COPY,"status":"tagged_copy_ready_for_review",
        "preview_fingerprint":"f"*64,"release_id":RELEASE,"files":files}))
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(stage))
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN",TOKEN)
    monkeypatch.setenv("OSCAR_ALIAS_CACHE_PATH",str(tmp_path/"nonexistent.sqlite"))
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI",raising=False)
    return original


def sections():
    return [{"start":1,"end":2,"name":"Suite I on this physical CD"},
            {"start":3,"end":3,"name":"Royal Fireworks"}]


def test_no_guessing_work_and_movement(source):
    p=v2.create_preview(JOB,COPY,sections())
    assert p["track_count"]==3
    assert p["tracks"][0]["release_section"]=="Suite I on this physical CD"
    assert p["tracks"][0]["tags"]["RELEASE_SECTION"]=="Suite I on this physical CD"
    assert p["tracks"][0]["tags"]["WORK"]==["19. Minuet"]
    assert p["tracks"][0]["tags"]["WORK_PARENT"]==["Water Music Suite no. 3, HWV 350"]
    assert "GROUPING" not in p["tracks"][0]["tags"]
    assert "MOVEMENT" not in p["tracks"][0]["tags"]
    assert p["tracks"][0]["tags"]["TITLE"]=="Water Music, Suite I: Menuet I"
    assert p["tracks"][1]["work"]==["19. Minuet"]
    assert not any(source.parent.glob("metadata-v2-*"))


def test_explicit_movement_only(source):
    p=v2.create_preview(JOB,COPY,sections(),{"2":"II. Menuet II"})
    assert p["tracks"][1]["tags"]["MOVEMENT"]=="II. Menuet II"
    assert "MOVEMENT" not in p["tracks"][0]["tags"]


@pytest.mark.parametrize("invalid", [
    [{"start":1,"end":1,"name":"Suite I"}],
    [{"start":1,"end":2,"name":"Suite I"},{"start":2,"end":3,"name":"Overlaps"}],
    [{"start":0,"end":3,"name":"Invalid"}],
    [{"start":1,"end":3,"name":""}],
])
def test_invalid_section_review_rejected(source,invalid):
    with pytest.raises(v2.ClassicalError):
        v2.create_preview(JOB,COPY,invalid)


def test_explicit_en_alias_never_replaces_original(source,monkeypatch):
    def alias(kind,identifier):
        return "Handel" if kind=="artist" else "English work name"
    monkeypatch.setattr(v2,"_alias",alias)
    p=v2.create_preview(JOB,COPY,sections())
    assert p["tracks"][0]["tags"]["COMPOSER"]==["George Frideric Handel"]
    assert p["tracks"][0]["tags"]["COMPOSER_EN"]==["Handel"]
    assert p["tracks"][0]["tags"]["WORK_EN"]==["English work name"]


def test_tagged_v2_copy_real_flac_preserves_source(source):
    before={p.name:p.read_bytes() for p in (source/"audio").glob("*.flac")}
    p=v2.create_preview(JOB,COPY,sections(),{"1":"I. Minuet"})
    output=v2._do_copy(p,"a"*32)
    assert output["status"]=="classical_v2_ready_for_review"
    folder=source.parent/("metadata-v2-"+"a"*32)
    assert len(list((folder/"audio").glob("*.flac")))==3
    file=FLAC(str(folder/"audio"/"01 - Unknown track.flac"))
    assert file["release_section"]==["Suite I on this physical CD"]
    assert file["work_parent"]==["Water Music Suite no. 3, HWV 350"]
    assert file["movement"]==["I. Minuet"]
    assert "grouping" not in file
    assert before=={p.name:p.read_bytes() for p in (source/"audio").glob("*.flac")}


def test_wrong_fingerprint_and_confirmation(source):
    p=v2.create_preview(JOB,COPY,sections())
    with pytest.raises(v2.ClassicalError, match="confirmation"):
        v2.start_copy(p,"WRONG")
    p["tracks"][0]["tags"]["WORK"]=["tampered"]
    with pytest.raises(v2.ClassicalError, match="Tampered"):
        v2.start_copy(p,"COPY_CLASSICAL_V2_TO_STAGING")


def test_api_auth_and_html_controls(source):
    client=TestClient(app)
    url=f"/api/rip/jobs/{JOB}/metadata/copies/{COPY}/classical-v2/preview"
    assert client.post(url,json={"sections":sections()}).status_code==403
    response=client.post(url,json={"sections":sections()},
                         headers={"X-OSCAR-RIP-TOKEN":TOKEN})
    assert response.status_code==200,response.text
    assert response.json()["status"]=="requires_review"
    html=client.get("/").text
    assert "Preview classical v2 tags" in html
    assert "COPY_CLASSICAL_V2_TO_STAGING" in html


def test_v2_inspector_reads_back_actual_vorbis_comments(source):
    p = v2.create_preview(JOB, COPY, sections(), {"1": "Reviewed movement"})
    output = v2._do_copy(p, "b" * 32)
    assert output["status"] == "classical_v2_ready_for_review"
    result = v2.inspect_copy(JOB, "b" * 32)
    assert result["status"] == "tags_match_preview"
    assert result["track_count"] == 3
    assert result["tracks"][0]["release_section"] == "Suite I on this physical CD"
    assert result["tracks"][0]["movement"] == ["Reviewed movement"]
    assert all(x["sha256_matches"] and x["audio_md5_matches"] for x in result["tracks"])


def test_v2_inspector_detects_tampered_copy(source):
    p = v2.create_preview(JOB, COPY, sections())
    v2._do_copy(p, "c" * 32)
    changed = source.parent / ("metadata-v2-" + "c"*32) / "audio" / "01 - Unknown track.flac"
    obj = FLAC(str(changed))
    obj["RELEASE_SECTION"] = ["Incorrect suite"]
    obj.save()
    report = v2.inspect_copy(JOB, "c" * 32)
    assert report["status"] == "review_required"
    assert "RELEASE_SECTION" in report["tracks"][0]["differences"]
    assert not report["tracks"][0]["sha256_matches"]


def test_v2_inspector_api_requires_auth(source):
    client = TestClient(app)
    p = v2.create_preview(JOB, COPY, sections())
    v2._do_copy(p, "d"*32)
    url = f"/api/rip/jobs/{JOB}/metadata/classical-v2/copies/{'d'*32}/inspect"
    assert client.get(url).status_code == 403
    r = client.get(url, headers={"X-OSCAR-RIP-TOKEN": TOKEN})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "tags_match_preview"
