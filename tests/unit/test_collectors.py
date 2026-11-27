import json

import pytest

from discogs_pipeline.collectors import TooManyFailures
from discogs_pipeline.collectors.discovery import release_ids_from_search, run_discovery, search_params, seed_origin
from discogs_pipeline.collectors.entities import entity_ids, run_new_entities
from discogs_pipeline.collectors.snapshot import run_snapshot
from discogs_pipeline.collectors.users import run_user_lists
from discogs_pipeline.storage import LocalLake, bronze_key, write_bronze
from discogs_pipeline.tracking import KnownEntities, TrackedReleases, TrackingConfig, load_config

from fakes import FakeClient, release

DS = "2026-11-27"


@pytest.fixture
def lake(tmp_path):
    return LocalLake(tmp_path)


def bronze_lines(lake, entity):
    raw = lake.get_bytes(bronze_key(entity, DS)).decode()
    return [json.loads(line) for line in raw.splitlines() if line]


def test_load_config_ignores_placeholder_username(tmp_path):
    cfg = tmp_path / "t.yml"
    cfg.write_text("usernames: [your_username_here, vitor]\ndiscovery: [{year: 1991}]\nlimits: {max_tracked_releases: 7}\n")
    config = load_config(cfg)
    assert config.usernames == ["vitor"]
    assert config.max_tracked_releases == 7
    assert config.max_failure_ratio == 0.2


def test_tracked_releases_only_grow(lake):
    tracked = TrackedReleases(lake)
    assert tracked.add(10, "discovery:1991", DS)
    assert not tracked.add(10, "collection:vitor", "2027-01-01")
    tracked.save()
    reloaded = TrackedReleases(lake)
    assert reloaded.ids() == [10]
    assert reloaded.data["10"] == {"origin": "discovery:1991", "first_seen": DS}


def test_search_results_only_yield_release_ids():
    # Real /database/search shape: label is a list of names and there is no artist field.
    results = [
        {"id": 1, "type": "release", "label": ["Liquid Records", "Tidal"]},
        {"id": 2, "type": "master"},
        {"id": 3, "type": "release", "label": []},
    ]
    assert release_ids_from_search(results) == [1, 3]


def test_seed_to_search_params():
    seed = {"year": 1991, "genre": "Rock", "pages": 2}
    assert seed_origin(seed) == "discovery:1991-Rock"
    assert search_params(seed) == {"year": 1991, "genre": "Rock", "type": "release", "sort": "want", "sort_order": "desc"}


def test_discovery_respects_tracking_cap(lake):
    results = [{"id": i, "type": "release"} for i in range(10)]
    client = FakeClient(pages={"/database/search": results})
    config = TrackingConfig(discovery=[{"year": 1991}], max_tracked_releases=4)
    out = run_discovery(client, lake, config, DS)
    assert out == {"results": 10, "added": 4, "tracked": 4}
    assert len(bronze_lines(lake, "search")) == 10


def test_user_lists_track_their_releases(lake):
    client = FakeClient(pages={
        "/users/vitor/collection/folders/0/releases": [{"id": 5, "instance_id": 1}, {"id": 5, "instance_id": 2}],
        "/users/vitor/wants": [{"id": 6}],
    })
    run_user_lists(client, lake, TrackingConfig(usernames=["vitor"]), DS)
    assert TrackedReleases(lake).data["5"]["origin"] == "collection:vitor"
    assert TrackedReleases(lake).data["6"]["origin"] == "wantlist:vitor"
    assert [r["username"] for r in bronze_lines(lake, "collection")] == ["vitor", "vitor"]


def test_snapshot_fetches_release_and_usd_stats(lake):
    tracked = TrackedReleases(lake)
    tracked.add(1, "x", DS)
    tracked.add(2, "x", DS)
    tracked.save()
    client = FakeClient(routes={
        "/releases/1": release(1),
        "/marketplace/stats/1": {"lowest_price": {"value": 9.5, "currency": "USD"}, "num_for_sale": 3},
        # release 2 was removed from Discogs (404)
    })
    out = run_snapshot(client, lake, TrackingConfig(), DS)
    assert out == {"tracked": 2, "releases": 1, "stats": 1, "failed": 0}


def test_snapshot_fails_when_too_many_calls_fail(lake):
    tracked = TrackedReleases(lake)
    for i in range(3):
        tracked.add(i, "x", DS)
    tracked.save()
    client = FakeClient(fail={"/releases/0", "/releases/1"})
    with pytest.raises(TooManyFailures):
        run_snapshot(client, lake, TrackingConfig(max_failure_ratio=0.5), DS)


def test_entity_ids_skip_placeholders():
    payload = release(1, artists=((1, "Nirvana"), (0, "Various")), label=(0, "Not On Label", "none"))
    assert entity_ids(payload) == {"artists": {1}, "labels": set(), "masters": {13814}}


def test_new_entities_are_fetched_once(lake):
    write_bronze(lake, "releases", DS, [{"id": 1, "data": release(1)}])
    routes = {"/artists/1": {"id": 1, "name": "Nirvana"}, "/labels/895": {"id": 895, "name": "DGC"},
              "/masters/13814": {"id": 13814, "title": "Nevermind"}}
    client = FakeClient(routes=routes)
    assert run_new_entities(client, lake, TrackingConfig(), DS) == {"artists": 1, "labels": 1, "masters": 1}
    assert KnownEntities(lake).unknown("artists", {1, 2}) == [2]

    again = FakeClient(routes=routes)
    run_new_entities(again, lake, TrackingConfig(), DS)
    assert again.calls == []
