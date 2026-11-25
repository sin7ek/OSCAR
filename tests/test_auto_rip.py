"""Insertion and Settings regressions for opt-in tracked starts."""
from threading import Event

import pytest
from fastapi.testclient import TestClient

from oscar import auto_rip, go_controller, ripping, settings
from oscar.api import app


DRIVE = "ata-insertion-test"
TOKEN = "rip-token-for-insertion-settings"


@pytest.fixture
def watcher(monkeypatch):
    preference = settings.DriveSettings(
        stable_id=DRIVE, label="Test", enabled=True, offset_samples=0)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setattr(settings, "read_settings", lambda: settings.OscarSettings(drives=[preference]))
    monkeypatch.setattr(settings, "inspect_drives", lambda: [
        {"stable_id": DRIVE, "device": "/dev/sr7", "identity_persistent": True}])
    state = {"observed": {"status": "disc_present", "audio_tracks": 7},
             "count": 0, "idle": True, "slot": True, "probes": 0, "starts": []}

    def probe(device):
        assert device == "/dev/sr7"
        state["probes"] += 1
        return state["observed"]

    def start(stable_id, *, insertion_count):
        assert stable_id == DRIVE and insertion_count == state["count"]
        state["starts"].append(insertion_count)
        state["count"] += 1

    monkeypatch.setattr(auto_rip.media, "probe_device", probe)
    monkeypatch.setattr(ripping, "insertion_status",
                        lambda _: (state["count"], state["idle"], state["slot"]))
    monkeypatch.setattr(go_controller, "start_tracked_rip", start)
    insertions = {}
    stop = Event()

    def sample(status, audio=0, times=1):
        state["observed"] = {"status": status, "audio_tracks": audio}
        for _ in range(times):
            auto_rip.poll(insertions, stop)

    return preference, state, sample, insertions


def test_opt_in_insert_and_restart_deduplication(watcher):
    drive, state, sample, insertions = watcher
    sample("disc_present", audio=7, times=2)
    assert state["probes"] == 0
    drive.auto_rip_on_insert = True
    sample("disc_present", audio=7, times=2)
    assert state["starts"] == []
    sample("no_disc")
    sample("disc_present", audio=7, times=4)
    assert state["starts"] == [0]
    insertions.clear()
    sample("disc_present", audio=7, times=4)
    assert state["starts"] == [0]
    sample("tray_open")
    sample("disc_present", audio=7, times=2)
    assert state["starts"] == [0, 1]


def test_data_and_transient_samples_wait_and_manual_start_consumes_insertion(watcher):
    drive, state, sample, _ = watcher
    drive.auto_rip_on_insert = True
    state["slot"] = False
    sample("no_disc")
    sample("disc_present", times=3)
    sample("not_ready")
    sample("disc_present", audio=7, times=3)
    assert not state["starts"]
    state["count"] = 1  # A manual or diagnostic start already reserved this drive.
    state["slot"] = True
    sample("disc_present", audio=7, times=3)
    assert not state["starts"]
    sample("tray_open")
    sample("disc_present", audio=7)
    sample("not_ready")
    sample("disc_present", audio=7)
    assert not state["starts"]
    sample("disc_present", audio=7)
    assert state["starts"] == [1]


def test_insertion_rechecks_settings_and_reservation_before_start(tmp_path, monkeypatch):
    monkeypatch.setattr(ripping, "plan", lambda *a, **k: {"offset_samples": 0})
    monkeypatch.setattr(ripping, "staging_root", lambda: tmp_path)
    monkeypatch.setattr(settings, "read_settings", lambda: settings.OscarSettings())
    callbacks = {"on_created": lambda _: None, "on_completed": lambda _: None}
    with pytest.raises(ripping.RipError, match="already started"):
        ripping.start(DRIVE, insertion_count=-1, **callbacks)
    with pytest.raises(ripping.RipError, match="disabled"):
        count, _, _ = ripping.insertion_status(DRIVE)
        ripping.start(DRIVE, insertion_count=count, **callbacks)
    assert not list(tmp_path.iterdir())


def test_settings_auto_rip_requires_existing_rip_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    body = {"drives": [{"stable_id": DRIVE, "label": "Test", "enabled": True,
                        "auto_rip_on_insert": True, "offset_samples": 0}]}
    assert client.put("/api/settings", json=body).status_code == 403
    headers = {"X-OSCAR-RIP-TOKEN": TOKEN}
    assert client.put("/api/settings", json=body, headers=headers).status_code == 200
    body["drives"][0]["auto_rip_on_insert"] = False
    assert client.put("/api/settings", json=body).status_code == 403
    assert client.put("/api/settings", json=body, headers=headers).status_code == 200


def test_automatic_start_registers_existing_go_workflow_with_insertion_evidence(tmp_path, monkeypatch):
    from oscar import workflow_ledger

    root = tmp_path / "staging"
    root.mkdir()
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(tmp_path / "catalog.sqlite3"))
    drive = settings.DriveSettings(
        stable_id=DRIVE, label="Test", enabled=True, offset_samples=0, auto_rip_on_insert=True)
    settings.save_settings(settings.OscarSettings(drives=[drive], identification_mode="semi_automatic"))
    monkeypatch.setattr(ripping, "plan", lambda *a, **k: {
        "device": "/dev/sr7", "offset_samples": 0, "disc_id": "a" * 28, "selected_tracks": None})
    monkeypatch.setattr(ripping, "_ACTIVE", set())
    monkeypatch.setattr(ripping, "_JOBS", {})
    monkeypatch.setattr(ripping, "_START_COUNTS", {})

    class DeferredThread:
        def __init__(self, **kwargs):
            assert kwargs["args"][-1] is go_controller._after_rip

        def start(self):
            pass

    monkeypatch.setattr(ripping.threading, "Thread", DeferredThread)
    job = go_controller.start_tracked_rip(DRIVE, insertion_count=0)
    assert job["start_trigger"] == "disc_insertion"
    with workflow_ledger._db() as db:
        saved = workflow_ledger._view(db, job["id"])
    assert saved["phase"] == "RIP_IN_PROGRESS"
    assert saved["identification_mode"] == "semi_automatic"
    assert saved["events"][0]["reason"] == "disc_insertion_before_extraction"
