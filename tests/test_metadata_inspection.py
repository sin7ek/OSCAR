"""Read actual tagged FLAC comments; trusted UI remains opt-in and same-origin."""
import hashlib
import json
import shutil
import struct
import subprocess
import wave

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC

from oscar.api import app
from oscar import metadata_staging as metadata

JOB="f41806152a614b1a9006b10456b9bbd4"
COPY="3ac951bdd5b74ad8b484aaea955eb757"
RELEASE="4a8cbc25-21a0-4a24-8bb8-2f388164d544"
TOKEN="0123456789abcdef0123456789abcdef"


@pytest.fixture
def tagged(tmp_path,monkeypatch):
    if not shutil.which("flac"):
        pytest.skip("flac executable required")
    root=tmp_path/"staging";root.mkdir()
    source=root/("oscar-"+JOB);source.mkdir()
    copy=source/("metadata-copy-"+COPY);copy.mkdir()
    audio=copy/"audio";audio.mkdir()
    wav=tmp_path/"sample.wav"
    with wave.open(str(wav),"wb") as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(44100)
        out.writeframes(struct.pack("<2000h",*[0]*2000))
    flac=audio/"01 - Unknown track.flac"
    subprocess.run(["flac","--silent","-f","-o",str(flac),str(wav)],check=True)
    obj=FLAC(str(flac))
    obj["TITLE"]=["Air: Allegro"]
    obj["ALBUM"]=["Water Music"]
    obj["COMPOSER"]=["Georg Friedrich Händel"]
    obj["CONDUCTOR"]=["Jordi Savall"]
    obj.save()
    tags={"TITLE":"Air: Allegro","ALBUM":"Water Music",
          "COMPOSER":["Georg Friedrich Händel"],"CONDUCTOR":["Jordi Savall"]}
    md5=metadata._streaminfo_md5_hex(FLAC(str(flac)).info.md5_signature)
    (copy/"metadata-manifest.json").write_text(json.dumps({
        "job_id":JOB,"copy_id":COPY,"status":"tagged_copy_ready_for_review",
        "release_id":RELEASE,"preview_fingerprint":"f"*64,
        "files":{"audio/01 - Unknown track.flac":{
            "tagged_sha256":hashlib.sha256(flac.read_bytes()).hexdigest(),
            "audio_streaminfo_md5":md5
        }}
    }))
    (copy/"metadata-preview.json").write_text(json.dumps({
        "job_id":JOB,"release_id":RELEASE,"fingerprint":"f"*64,
        "album":{"title":"Water Music"},
        "tracks":[{"number":1,"original_file":"audio/01 - Unknown track.flac","tags":tags}]
    }))
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(root))
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN",TOKEN)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI",raising=False)
    return copy


def test_inspector_reads_actual_tags_and_hashes(tagged):
    result=metadata.inspect_copy(JOB,COPY)
    assert result["status"]=="tags_match_preview"
    track=result["tracks"][0]
    assert track["tags"]["COMPOSER"]==["Georg Friedrich Händel"]
    assert track["tags"]["CONDUCTOR"]==["Jordi Savall"]
    assert track["sha256_matches"]
    assert track["audio_streaminfo_md5_matches"]


def test_inspector_not_blind_to_real_tag_difference(tagged):
    f=tagged/"audio"/"01 - Unknown track.flac"
    obj=FLAC(str(f));obj["TITLE"]=["Not the original title"];obj.save()
    result=metadata.inspect_copy(JOB,COPY)
    assert result["status"]=="review_required"
    assert "TITLE" in result["tracks"][0]["differences"]
    assert not result["tracks"][0]["sha256_matches"]


def test_inspection_only_with_valid_auth(tagged):
    client=TestClient(app)
    url=f"/api/rip/jobs/{JOB}/metadata/copies/{COPY}/inspect"
    assert client.get(url).status_code==403
    r=client.get(url,headers={"X-OSCAR-RIP-TOKEN":TOKEN})
    assert r.status_code==200
    assert r.json()["status"]=="tags_match_preview"


def test_trusted_mode_is_explicit_and_guarded(tagged,monkeypatch):
    monkeypatch.setenv("OSCAR_TRUSTED_LOCAL_UI","1")
    client=TestClient(app,client=("192.168.1.30",12345))
    url=f"/api/rip/jobs/{JOB}/metadata/copies/{COPY}/inspect"
    assert client.get("/api/ui/access").json()["trusted_local_ui"]
    assert client.get(url).status_code==403
    headers={"X-OSCAR-UI-ACTION":"confirmed"}
    assert client.get(url,headers=headers).status_code==200
    assert client.get(url,headers={**headers,"Origin":"https://attacker.example"}).status_code==403
    assert client.get(url,headers={**headers,"Sec-Fetch-Site":"cross-site"}).status_code==403
    # State-changing actions must come from the exact same browser origin.
    from oscar.api import _rip_auth
    from fastapi import HTTPException
    class RequestMock:
        method="POST"
        client=type("Client",(),{"host":"192.168.1.30"})()
        headers={"host":"testserver","x-oscar-ui-action":"confirmed",
                 "origin":"http://testserver"}
    _rip_auth(None,RequestMock())
    RequestMock.headers={"host":"testserver","x-oscar-ui-action":"confirmed"}
    with pytest.raises(HTTPException,match="Same-origin"):
        _rip_auth(None,RequestMock())


def test_trusted_mode_off_still_needs_real_token(tagged):
    client=TestClient(app,client=("192.168.1.30",12345))
    url=f"/api/rip/jobs/{JOB}/metadata/copies/{COPY}/inspect"
    assert client.get(url,headers={"X-OSCAR-UI-ACTION":"confirmed"}).status_code==403
    assert not client.get("/api/ui/access").json()["trusted_local_ui"]


def test_inspector_visible_in_ui():
    html=TestClient(app).get("/").text
    assert "Inspect saved tags" in html
    assert "X-OSCAR-UI-ACTION" in html
