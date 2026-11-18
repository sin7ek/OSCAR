"""Classical metadata: MusicBrainz credits are not role assignments."""
from oscar.classical import recording_roles
from oscar.boxsets import parse_release_media

DISC_ID = "sT6cTPp0_qZRfvu1jHQ8VBNx.X4-"


def test_composer_and_performers_from_explicit_relationships():
    recording = {"id": "r1", "artist-credit": [{"name": "Igor Stravinsky"}], "relations": [
        {"type": "conductor", "target-type": "artist",
         "artist": {"name": "Pierre Boulez", "id": "b1"}},
        {"type": "performing orchestra", "target-type": "artist",
         "artist": {"name": "Orchestra A", "id": "o1"}},
        {"type": "performance", "target-type": "work",
         "work": {"id": "work1", "title": "Pastorale", "relations": [
             {"type": "composer", "target-type": "artist",
              "artist": {"name": "Igor Stravinsky", "id": "c1"}}
         ]}}
    ]}
    result = recording_roles(recording)
    assert [v["name"] for v in result["composers"]] == ["Igor Stravinsky"]
    assert [v["name"] for v in result["performers"]] == ["Pierre Boulez", "Orchestra A"]
    assert result["works"][0]["title"] == "Pastorale"


def test_artist_credit_alone_does_not_imply_composer_or_performer():
    recording = {"artist-credit": [{"name": "Igor Stravinsky"}]}
    result = recording_roles(recording)
    assert result["composers"] == []
    assert result["performers"] == []


def test_release_parsing_preserves_credit_without_mislabeling_it():
    data = {"id": "release", "title": "Box", "media": [{
        "position": 6, "track-count": 1, "discs": [{"id": DISC_ID}],
        "tracks": [{"position": 1, "title": "Song", "artist-credit": [{"name": "Igor Stravinsky"}],
                    "recording": {"id": "rec", "artist-credit": [{"name": "Igor Stravinsky"}]}}]
    }]}
    item = parse_release_media(data, DISC_ID, 1)["matched_media"][0]["tracks"][0]
    assert item["artist_credit"] == "Igor Stravinsky"
    assert not item["performers"]
    assert not item["composers"]


def test_vocal_and_work_roles_are_not_conflated():
    recording = {"relations": [
        {"type": "vocal", "target-type": "artist",
         "artist": {"name": "Singer", "id": "s1"}, "attributes": ["soprano"]},
        {"type": "performance", "target-type": "work",
         "work": {"id": "w1", "title": "Lied", "relations": [
             {"type": "lyricist", "target-type": "artist",
              "artist": {"name": "Poet", "id": "l1"}}
         ]}}
    ]}
    result = recording_roles(recording)
    assert result["performers"][0]["name"] == "Singer"
    assert result["performers"][0]["attributes"] == ["soprano"]
    assert result["composers"] == []


def test_same_artist_can_have_different_roles():
    recording = {"relations": [
        {"type": "conductor", "target-type": "artist",
         "artist": {"name": "Artist X", "id": "x"}},
        {"type": "performance", "target-type": "work", "work": {
            "id": "w", "relations": [
                {"type": "composer", "target-type": "artist",
                 "artist": {"name": "Artist X", "id": "x"}}
            ]}}
    ]}
    result = recording_roles(recording)
    assert len(result["composers"]) == 1
    assert len(result["performers"]) == 1
