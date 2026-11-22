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
