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
    assert first["RIPPED_WITH"] == "Ripped with OSCAR - Preserve Every Note."
    assert first["RIPPER_URL"] == "https://github.com/sin7ek/OSCAR"
    assert first["COMPOSER"]==["George Frideric Handel"]
    assert first["CONDUCTOR"]==["Jordi Savall"]
    assert first["ORCHESTRA"]==["Le Concert des Nations"]
    assert first["WORK"]==["Allegro"]
    assert first["GROUPING"]==["Water Music"]
    assert first["MUSICBRAINZ_TRACKID"]=="rec-1"
    assert first["MUSICBRAINZ_RELEASETRACKID"]=="track-1"
    assert len(plan["fingerprint"])==64
    assert not list(setup.glob("metadata-copy-*"))


def test_preview_maps_unpadded_source_names_without_changing_rip(setup):
    audio = setup / "audio"
    manifest = {}
    for number in (1, 2):
        original = audio / f"{number:02d} - Unknown track.flac"
        renamed = audio / f"{number} - Unknown track.flac"
        original.rename(renamed)
        manifest[f"audio/{renamed.name}"] = hashlib.sha256(renamed.read_bytes()).hexdigest()
    state_path = setup / "state.json"
    state = json.loads(state_path.read_text())
    state["files_sha256"] = manifest
    state_path.write_text(json.dumps(state))
    before = {p.name: p.read_bytes() for p in audio.iterdir()}
    plan = metadata.preview(JOB, RELEASE, lookup=lookup)
    assert [track["original_file"] for track in plan["tracks"]] == [
        "audio/1 - Unknown track.flac", "audio/2 - Unknown track.flac"]
    assert len(plan["fingerprint"]) == 64
    assert before == {p.name: p.read_bytes() for p in audio.iterdir()}


def test_operator_accepted_single_cd_without_discid_can_prepare_reviewed_preview(setup):
    info = medium_payload()
    medium = info["matched_media"][0]
    medium.update({"disc_id_attached": False, "format": "CD"})
    info.update({"status": "no_exact_medium_match", "matched_media": [],
                 "all_media": [medium]})

    def accepted_lookup(release, disc, count):
        assert (release, disc, count) == (RELEASE, DISC, 2)
        return info

    with pytest.raises(metadata.MetadataError, match="exact Disc ID"):
        metadata.preview(JOB, RELEASE, lookup=accepted_lookup)
    plan = metadata.preview(JOB, RELEASE, lookup=accepted_lookup,
                            operator_accepted=True)
    assert plan["disc_number"] == 1
    assert plan["medium_match_method"] == "single_cd_operator_accepted_track_count_only"
    assert "NO attached matching Disc ID" in plan["source"]
    assert any("not Disc ID or physical-edition verification" in warning
               for warning in plan["warnings"])
    assert plan["requires_review"] and not plan["approved"]


def test_operator_acceptance_cannot_guess_boxset_medium_from_count(setup):
    info = medium_payload()
    medium = info["matched_media"][0]
    medium.update({"disc_id_attached": False, "format": "CD"})
    info.update({"status": "no_exact_medium_match", "matched_media": [],
                 "total_media": 2, "all_media": [medium]})
    with pytest.raises(metadata.MetadataError, match="exact Disc ID"):
        metadata.build_preview(info, JOB, DISC, 2, operator_accepted=True)


def test_operator_acceptance_rejects_wrong_count_or_format_or_multiple_media(setup):
    for invalid in ("wrong_count", "wrong_format", "duplicates"):
        info = medium_payload()
        medium = info["matched_media"][0]
        medium.update({"disc_id_attached": False, "format": "CD"})
        info.update({"status": "no_exact_medium_match", "matched_media": [],
                     "all_media": [medium]})
        if invalid == "wrong_count":
            medium["track_count"] = 99
        elif invalid == "wrong_format":
            medium["format"] = "Digital Media"
        else:
            info["all_media"].append(dict(medium))
        with pytest.raises(metadata.MetadataError, match="compatible CD medium"):
            metadata.build_preview(info, JOB, DISC, 2, operator_accepted=True)


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


class FakeFLACInteger(FakeFLAC):
    """Match Mutagen's real STREAMINFO MD5 representation: an integer."""
    def __init__(self, path):
        super().__init__(path)
        self.info.md5_signature = int.from_bytes(bytes.fromhex("a1" * 16), "big")


def test_streaminfo_md5_mutagen_integer_and_leading_zeros():
    assert metadata._streaminfo_md5_hex(int("a1" * 16, 16)) == "a1" * 16
    assert metadata._streaminfo_md5_hex(1) == "0" * 31 + "1"
    assert metadata._streaminfo_md5_hex(bytes.fromhex("a1" * 16)) == "a1" * 16
    with pytest.raises(metadata.MetadataError):
        metadata._streaminfo_md5_hex(-1)
    with pytest.raises(metadata.MetadataError):
        metadata._streaminfo_md5_hex(1 << 128)


def test_tagged_copy_with_actual_mutagen_integer_md5_representation(setup):
    original = {p.name: p.read_bytes() for p in (setup / "audio").iterdir()}
    plan = metadata.preview(JOB, RELEASE, lookup=lookup)
    output = metadata._tagged_copy(
        JOB, RELEASE, plan["fingerprint"], "d" * 32,
        lookup=lookup, flac_factory=FakeFLACInteger, runner=fake_runner)
    assert output["status"] == "tagged_copy_ready_for_review"
    assert len(output["files"]) == 2
    assert {v["audio_streaminfo_md5"] for v in output["files"].values()} == {"a1" * 16}
    assert original == {p.name: p.read_bytes() for p in (setup / "audio").iterdir()}


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


def test_real_flac_mutagen_streaminfo_md5_roundtrip(tmp_path):
    """End-to-end actual FLAC: tagging must preserve decoded audio."""
    import shutil
    import struct
    import subprocess
    import wave

    if shutil.which("flac") is None:
        pytest.skip("Requires flac binary (installed in OSCAR Docker image)")
    from mutagen.flac import FLAC
    wav = tmp_path / "sample.wav"
    path = tmp_path / "sample.flac"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(struct.pack("<1000h", *[0] * 1000))
    subprocess.run(["flac", "--silent", "-f", "-o", str(path), str(wav)], check=True)
    original_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    audio = FLAC(str(path))
    assert isinstance(audio.info.md5_signature, int)
    original_md5 = metadata._streaminfo_md5_hex(audio.info.md5_signature)
    audio["ALBUM"] = ["Music for the Royal Fireworks"]
    audio["COMPOSER"] = ["George Frideric Handel"]
    audio.save()
    reread = FLAC(str(path))
    assert reread["album"] == ["Music for the Royal Fireworks"]
    assert reread["composer"] == ["George Frideric Handel"]
    assert metadata._streaminfo_md5_hex(reread.info.md5_signature) == original_md5
    assert hashlib.sha256(path.read_bytes()).hexdigest() != original_sha
    subprocess.run(["flac", "-t", "--silent", str(path)], check=True)
