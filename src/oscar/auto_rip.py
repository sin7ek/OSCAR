"""Opt-in audio-disc insertion monitor for configured optical drives."""

import logging
from dataclasses import dataclass

from oscar import go_controller, media, ripping, settings

LOG = logging.getLogger(__name__)


@dataclass
class Insertion:
    start_count: int
    armed: bool = False
    audio_observations: int = 0


def poll(insertions, stop):
    """Start only after observing empty media followed by stable audio media."""
    configured = {
        drive.stable_id for drive in settings.read_settings().drives
        if drive.enabled and drive.auto_rip_on_insert and drive.offset_samples is not None
    }
    drives = {
        drive["stable_id"]: drive["device"] for drive in settings.inspect_drives()
        if drive["identity_persistent"] and drive["stable_id"] in configured
    } if configured and ripping.enabled() else {}
    for stable_id in insertions.keys() - drives.keys():
        del insertions[stable_id]

    for stable_id, device in drives.items():
        if stop.is_set():
            return
        count, idle, slot_available = ripping.insertion_status(stable_id)
        insertion = insertions.get(stable_id)
        if insertion is None or insertion.start_count != count:
            insertion = insertions[stable_id] = Insertion(count)
        if not idle:
            insertion.audio_observations = 0
            continue
        observed = media.probe_device(device)
        status = observed["status"]
        if status in {"tray_open", "no_disc"}:
            insertion.armed = True
            insertion.audio_observations = 0
            continue
        if status != "disc_present" or not observed.get("audio_tracks"):
            insertion.audio_observations = 0
            continue
        if not insertion.armed:
            continue
        insertion.audio_observations += 1
        if insertion.audio_observations < 2 or not slot_available or stop.is_set():
            continue
        insertion.armed = False
        try:
            go_controller.start_tracked_rip(stable_id, insertion_count=count)
        except (OSError, ValueError, RuntimeError) as error:
            LOG.warning("Automatic rip did not start for %s: %s", stable_id, error)


def watch_insertions(stop):
    insertions = {}
    while not stop.is_set():
        try:
            poll(insertions, stop)
        except (OSError, ValueError, RuntimeError) as error:
            insertions.clear()
            LOG.warning("Automatic disc detection failed: %s", error)
        stop.wait(3)
