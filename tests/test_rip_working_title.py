import json
from oscar import rip_working_title as hints


DISC = "x" * 28


def test_album_hint_groups_pressings_but_does_not_guess_a_tie():
    releases = [
        {"id": "a", "artist": "Jean-Michel Jarre", "title": "Équinoxe"},
        {"id": "b", "artist": "Jean Michel Jarre", "title": "Equinoxe"},
        {"id": "c", "artist": "Jean-Michel Jarre", "title": "Oxygène / Équinoxe"},
    ]
    assert hints.summarize(releases) == "Jean-Michel Jarre — Équinoxe"
    assert hints.summarize(releases[1:]) == ""
    assert hints.summarize([releases[0], releases[0], releases[2]]) == ""


def test_completed_staging_hint_is_saved_separately(tmp_path, monkeypatch):
    job_id = "a" * 32
    directory = tmp_path / ("oscar-" + job_id)
    directory.mkdir()
    state = {"id": job_id, "status": "needs_verification", "disc_id": DISC}
    (directory / "state.json").write_text(json.dumps(state))
    plan = {"disc_id": DISC, "toc_string": "1 2 450 150 300"}
    (directory / "plan.json").write_text(json.dumps(plan))
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(tmp_path))
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    calls = []
    monkeypatch.setattr(hints._WORKER, "submit", lambda fn, *args: calls.append((fn, args)))
    monkeypatch.setattr(hints.musicbrainz, "lookup_releases", lambda *_: {
        "releases": [{"id": "edition", "artist": "Alanis Morissette",
                      "title": "Jagged Little Pill"}],
    })
    assert hints.display(job_id, DISC, schedule=True) == ""
    assert hints.display(job_id, DISC, schedule=True) == ""
    assert len(calls) == 1
    worker, args = calls[0]
    worker(*args)
    assert hints.display(job_id, DISC, schedule=True) == "Alanis Morissette — Jagged Little Pill"
    assert json.loads((directory / "state.json").read_text()) == state
    assert json.loads((directory / "plan.json").read_text()) == plan
    assert hints.display(job_id, "y" * 28) == ""
