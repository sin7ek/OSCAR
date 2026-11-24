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
from oscar import archive_review, archive_publish, ripping, verification
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
    assert report["music_profile"]["name"]=="standard"
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


def test_classical_cue_uses_recording_performers_not_composer(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    original = (
        'PERFORMER "Stravinsky; Pierre Boulez"\n'
        'TITLE "Unknown disc"\n'
        'FILE "01 - Unknown track.flac" WAVE\n'
        '  TRACK 01 AUDIO\n'
        '    PERFORMER "Igor Stravinsky"\n'
        '    PREGAP 00:00:33\n'
        '    INDEX 01 00:00:00\n'
        'FILE "02 - Unknown track.flac" WAVE\n'
        '  TRACK 02 AUDIO\n'
        '    PERFORMER "Igor Stravinsky"\n'
        '    INDEX 01 00:00:00\n'
    )
    (audio / "disc.cue").write_text(original)
    tracks = [
        {"number": 1, "file": "audio/01 - Unknown track.flac",
         "title": "Tilim-bom", "artist": "Igor Stravinsky",
         "composer": [], "conductor": ["Pierre Boulez"],
         "documented_performers": ["Pierre Boulez (conductor)",
                                   "Ensemble intercontemporain (performer)",
                                   "Phyllis Bryn-Julson (vocal)"]},
        {"number": 2, "file": "audio/02 - Unknown track.flac",
         "title": "Wolf: Sacred Song", "artist": "Igor Stravinsky",
         "composer": ["Hugo Wolf"], "conductor": ["Pierre Boulez"],
         "documented_performers": ["Pierre Boulez (conductor)",
                                   "Ann Murray (vocal)"]},
    ]
    result = archive_review.cue_preview(tmp_path, tracks, "Boulez Conducts Stravinsky",
                                        "Stravinsky; Pierre Boulez")
    assert result["status"] == "preview_requires_review"
    assert 'PERFORMER "Pierre Boulez"' in result["text"]
    assert 'PERFORMER "Pierre Boulez; Ensemble intercontemporain; Phyllis Bryn-Julson"' in result["text"]
    assert 'PERFORMER "Pierre Boulez; Ann Murray"' in result["text"]
    assert 'PERFORMER "Igor Stravinsky"' not in result["text"]
    assert "PREGAP 00:00:33" in result["text"]
    assert "PREGAP 00:00:33" in result["archive_cue_proposal"]
    assert (audio / "disc.cue").read_text() == original


def test_classical_composer_without_performer_is_not_falsely_cue_credited(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    (audio / "disc.cue").write_text(
        'PERFORMER "Unknown Artist"\n'
        'FILE "01 - Unknown track.flac" WAVE\n'
        '  TRACK 01 AUDIO\n'
        '    INDEX 01 00:00:00\n')
    tracks = [{"number": 1, "file": "audio/01 - Unknown track.flac",
               "title": "A Work", "artist": "Hugo Wolf",
               "composer": ["Hugo Wolf"], "conductor": [],
               "documented_performers": []}]
    output = archive_review.cue_preview(tmp_path, tracks, "Classical", "Hugo Wolf")
    assert 'PERFORMER "Hugo Wolf"' not in output["text"]
    assert 'TITLE "A Work"' in output["text"]


def test_missing_classical_work_is_review_not_conflict():
    tracks = sample_tracks()
    tracks[1]["work_ids"] = []
    tracks[1]["work_names"] = []
    report = archive_review.consistency(tracks)
    assert report["status"] == "review_recommended"
    assert len(report["flags"]) == 1
    assert report["flags"][0]["code"] == "missing_classical_work_link"
    assert report["flags"][0]["tracks"] == [2]


def test_auto_profile_resolves_classical_v2_and_verified_conductors():
    classical = [{"conductor": ["Pierre Boulez"]}, {"conductor": ["Pierre Boulez"]},
                 {"conductor": ["Pierre Boulez"]}]
    assert archive_review.resolve_music_profile(classical, "classical_v2")["name"] == "classical"
    assert archive_review.resolve_music_profile(classical, "original_tags")["name"] == "classical"
    assert archive_review.resolve_music_profile([
        {"documented_performers": ["Eric Kupper (instrument)"]}],
        "original_tags")["name"] == "standard"
    assert archive_review.resolve_music_profile(classical, "original_tags",
                                                requested="standard")["source"] == "operator_review_override"


def test_anastacia_reprise_is_not_a_false_work_conflict():
    tracks = [
        {"number":3, "title":"Overdue Goodbye", "artist":"Anastacia",
         "recording_id":"recording-main", "work_ids":["same-work"],
         "length_seconds":274.36, "musicbrainz_length_ms":None},
        {"number":12, "title":"Overdue Goodbye (reprise)", "artist":"Anastacia",
         "recording_id":"recording-reprise", "work_ids":["same-work"],
         "length_seconds":95.16, "musicbrainz_length_ms":None},
    ]
    output = archive_review.consistency(tracks, profile="standard")
    assert output["status"] == "no_detected_conflicts"
    assert output["review_count"] == 0
    # On the classical policy, multiple distinct track titles sharing a work
    # are still flagged rather than silently conflated.
    assert archive_review.consistency(tracks, profile="classical")["review_count"] == 1


def test_pop_cue_shows_track_artist_not_every_session_musician(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    source = ('REM DISCID "9B0B170C"\n'
              'FILE "01 - Unknown track.flac" WAVE\n'
              '  TRACK 01 AUDIO\n'
              '    INDEX 01 00:00:00\n'
              'FILE "02 - Unknown track.flac" WAVE\n'
              '  TRACK 02 AUDIO\n'
              '    INDEX 01 00:00:00\n')
    (audio / "source.cue").write_text(source)
    tracks = [
        {"number": 1, "file":"audio/01 - Unknown track.flac",
         "title":"Freak of Nature", "artist":"Anastacia", "composer":[],
         "documented_performers":["Anastacia (vocal)","Eric Kupper (instrument)",
                                  "Billy Mann (performer)"]},
        {"number": 2, "file":"audio/02 - Unknown track.flac",
         "title":"Overdue Goodbye (reprise)", "artist":"Anastacia",
         "composer":[], "documented_performers":[]},
    ]
    output = archive_review.cue_preview(tmp_path, tracks, "Freak of Nature",
                                        "Anastacia", profile="standard")
    assert output["music_profile"] == "standard"
    assert output["text"].count('PERFORMER "Anastacia"') == 3
    assert "Eric Kupper" not in output["text"]
    assert "Billy Mann" not in output["text"]
    assert 'FILE "02 - Overdue Goodbye (reprise).flac" WAVE' in output["archive_cue_proposal"]
    assert (audio / "source.cue").read_text() == source


def test_invalid_music_profile_is_rejected():
    with pytest.raises(archive_review.ReviewError, match="profile"):
        archive_review.resolve_music_profile([], "original_tags", requested="guess-pop")
    with pytest.raises(archive_review.ReviewError, match="profile"):
        archive_review.consistency([], profile="guess-pop")


def test_processing_profile_selector_visible():
    html = TestClient(app).get("/").text
    assert 'id="review-profile"' in html
    assert "Automatic (recommended)" in html


@pytest.fixture
def publishable(staged, tmp_path, monkeypatch):
    """Give existing FLAC staging fixture the full publish manifest evidence."""
    original = staged / ("metadata-copy-" + COPY)
    manifest_path = original / "metadata-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    original_hashes = {}
    for rel, entry in manifest["files"].items():
        target = original / rel
        entry["tagged_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        entry["audio_streaminfo_md5"] = (
            archive_publish._streaminfo_md5_hex(FLAC(str(target)).info.md5_signature)
        )
        original_hashes[rel] = entry["tagged_sha256"]
    manifest_path.write_text(json.dumps(manifest))
    archive = tmp_path / "separate-archive"
    archive.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(archive))
    monkeypatch.setattr(verification, "report",
                        lambda job: {"status": "checks_passed", "job_id": job})
    return staged, original, archive, original_hashes


def test_safe_publisher_writes_verified_new_files_and_preserves_original(publishable):
    job, original, archive, before = publishable
    original_cue = (job / "audio" / "original.cue").read_bytes()
    plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    assert plan["tracks"][0]["filename"] == "01 - Air.flac"
    assert not plan["output_exists"]
    assert plan["profile"] == "standard"
    assert plan["include_cover"] is False
    published = archive_publish._do_publish(
        plan, "b" * 32, allow_metadata_observations=True)
    assert published["status"] == "published_verified"
    assert published["file_count"] == 2
    destination = archive / published["relative_directory"]
    assert (destination / "album.cue").is_file()
    assert (destination / "manifest.json").is_file()
    sources = (destination / "SOURCES.txt").read_text()
    assert "SOURCE_TYPE: PHYSICAL_CD_RIP" in sources
    assert "Disc 01 / Track 01 — 01 - Air.flac" in sources
    assert "Verification method not recorded" in sources
    assert "CTDB: not checked by OSCAR" in sources
    assert (destination / "ExtractionEvidence" / "audio" / "original.cue").read_bytes() == original_cue
    assert 'FILE "01 - Air.flac" WAVE' in (destination / "album.cue").read_text()
    assert 'FILE "02 - Aria.flac" WAVE' in (destination / "album.cue").read_text()
    assert (job / "audio" / "original.cue").read_bytes() == original_cue
    for rel, sha in before.items():
        assert hashlib.sha256((original / rel).read_bytes()).hexdigest() == sha
    evidence = json.loads((destination / "manifest.json").read_text())
    assert evidence["cue"]["original_indexes_preserved_as_reported"]
    assert evidence["source_evidence"][0]["sha256"] == hashlib.sha256(original_cue).hexdigest()
    assert evidence["source_preview_fingerprint"] == "f" * 64
    assert evidence["files"][0]["sha256"] == before["audio/01 - Unknown track.flac"]
    with pytest.raises(archive_publish.PublishError, match="exists"):
        archive_publish._do_publish(plan, "c" * 32,
                                    allow_metadata_observations=True)


@pytest.mark.parametrize("add_to_existing", [False, True])
def test_cd_extra_publishes_audio_cue_without_dangling_data_track(publishable, monkeypatch, add_to_existing):
    from oscar import cd_extra, go_controller
    job, _, archive, _ = publishable
    cue = job / "audio" / "original.cue"
    source = cue.read_text() + (
        'FILE "03 - Unknown track.bin" BINARY\n'
        '  TRACK 03 MODE1/2352\n    PREGAP 02:32:00\n    INDEX 01 00:00:00\n')
    cue.write_text(source)
    data = job / "audio" / "03 - Unknown track.bin"
    data.write_bytes(b"data session")
    layout = {"track": 3, "source": "audio/" + data.name, "format": "MODE1/2352",
              "start_lsn": 11402, "sectors": 1, "size": 2352, "disc_toc": "0:1:-11402:11403"}
    monkeypatch.setattr(cd_extra, "geometry", lambda root: layout)
    unavailable = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    assert unavailable["provenance"]["cd_extra_data"]["status"] == "unavailable"
    with pytest.raises(archive_publish.PublishError, match="CD-Extra data unavailable"):
        archive_publish._do_publish(unavailable, "d" * 32, allow_metadata_observations=True)
    excluded = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard", include_data=False)
    assert excluded["provenance"]["cd_extra_data"]["status"] == "excluded_by_operator"
    assert excluded["fingerprint"] != unavailable["fingerprint"]
    if add_to_existing:
        (job / "audio" / "cyanrip.log").write_text(
            "Track 3 is data:\n"
            "  Data bytes: 2352\n  Frames: 1\n  Pregap LSN: 2\n"
            "  Start LSN: 11402\n  End LSN: 11402\n")
        excluded = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard", include_data=False)
        existing = archive_publish._do_publish(excluded, "b" * 32, allow_metadata_observations=True)
        destination = archive / existing["relative_directory"]
        originals = {path: path.read_bytes() for path in destination.iterdir() if path.is_file()}
    payload = b"X" * 2352
    data.write_bytes(payload)
    state_file = job / "state.json"
    state = {}
    state["cd_extra_data"] = {**layout, "sha256": hashlib.sha256(payload).hexdigest(),
                              "verification": "two_matching_raw_reads"}
    state_file.write_text(json.dumps(state))
    plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    assert plan["provenance"]["cd_extra_data"]["status"] == "included"
    assert bool(plan.get("data_supplement")) == add_to_existing, plan.get("destination_block_reason")
    data.write_bytes(b"Y" * 2352)
    with pytest.raises(archive_publish.PublishError, match="preview changed"):
        archive_publish._do_publish(plan, "e" * 32, allow_metadata_observations=True)
    data.write_bytes(payload)
    assert plan["provenance"]["excluded_data_track"] == 3
    assert "BINARY" not in plan["cue"]
    assert plan["cue"].count("INDEX 01") == 2
    published = archive_publish._do_publish(plan, "c" * 32, allow_metadata_observations=True)
    destination = archive / published["relative_directory"]
    assert (destination / "ExtractionEvidence" / "audio" / "original.cue").read_text() == source
    assert (destination / "album.cue").read_text() == plan["cue"]
    if add_to_existing:
        assert published["data_supplement"]
        assert all(path.read_bytes() == content for path, content in originals.items())
        assert "SHA-256:" in (destination / "CD-Extra/SOURCES.txt").read_text()
        assert go_controller._read_published_archive(JOB, {
            "archive_relative_directory": published["relative_directory"],
            "archive_publish_id": published["publish_id"], "metadata_copy_id": COPY,
            "archive_release_id": plan["release_id"], "archive_fingerprint": plan["fingerprint"],
        })
        retry = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
        assert "already contains" in retry["destination_block_reason"]
    else:
        assert "CD-Extra data track 3: included" in (destination / "SOURCES.txt").read_text()
    assert data.read_bytes() == payload
    assert (destination / cd_extra.ARCHIVE_FILENAME).read_bytes() == payload
    manifest = json.loads((destination / "manifest.json").read_text())
    cd_extra.check_archive(destination, manifest)
    exported = archive.parent / "payload.iso"
    cd_extra.extract_payload(destination, exported)
    assert exported.read_bytes() == payload[16:2064]
    (destination / cd_extra.ARCHIVE_FILENAME).write_bytes(b"corrupt")
    with pytest.raises(cd_extra.DataError, match="integrity"):
        cd_extra.check_archive(destination, manifest)


@pytest.fixture
def recovered_disc(publishable, monkeypatch):
    job, copy, archive, _ = publishable
    original_id, diagnostic_id = "1" * 32, "2" * 32
    disc_id = "1FGELhYaLaSf9MIPUxtlZGDbQU8-"
    preview_path = copy / "metadata-preview.json"
    preview = json.loads(preview_path.read_text())
    preview["album"]["musicbrainz_disc_id"] = disc_id
    preview["album"]["title"] = "The Symphonies"
    manifest_path = copy / "metadata-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    template = (copy / "audio/01 - Unknown track.flac").read_bytes()
    preview["tracks"] = []
    manifest["files"] = {}
    hashes, sources, verified, cue = {}, [], [], []
    for n in range(1, 18):
        relative = f"audio/{n:02d} - Unknown track.flac"
        path = copy / relative
        path.write_bytes(template)
        tagged = FLAC(str(path))
        tagged["TITLE"] = [f"Movement {n}"]
        tagged.save()
        source_hash = hashlib.sha256(f"raw rip track {n}".encode()).hexdigest()
        manifest["files"][relative] = {
            "source_sha256": source_hash,
            "tagged_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "audio_streaminfo_md5": archive_publish._streaminfo_md5_hex(tagged.info.md5_signature),
        }
        preview["tracks"].append({"number": n, "original_file": relative,
                                  "tags": {"DISCNUMBER": "11", "DISCTOTAL": "11"}})
        cue.append(f'FILE "{path.name}" WAVE\n  TRACK {n:02d} AUDIO\n    INDEX 01 00:00:00\n')
        source_job = diagnostic_id if n == 7 else original_id
        hashes[relative] = source_hash
        sources.append({"track": n, "source_job_id": source_job, "source_path": relative,
                        "source_sha256": source_hash, "recovered_sha256": source_hash})
        verified.append({"number": n, "file": relative, "source_job_id": source_job,
                         "checks_passed": True, "accuraterip": {
                             "v1": {"status": "accurately_ripped", "confidence": 30},
                             "v2": {"status": "accurately_ripped", "confidence": 28},
                         }})
    preview_path.write_text(json.dumps(preview))
    manifest_path.write_text(json.dumps(manifest))
    (job / "audio/original.cue").write_text("".join(cue))
    parents = {"original_job_id": original_id, "diagnostic_job_id": diagnostic_id}
    report = {"job_id": JOB, "status": "checks_passed", "accuraterip_coverage": "both_versions",
              "verification_method": "independent_trackverify_R_v1_v2",
              "tracks": verified, "recovery_sources": parents}
    (job / "verification-report.json").write_text(json.dumps(report))
    (job / "recovery-sources.json").write_text(json.dumps({
        **parents, "format": "OSCAR_TRACK_RECOVERY_V1", "disc_id": disc_id,
        "track_count": len(sources), "tracks": sources,
    }))
    (job / "state.json").write_text(json.dumps({
        "id": JOB, "disc_id": disc_id, "status": "needs_verification",
        "returncode": 0, "files_sha256": hashes,
    }))
    (job / "trackverify-console.log").write_text("saved independent verifier transcript")
    monkeypatch.setattr(verification, "report", lambda _: report)
    return job, archive


def test_recovered_disc_11_sources_preview_matches_publication(recovered_disc):
    job, archive = recovered_disc
    plan = archive_publish.prepare(JOB, COPY, profile="standard")
    plan["_release_match_status"] = "INFERRED_OPERATOR_ACCEPTED"
    preview = archive_publish.render_sources(plan, plan["_release_match_status"])
    published = archive_publish._do_publish(plan, "c" * 32, allow_metadata_observations=True)
    destination = archive / published["relative_directory"]
    assert destination.name == "Disc 11"
    assert (destination / "SOURCES.txt").read_text() == preview
    assert "SOURCE_TYPE: HYBRID_REPAIRED_CD_RIP" in preview
    assert "Medium: Disc 11 of 11" in preview
    assert "Independent trackverify -R (AccurateRip v1 and v2, offset 0)" in preview
    assert preview.count("Audio source: original full-disc rip") == 16
    assert preview.count("Audio source: diagnostic replacement") == 1
    track7 = preview.split("Disc 11 / Track 07")[1].split("Disc 11 / Track 08")[0]
    assert "Audio source: diagnostic replacement" in track7
    assert f"Source job: {'2' * 32}" in track7
    assert "Source file: audio/07 - Unknown track.flac" in track7
    assert hashlib.sha256(b"raw rip track 7").hexdigest() in track7
    assert "AccurateRip v1: accurately ripped (confidence 30)" in track7
    assert "AccurateRip v2: accurately ripped (confidence 28)" in track7
    for name in ("verification-report.json", "recovery-sources.json", "trackverify-console.log"):
        assert (destination / "ExtractionEvidence" / name).read_bytes() == (job / name).read_bytes()
    from oscar.archive_audit import audit_release
    audit = audit_release(destination)
    assert audit["source_type"] == "HYBRID_REPAIRED_CD_RIP"
    assert not audit["errors"]


def test_recovery_with_misattributed_track_cannot_be_published(recovered_disc):
    job, archive = recovered_disc
    evidence = job / "recovery-sources.json"
    recovery = json.loads(evidence.read_text())
    recovery["tracks"][5]["source_job_id"] = recovery["diagnostic_job_id"]
    evidence.write_text(json.dumps(recovery))
    with pytest.raises(archive_publish.PublishError, match="Inconsistent track recovery evidence"):
        archive_publish.prepare(JOB, COPY, profile="standard")
    assert not list(archive.iterdir())


def test_publish_without_review_confirmation_rejected(publishable):
    plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    with pytest.raises(archive_publish.PublishError, match="confirmation"):
        archive_publish.start(JOB, COPY, "original_tags", "standard",
                              plan["fingerprint"], "NO")
    with pytest.raises(archive_publish.PublishError, match="cover"):
        archive_publish.start(JOB, COPY, "original_tags", "standard",
                              plan["fingerprint"], "PUBLISH_REVIEWED_ARCHIVE",
                              include_cover=True)
    with pytest.raises(archive_publish.PublishError, match="preview changed"):
        archive_publish.start(JOB, COPY, "original_tags", "standard",
                              "0" * 64, "PUBLISH_REVIEWED_ARCHIVE")


def test_publish_blocked_if_tagged_copy_has_changed(publishable):
    _, copy, _, _ = publishable
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "standard")
    source = copy / "audio" / "01 - Unknown track.flac"
    obj = FLAC(str(source))
    obj["COMMENT"] = ["changed unexpectedly"]
    obj.save()
    with pytest.raises(archive_publish.PublishError, match="hash changed"):
        archive_publish._do_publish(plan, "d" * 32, allow_metadata_observations=True)


def test_publication_api_requires_independent_opt_in(publishable, monkeypatch):
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.delenv("OSCAR_ENABLE_ARCHIVE_PUBLISH", raising=False)
    response = TestClient(app).post(
        f"/api/rip/jobs/{JOB}/archive-publish/preview",
        headers={"X-OSCAR-RIP-TOKEN": TOKEN},
        json={"copy_id": COPY, "kind": "original_tags", "profile": "standard"})
    assert response.status_code == 403
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_PUBLISH", "1")
    response = TestClient(app).post(
        f"/api/rip/jobs/{JOB}/archive-publish/preview",
        headers={"X-OSCAR-RIP-TOKEN": TOKEN},
        json={"copy_id": COPY, "kind": "original_tags", "profile": "standard"})
    assert response.status_code == 200, response.text
    assert response.json()["tracks"][0]["filename"] == "01 - Air.flac"


def test_archive_publisher_ui_present():
    html = TestClient(app).get("/").text
    assert "Publish verified FLAC archive (explicit opt-in)" in html
    assert 'id="publish-preview"' in html
    assert 'id="publish-start"' in html
    assert 'id="publish-physical"' in html
    assert "[hidden]{display:none!important}" in html
    assert 'id="publish-observation-label" hidden' in html
    assert 'id="publish-cover-label" hidden' in html
    assert "Preview not started: OSCAR rip token was not supplied" in html
    assert "Preparing archive preview authorization" in html
    assert "Archive preview authorization unavailable" in html


def test_publish_requires_explicit_acknowledgement_of_classical_work_gaps(publishable, monkeypatch):
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "classical")
    # This two-track fixture uses one shared work with different titles.
    assert plan["metadata_observations"]
    with pytest.raises(archive_publish.PublishError, match="acknowledgement"):
        archive_publish.start(JOB, COPY, "original_tags", "classical",
                              plan["fingerprint"], "PUBLISH_REVIEWED_ARCHIVE")
    with pytest.raises(archive_publish.PublishError, match="acknowledgement"):
        archive_publish._do_publish(plan, "e" * 32,
                                    allow_metadata_observations=False)


def test_archive_root_refuses_staging_or_symlink(publishable, monkeypatch, tmp_path):
    stage, _, archive, _ = publishable
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(stage))
    with pytest.raises(archive_publish.PublishError, match="separate"):
        archive_publish.archive_root()
    symlink = tmp_path / "redirect"
    symlink.symlink_to(archive, target_is_directory=True)
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(symlink))
    with pytest.raises(archive_publish.PublishError, match="real"):
        archive_publish.archive_root()


def test_archive_path_refuses_symlinked_artist_parent(publishable):
    _, _, archive, _ = publishable
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "standard")
    artist = archive / Path(plan["relative_directory"]).parts[0]
    artist.symlink_to(archive.parent, target_is_directory=True)
    with pytest.raises(archive_publish.PublishError, match="Symlink"):
        archive_publish._do_publish(plan, "f" * 32,
                                    allow_metadata_observations=True)


def test_rendered_web_page_preserves_javascript_escapes():
    """Catch Python triple-quoted HTML converting JS '\n' to a syntax error."""
    from oscar.web import PAGE
    import shutil
    import subprocess

    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    assert r".join('\n')" in script
    assert "join('\n')" not in script  # an actual embedded newline in JS quotes
    assert r"/^\d+$/" in script
    assert r"/^(\d+)\s*-\s*(\d+)$/" in script
    # The browser parses the *rendered* HTML, not the Python source.
    if shutil.which("node"):
        completed = subprocess.run(
            ["node", "--check", "-"],
            input=script, text=True, capture_output=True, check=False,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr


def test_unraid_fuse_rename_fallback_preserves_verified_folder(tmp_path, monkeypatch):
    """FUSE may return EINVAL for RENAME_NOREPLACE despite supporting rename."""
    import errno

    class UnsupportedRename:
        def __call__(self, *args):
            return -1

    class FakeLibc:
        renameat2 = UnsupportedRename()

    monkeypatch.setattr(archive_publish.ctypes, "CDLL", lambda *a, **kw: FakeLibc())
    monkeypatch.setattr(archive_publish.ctypes, "get_errno", lambda: errno.EINVAL)
    src = tmp_path / ".oscar-unpublished-test"
    src.mkdir()
    (src / "01 - Track.flac").write_bytes(b"test source remains identical")
    dest = tmp_path / "Album"
    archive_publish._rename_noreplace(src, dest)
    assert not src.exists()
    assert (dest / "01 - Track.flac").read_bytes() == b"test source remains identical"


def test_unraid_fuse_rename_fallback_never_overwrites_existing_folder(tmp_path, monkeypatch):
    import errno

    class UnsupportedRename:
        def __call__(self, *args):
            return -1

    class FakeLibc:
        renameat2 = UnsupportedRename()

    monkeypatch.setattr(archive_publish.ctypes, "CDLL", lambda *a, **kw: FakeLibc())
    monkeypatch.setattr(archive_publish.ctypes, "get_errno", lambda: errno.EINVAL)
    src = tmp_path / ".oscar-unpublished-test"
    src.mkdir()
    dest = tmp_path / "Album"
    dest.mkdir()
    with pytest.raises(archive_publish.PublishError, match="already exists"):
        archive_publish._rename_noreplace(src, dest)
    assert src.is_dir()
    assert dest.is_dir()


def test_unraid_fuse_directory_fsync_failure_after_promotion_is_not_false_failure(publishable, monkeypatch):
    import errno
    import stat

    real_fsync = archive_publish.os.fsync

    def fuse_fsync(fd):
        if stat.S_ISDIR(archive_publish.os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "FUSE directory fsync unsupported")
        return real_fsync(fd)

    monkeypatch.setattr(archive_publish.os, "fsync", fuse_fsync)
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "standard")
    result = archive_publish._do_publish(plan, "a" * 32,
                                        allow_metadata_observations=True)
    assert result["status"] == "published_verified"
    assert result["directory_sync"].startswith("unavailable:")
    archive = publishable[2]
    assert (archive / result["relative_directory"] / "manifest.json").is_file()


def test_publisher_preserves_cyanrip_extraction_logs(publishable):
    job, _, archive, _ = publishable
    (job / "cyanrip-console.log").write_bytes(b"cyanrip console original")
    (job / "audio" / "original.log").write_bytes(b"cyanrip extraction original")
    originals = {name: (job / name).read_bytes() for name in
                 ("cyanrip-console.log", "audio/original.log", "audio/original.cue")}
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "standard")
    result = archive_publish._do_publish(plan, "1" * 32, allow_metadata_observations=True)
    dest = archive / result["relative_directory"]
    manifest = json.loads((dest / "manifest.json").read_text())
    for record in manifest["source_evidence"]:
        raw = originals[record["original_staging_path"]]
        assert (dest / record["filename"]).read_bytes() == raw
        assert record["sha256"] == hashlib.sha256(raw).hexdigest()


def test_publisher_rejects_changed_extraction_log(publishable):
    job, _, archive, _ = publishable
    original_log = job / "cyanrip-console.log"
    original_log.write_text("original")
    plan = archive_publish.prepare(JOB, COPY, "original_tags", "standard")
    original_log.write_text("changed")
    with pytest.raises(archive_publish.PublishError, match="preview changed"):
        archive_publish._do_publish(plan, "2" * 32, allow_metadata_observations=True)
    assert not list(archive.rglob("manifest.json"))


def test_publisher_rejects_symlinked_extraction_log(publishable, tmp_path):
    job, _, _, _ = publishable
    outside = tmp_path / "outside.log"
    outside.write_text("private")
    (job / "audio" / "unknown.log").symlink_to(outside)
    with pytest.raises(archive_publish.PublishError, match="Unsafe original extraction log"):
        archive_publish.prepare(JOB, COPY, "original_tags", "standard")


def test_missing_catalog_number_warns_in_physical_archive_review(staged):
    source = staged / ("metadata-copy-" + COPY) / "metadata-preview.json"
    original = json.loads(source.read_text(encoding="utf-8"))
    original["album"]["catalog_numbers"] = []
    source.write_text(json.dumps(original), encoding="utf-8")
    before = source.read_bytes()
    result = archive_review.review(JOB, COPY, "original_tags", artwork=False)
    found = [f for f in result["consistency"]["flags"]
             if f["code"] == "missing_release_catalog_number"]
    assert len(found) == 1
    assert found[0]["severity"] == "review"
    assert "MusicBrainz" in found[0]["message"]
    assert result["consistency"]["review_count"] >= 1
    assert source.read_bytes() == before


def test_documented_catalog_number_does_not_raise_missing_warning(staged):
    result = archive_review.review(JOB, COPY, "original_tags", artwork=False)
    assert not any(f["code"] == "missing_release_catalog_number"
                   for f in result["consistency"]["flags"])


def test_matrix_transcription_is_in_proposed_and_published_sources(publishable):
    _, original, archive, _ = publishable
    preview_path = original / "metadata-preview.json"
    preview = json.loads(preview_path.read_text())
    matrix = "936245901-2.2 WME"
    preview["album"]["matrix_runout"] = matrix
    preview_path.write_text(json.dumps(preview))
    plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    proposed = archive_publish.render_sources(plan, "EDITION_NOT_VERIFIED")
    assert f"Physical matrix/runout (operator transcription): {matrix}" in proposed
    published = archive_publish._do_publish(plan, "b" * 32, allow_metadata_observations=True)
    destination = archive / published["relative_directory"]
    assert (destination / "SOURCES.txt").read_text() == proposed
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["provenance"]["physical_matrix_runout"] == {
        "value": matrix, "source": "operator_transcription",
    }


def test_archive_carries_saved_ctdb_evidence(publishable):
    job, _, archive, _ = publishable
    report = {"status": "matched", "method": "ctdb-cli verify", "confidence": 2, "total": 3,
              "trigger": "automatic"}
    path = job / archive_publish.ctdb_verification.REPORT
    path.write_text(json.dumps(report))
    # The separate verifier tests verify binding the report to the real input hashes.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(archive_publish.ctdb_verification, "saved_evidence",
                      lambda *_: (report, hashlib.sha256(path.read_bytes()).hexdigest()))
        plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
        proposed = archive_publish.render_sources(plan, "EDITION_NOT_VERIFIED")
        assert "CTDB: matched (2/3 confidence) via ctdb-cli verify (automatic)" in proposed
        published = archive_publish._do_publish(plan, "b" * 32, allow_metadata_observations=True)
    destination = archive / published["relative_directory"]
    assert (destination / "SOURCES.txt").read_text() == proposed
    assert (destination / "ExtractionEvidence" / path.name).read_bytes() == path.read_bytes()


def test_archive_carries_edition_search_for_selected_release(publishable):
    job, original, archive, _ = publishable
    disc_id = "a" * 28
    preview_path = original / "metadata-preview.json"
    saved_preview = json.loads(preview_path.read_text())
    saved_preview["album"]["musicbrainz_disc_id"] = disc_id
    preview_path.write_text(json.dumps(saved_preview))
    provider = archive_publish.edition_provenance
    provider.save(JOB, disc_id, "disc_lookup", [{"id": RELEASE, "country": "CA"}])
    provider.save(JOB, disc_id, "combined_search", [{
        "id": RELEASE, "country": "CA", "sources": ["disc_lookup", "barcode"],
        "catalog_matches": True, "barcode_matches": True,
        "discogs": [{"id": 4709815, "country": "Germany",
                     "link": "Shared artist, title, barcode and catalog number",
                     "variants": [{"variant": "Variant 1",
                                   "comparison": {"Matrix / Runout": "matches"}}]}],
    }], identifiers={"barcode": "3259180002527", "matrix": "800 025-2 02"}, suggested=RELEASE)
    assert provider.for_release(job, JOB, "b" * 28, RELEASE) is None
    assert provider.for_release(job, JOB, disc_id, "b" * 36) is None
    plan = archive_publish.prepare(JOB, COPY, "original_tags", profile="standard")
    proposed = archive_publish.render_sources(plan, "EDITION_NOT_VERIFIED")
    assert "[Edition search]" in proposed
    assert "MusicBrainz release country: CA" in proposed
    assert "Discogs release country: Germany" in proposed
    assert "Variant 1: Matrix / Runout matches" in proposed
    assert "Combined search suggested this candidate: yes" in proposed
    result = archive_publish._do_publish(plan, "b" * 32, allow_metadata_observations=True)
    destination = archive / result["relative_directory"]
    assert (destination / "SOURCES.txt").read_text() == proposed
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["provenance"]["edition_search"] == plan["provenance"]["edition_search"]


def _cover_image(color):
    from io import BytesIO
    from PIL import Image

    data = BytesIO()
    Image.new("RGBA", (80, 64), color).save(data, "PNG")
    return data.getvalue()


def test_cover_upload_preview_and_archive_flac_embedding(publishable, monkeypatch):
    from base64 import b64decode

    _, tagged, archive, original_hashes = publishable
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIP", "true")
    client = TestClient(app)
    path = f"/api/rip/jobs/{JOB}/cover-art/{COPY}?source=upload"
    assert client.post(path, content=b"unauthenticated").status_code == 403
    auth = {"X-OSCAR-Rip-Token": TOKEN}
    assert client.post(path, headers=auth, content=b"bad image").status_code == 409
    response = client.post(path, headers=auth, content=_cover_image("red"))
    assert response.status_code == 200, response.text
    selected = response.json()
    jpeg = b64decode(selected["preview"].split(",", 1)[1])
    assert jpeg.startswith(b"\xff\xd8")
    assert selected["artwork"]["provider"] == "upload"
    assert selected["artwork"]["sha256"] == hashlib.sha256(jpeg).hexdigest()
    plan = archive_publish.prepare(JOB, COPY, "original_tags", include_cover=True)
    assert plan["provenance"]["artwork"] == selected["artwork"]
    assert "Front cover: User upload" in archive_publish.render_sources(plan, "EDITION_NOT_VERIFIED")

    response = client.post(path, headers=auth, content=_cover_image("blue"))
    assert response.status_code == 200
    with pytest.raises(archive_publish.PublishError, match="changed"):
        archive_publish._do_publish(plan, "a" * 32, allow_metadata_observations=True)
    renewed = archive_publish.prepare(JOB, COPY, "original_tags", include_cover=True)
    assert renewed["fingerprint"] != plan["fingerprint"]
    published = archive_publish._do_publish(renewed, "b" * 32, allow_metadata_observations=True)
    destination = archive / published["relative_directory"]
    folder_jpeg = (destination / "folder.jpg").read_bytes()
    assert folder_jpeg == b64decode(response.json()["preview"].split(",", 1)[1])
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["provenance"]["artwork"]["sha256"] == hashlib.sha256(folder_jpeg).hexdigest()
    sources = (destination / "SOURCES.txt").read_text()
    for item, entry in zip(manifest["files"], renewed["tracks"], strict=True):
        path = destination / item["filename"]
        flac = FLAC(path)
        original = FLAC(tagged / entry["source"])
        assert flac.tags == original.tags
        assert flac.info.md5_signature == original.info.md5_signature
        assert [(p.type, p.mime, p.data) for p in flac.pictures] == [(3, "image/jpeg", folder_jpeg)]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert f"Published FLAC SHA-256: {item['sha256']}" in sources
    for rel, digest in original_hashes.items():
        assert hashlib.sha256((tagged / rel).read_bytes()).hexdigest() == digest


def test_cover_lookup_prefers_exact_musicbrainz_then_linked_discogs(tmp_path, monkeypatch):
    from oscar import cover_art

    calls = []
    archive = tmp_path / "musicbrainz"
    archive.mkdir()
    discogs = tmp_path / "discogs"
    discogs.mkdir()

    def download(url):
        calls.append(url)
        if url.startswith("https://coverartarchive.org") and len(calls) > 1:
            raise urllib.error.HTTPError(url, 404, "missing", None, None)
        return _cover_image("red")

    monkeypatch.setattr(cover_art, "_download", download)
    monkeypatch.setattr(cover_art.discogs_readonly, "configured", lambda: True)
    monkeypatch.setattr(cover_art, "fetch_json", lambda request: {
        "id": RELEASE,
        "relations": [{"type": "discogs", "url": {"resource": "https://www.discogs.com/release/42"}}],
    })
    monkeypatch.setattr(cover_art.discogs_readonly, "_get", lambda path: {
        "id": 42, "formats": [{"name": "CD"}],
        "images": [{"type": "primary", "uri": "https://i.discogs.com/front.jpg"}],
    })

    assert cover_art.select(archive, RELEASE, "auto")[0]["provider"] == "musicbrainz"
    assert calls == [f"https://coverartarchive.org/release/{RELEASE}/front-1200"]
    info, _ = cover_art.select(discogs, RELEASE, "auto")
    assert info["provider"] == "discogs"
    assert info["source"] == "https://www.discogs.com/release/42"
    assert calls[-3:] == [
        f"https://coverartarchive.org/release/{RELEASE}/front-1200",
        f"https://coverartarchive.org/release/{RELEASE}/front",
        "https://i.discogs.com/front.jpg",
    ]
    assert cover_art.select(discogs, RELEASE, "auto")[0] == info
    assert len(calls) == 4
