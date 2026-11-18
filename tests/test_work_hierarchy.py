"""Conservative classical work hierarchy regression cases.

These fixtures are synthetic, reflecting user-provided track titles and credited
performers; MusicBrainz parent links here are simulated, not verified live data.
"""
from oscar.work_hierarchy import group_tracks, work_details
from oscar.boxsets import parse_release_media


def rel(parent_id: str, parent_title: str):
    return {"target-type": "work", "type": "parts", "direction": "backward",
            "work": {"id": parent_id, "title": parent_title}}


def recording(work_id, title, parents=None):
    return {"id": "rec-"+work_id, "relations": [
        {"target-type": "work", "type": "performance",
         "work": {"id": work_id, "title": title, "relations": parents or []}}
    ]}


def get_track(number, title, rec):
    return {"number": str(number), "position": number, "title": title,
            "work_details": work_details(rec)}


def test_savall_water_music_suite_group_when_explicit_parent_rels_present():
    a = get_track(1, "Water Music, Suite I: Prélude",
                  recording("wm-1", "Prélude", [rel("suite-i", "Water Music, Suite I")]))
    b = get_track(2, "Water Music, Suite I: Menuet I",
                  recording("wm-2", "Menuet I", [rel("suite-i", "Water Music, Suite I")]))
    groups = group_tracks([a, b])
    assert len(groups) == 1
    assert groups[0]["parent_work_id"] == "suite-i"
    assert groups[0]["tracks"] == ["1", "2"]


def test_tchaikovsky_symphony_movements_group_when_explicit_parent():
    a = get_track(1, "Symphony no. 5: I. Andante – Allegro con anima",
                  recording("t-1", "I. Andante – Allegro con anima",
                            [rel("symph-5", "Symphony no. 5 in E minor, op. 64")]))
    b = get_track(2, "Symphony no. 5: II. Andante cantabile",
                  recording("t-2", "II. Andante cantabile",
                            [rel("symph-5", "Symphony no. 5 in E minor, op. 64")]))
    assert group_tracks([a,b])[0]["parent_work_title"].startswith("Symphony no. 5")


def test_not_guessing_from_track_titles():
    a = get_track(1, "Symphony no. 5: I", recording("t-1", "I"))
    b = get_track(2, "Symphony no. 5: II", recording("t-2", "II"))
    groups = group_tracks([a, b])
    assert len(groups) == 2
    assert all(g["source"] == "ungrouped" for g in groups)


def test_multi_parent_ambiguous_stays_ungrouped():
    track = get_track(1, "Mixed work", recording(
        "mix", "Mixed", [rel("parent-a", "Suite A"), rel("parent-b", "Suite B")]
    ))
    assert group_tracks([track])[0]["source"] == "ungrouped"


def test_non_contiguous_parent_is_not_merged_across_other_work():
    tracks = [
        get_track(1, "One", recording("a", "A", [rel("s1", "Suite 1")])),
        get_track(2, "Other", recording("b", "B")),
        get_track(3, "Three", recording("c", "C", [rel("s1", "Suite 1")]))
    ]
    assert len(group_tracks(tracks)) == 3


def test_reversed_parts_relation_is_not_parent():
    work = recording("w", "Mov", [{
        "target-type": "work", "type": "parts", "direction": "forward",
        "work": {"id": "child", "title": "Child"}
    }])
    assert work_details(work)[0]["parents"] == []


def test_medium_includes_hierarchy_without_assigning_release_edition():
    from oscar.classical import recording_roles
    disc_id = "sT6cTPp0_qZRfvu1jHQ8VBNx.X4-"
    payload = {"id":"release", "title":"Example","media":[{"position":1, "track-count":2,
        "discs":[{"id":disc_id}], "tracks":[
            {"position":1,"number":"1","title":"Prélude",
             "recording":recording("w1","Prélude",[rel("water","Water Music")])},
            {"position":2,"number":"2","title":"Menuet",
             "recording":recording("w2","Menuet",[rel("water","Water Music")])}
        ]}]}
    result = parse_release_media(payload,disc_id,2)
    assert result["requires_review"]
    medium = result["matched_media"][0]
    assert medium["work_groups"][0]["tracks"] == ["1", "2"]
    assert medium["tracks"][0]["work_details"][0]["id"] == "w1"
