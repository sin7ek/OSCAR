"""Offline tests for consistency, original CUE preservation, CAA and parallel drive policy."""
import hashlib
import json
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest
from fastapi.testclient import TestClient
from mutagen.flac import FLAC
from oscar import archive_review, ripping
from oscar.api import app

JOB="f41806152a614b1a9006b10456b9bbd4"
COPY="3ac951bdd5b74ad8b484aaea955eb757"
RELEASE="4a8cbc25-21a0-4a24-8bb8-2f388164d544"
TOKEN="0123456789abcdef0123456789abcdef"


def sample_tracks():
    return [
        {"number":1,"title":"Air","artist":"Jordi Savall","recording_id":"r1","work_ids":["w1"],
         "work_names":["HWV 348: Air"],"length_seconds":173,
         "musicbrainz_length_ms":173000},
        {"number":2,"title":"Aria","artist":"Jordi Savall","recording_id":"r2","work_ids":["w1"],
         "work_names":["HWV 348: Air"],"length_seconds":222,
         "musicbrainz_length_ms":222000},
    ]


def test_same_work_different_tracks_is_review_not_invalid_audio():
    result=archive_review.consistency(sample_tracks())
    assert result["status"]=="review_recommended"
    assert len(result["flags"])==1
    assert result["flags"][0]["code"]=="same_work_different_titles"
    assert result["flags"][0]["recording_ids_differ"]
    assert result["flags"][0]["severity"]=="review"


def test_pop_album_without_works_is_not_flagged():
    tracks=sample_tracks()
    for track in tracks:
        track["work_ids"]=[]
    assert archive_review.consistency(tracks)["status"]=="no_detected_conflicts"


def test_duration_mismatch_and_missing_id_are_reported_without_guessing():
    tracks=sample_tracks()
    tracks[0]["musicbrainz_length_ms"]=100000
    tracks[0]["recording_id"]=""
    flags=archive_review.consistency(tracks)["flags"]
    assert any(x["code"]=="duration_mismatch" for x in flags)
    assert any(x["code"]=="missing_recording_id" for x in flags)
    tracks[0]["musicbrainz_length_ms"]=None
    assert not any(x["code"]=="duration_mismatch" for x in archive_review.consistency(tracks)["flags"])


def test_original_cue_indices_and_pregap_retained(tmp_path):
    original=tmp_path/"audio";original.mkdir()
    original_text='''REM DISCID "AB114D1C"
TITLE "Unknown disc (ROKQ)"
PERFORMER "Unknown Artist"
FILE "01 - Unknown track.flac" WAVE
  TRACK 01 AUDIO
    INDEX 01 00:00:00
    PREGAP 00:00:32
FILE "02 - Unknown track.flac" WAVE
  TRACK 02 AUDIO
    INDEX 01 00:00:00
'''
    (original/"original.cue").write_text(original_text)
    for number in (1,2):
        (original/f"{number:02d} - Unknown track.flac").touch()
    tracks=[
        {"number":1,"file":"audio/01 - Unknown track.flac","title":"Air","artist":"Jordi Savall"},
        {"number":2,"file":"audio/02 - Unknown track.flac","title":"Aria","artist":"Jordi Savall"}
    ]
    output=archive_review.cue_preview(tmp_path,tracks,"Water Music","Jordi Savall")
    assert output["status"]=="preview_requires_review"
    assert 'TITLE "Water Music"' in output["text"]
    assert 'TITLE "Air"' in output["text"]
    assert 'TITLE "Aria"' in output["text"]
    assert output["text"].count("INDEX 01 00:00:00")==2
    assert output["text"].count("PREGAP 00:00:32")==1
    assert 'FILE "01 - Air.flac" WAVE' in output["archive_cue_proposal"]
    assert 'FILE "02 - Aria.flac" WAVE' in output["archive_cue_proposal"]
    assert output["archive_cue_proposal"].count("PREGAP 00:00:32")==1
    assert output["archive_cue_requires_renaming"] is True
    assert (original/"original.cue").read_text()==original_text


def test_cue_does_not_synthesize_missing_disc_indices(tmp_path):
    audio=tmp_path/"audio";audio.mkdir()
    (audio/"original.cue").write_text(
        'FILE "01 - Other.flac" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')
    result=archive_review.cue_preview(tmp_path,[{"file":"audio/01 - Unknown track.flac",
                                                  "artist":"Artist","title":"Title"}],"A","B")
    assert result["status"]=="needs_review"
    assert "text" not in result


def test_cover_art_is_exact_release_candidate_only():
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"images":[{"front":true},{"front":false}]}'
    def opener(request,timeout):
        assert str(request.full_url).endswith(RELEASE)
        return Reply()
    result=archive_review.cover_preview(RELEASE,opener=opener)
    assert result["status"]=="candidate_found"
    assert result["thumbnail_url"].startswith("https://coverartarchive.org/release/"+RELEASE)
    assert result["needs_physical_cover_review"]


def test_missing_cover_falls_back_to_no_art():
    def opener(request,timeout):
        raise urllib.error.HTTPError(request.full_url,404,"missing",{},None)
    result=archive_review.cover_preview(RELEASE,opener=opener)
    assert result["status"]=="not_found"
    assert "thumbnail_url" not in result


@pytest.fixture
def staged(tmp_path,monkeypatch):
    if shutil.which("flac") is None:
        pytest.skip("FLAC utility required")
    root=tmp_path/"stage";root.mkdir()
    job=root/("oscar-"+JOB);job.mkdir()
    audio=job/"audio";audio.mkdir()
    copy=job/("metadata-copy-"+COPY);copy.mkdir()
    copied=copy/"audio";copied.mkdir()
    wave_path=tmp_path/"sample.wav"
    with wave.open(str(wave_path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100)
        w.writeframes(struct.pack("<3000h",*[0]*3000))
    files={}
    tracks=[]
    for n,title in ((1,"Air"),(2,"Aria")):
        p=copied/f"{n:02d} - Unknown track.flac"
        subprocess.run(["flac","--silent","-f","-o",str(p),str(wave_path)],check=True)
        obj=FLAC(str(p))
        obj["TITLE"]=[title];obj["ARTIST"]=["Jordi Savall"]
        obj["MUSICBRAINZ_TRACKID"]=["r"+str(n)]
        obj["MUSICBRAINZ_WORKID"]=["w1"]
        obj["WORK"]=["HWV 348: Air"]
        obj.save()
        files["audio/"+p.name]={"tagged_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
        tracks.append({"number":n,"original_file":"audio/"+p.name,
                       "tags":{"TITLE":title,"ARTIST":"Jordi Savall"},
                       "length_ms":None})
    (audio/"original.cue").write_text(
        'FILE "01 - Unknown track.flac" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
        'FILE "02 - Unknown track.flac" WAVE\n  TRACK 02 AUDIO\n    INDEX 01 00:00:00\n')
    (copy/"metadata-manifest.json").write_text(json.dumps({
        "job_id":JOB,"copy_id":COPY,"status":"tagged_copy_ready_for_review",
        "preview_fingerprint":"f"*64,"release_id":RELEASE,"files":files}))
    (copy/"metadata-preview.json").write_text(json.dumps({
        "job_id":JOB,"release_id":RELEASE,"fingerprint":"f"*64,
        "album":{"title":"Water Music","artist":"Jordi Savall","date":"1999",
                 "catalog_numbers":["ES 99220"]},"tracks":tracks}))
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(root))
    monkeypatch.setenv("OSCAR_RIP_TOKEN",TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI",raising=False)
    return job


def test_full_review_without_network_or_writes(staged):
    before=(staged/"audio"/"original.cue").read_bytes()
    report=archive_review.review(JOB,COPY,"original_tags",artwork=False)
    assert report["album"]["title"]=="Water Music"
    assert report["consistency"]["status"]=="review_recommended"
    assert report["cue"]["status"]=="preview_requires_review"
    assert report["publication_ready"] is False
    assert report["cover_art"]["status"]=="not_checked"
    assert (staged/"audio"/"original.cue").read_bytes()==before


def test_review_api_requires_trusted_ui_or_token(staged,monkeypatch):
    client=TestClient(app)
    url=f"/api/rip/jobs/{JOB}/archive-review/{COPY}?kind=original_tags"
    assert client.get(url).status_code==403
    monkeypatch.setattr(archive_review,"cover_preview",
       lambda *a,**kw: {"status":"not_found"})
    r=client.get(url,headers={"X-OSCAR-RIP-TOKEN":TOKEN})
    assert r.status_code==200,r.text
    assert r.json()["publication_ready"] is False


def test_drive_capacity_defaults_and_validation(monkeypatch):
    monkeypatch.delenv("OSCAR_MAX_CONCURRENT_RIPS",raising=False)
    assert ripping.max_concurrent_rips()==3
    monkeypatch.setenv("OSCAR_MAX_CONCURRENT_RIPS","7")
    assert ripping.max_concurrent_rips()==7
    monkeypatch.setenv("OSCAR_MAX_CONCURRENT_RIPS","17")
    with pytest.raises(ripping.RipError):
        ripping.max_concurrent_rips()


def test_archive_review_and_multidrive_panels_visible():
    html=TestClient(app).get("/").text
    assert "Review metadata, artwork" in html
    assert "Parallel optical drives" in html
    assert "oscar-mobile-cards" in html
