import pytest

from oscar import edition_search as search


@pytest.mark.parametrize("conflict, linked", [(False, False), (False, True), (True, True)])
def test_discogs_link_and_pressing_evidence_rank_musicbrainz_candidates(monkeypatch, conflict, linked):
    first = "e410a90a-d96c-3ac1-a65c-ac947016ffb1"
    other = "6bca182b-7155-4240-8dec-222b45ad545e"
    barcode = "3259180002527"
    disc_id = "a" * 28
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    monkeypatch.setenv("OSCAR_DISCOGS_PAT", "fixture-token")
    monkeypatch.setattr(search.ripping, "status", lambda _: {
        "status": "needs_verification", "disc_id": disc_id})
    from oscar import go_controller
    monkeypatch.setattr(go_controller, "_source_plan", lambda _: {
        "disc_id": disc_id, "toc_string": "1 2 450 150 300"})
    monkeypatch.setattr(search.musicbrainz, "lookup_releases", lambda *_: {
        "releases": [{"id": other, "title": "Équinoxe", "barcode": "80002529"}]})
    monkeypatch.setattr(search.musicbrainz, "search_release_candidates", lambda **_: {
        "releases": [{"id": first, "title": "Équinoxe", "artist": "Jean Michel Jarre",
                      "country": "CA",
                      "barcode": "99999999" if conflict else barcode,
                      "labels": [{"catalog_number": "800 025-2"}]}]})
    monkeypatch.setattr(search, "_discogs_candidates", lambda *_: {"releases": [{
        "id": 4709815, "title": "Equinoxe", "artist": "Jean-Michel Jarre",
        "country": "Germany", "barcodes": ["3 259180 002527"],
        "catalog_numbers": ["800 025-2"], "variants": [{"variant": "Variant 1",
                                    "comparison": {"Matrix / Runout": "matches"}}]}]})
    monkeypatch.setattr(search, "_discogs_links", lambda _: {first: {4709815}} if linked else {})
    result = search.search("a" * 32, catalog="800 025-2", barcode=barcode,
                           matrix="800 025-2 02", mastering_sid="", mould_sid="")
    assert result["recommended"] == (None if conflict else first)
    release = next(row for row in result["releases"] if row["id"] == first)
    assert release["country"] == "CA"
    assert release["discogs"][0]["country"] == "Germany"
    assert release["discogs"][0]["link"] == (
        "MusicBrainz URL relation" if linked else "Shared artist, title, barcode and catalog number")
