"""Discogs API test doubles with payloads in the documented shape."""

from discogs_pipeline.api import DiscogsError


def release(release_id, *, artists=((1, "Nirvana"),), label=(895, "DGC", "DGCD-24425"), master=13814,
            have=100, want=50, tracks=(("A1", "Smells Like Teen Spirit", "5:01"),)):
    return {
        "id": release_id, "title": "Nevermind", "year": 1991, "country": "US", "released": "1991-09-24",
        "master_id": master, "date_changed": "2024-05-01T10:00:00-07:00",
        "genres": ["Rock"], "styles": ["Grunge", "Alternative Rock"],
        "formats": [{"name": "Vinyl", "qty": "1"}],
        "labels": [{"id": label[0], "name": label[1], "catno": label[2]}],
        "artists": [{"id": a, "name": n, "anv": "", "join": "", "role": ""} for a, n in artists],
        "tracklist": [{"position": "", "type_": "heading", "title": "Side A", "duration": ""}]
        + [{"position": p, "type_": "track", "title": t, "duration": d} for p, t, d in tracks],
        "community": {"have": have, "want": want, "rating": {"average": 4.5, "count": 10}},
    }


class FakeClient:
    def __init__(self, routes=None, pages=None, fail=()):
        self.routes = routes or {}
        self.pages = pages or {}
        self.fail = set(fail)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        if path in self.fail:
            raise DiscogsError(f"falha simulada em {path}")
        return self.routes.get(path)

    def paginate(self, path, key, params=None, max_pages=None):
        self.calls.append(path)
        yield from self.pages.get(path, [])


def seed_bronze_day(lake, ds, *, have, first_day):
    """One day of synthetic bronze: 2 releases (one without a master and with a placeholder label), stats,
    new entities only on the first day, collection (one copy leaves on the second day) and wantlist."""
    from discogs_pipeline.storage import write_bronze
    from discogs_pipeline.tracking import TrackedReleases

    write_bronze(lake, "releases", ds, [
        {"id": 1, "data": release(1, have=have, artists=((1, "Nirvana"), (2, "Guest")),
                                  tracks=(("A1", "Teen Spirit", "5:01"), ("A2", "In Bloom", "1:04:15"),
                                          ("B1", "Untitled", "")))},
        {"id": 2, "data": release(2, master=None, label=(0, "Not On Label", "none"))},
    ])
    write_bronze(lake, "marketplace_stats", ds, [
        {"id": 1, "data": {"lowest_price": {"value": 12.34, "currency": "USD"}, "num_for_sale": 7,
                           "blocked_from_sale": False}},
        {"id": 2, "data": {"lowest_price": None, "num_for_sale": None, "blocked_from_sale": False}},
    ])
    write_bronze(lake, "artists", ds, [{"id": 1, "data": {"id": 1, "name": "Nirvana"}}] if first_day else [])
    write_bronze(lake, "labels", ds, [{"id": 895, "data": {"id": 895, "name": "DGC",
                                                           "parent_label": {"id": 1, "name": "UMG"}}}]
                 if first_day else [])
    write_bronze(lake, "masters", ds, [{"id": 13814, "data": {"id": 13814, "title": "Nevermind", "year": 1991,
                                                              "main_release": 1}}] if first_day else [])
    collection = [{"username": "vitor", "data": {"id": 1, "instance_id": 11, "folder_id": 1, "rating": 0,
                                                 "date_added": "2020-01-02T03:04:05-08:00"}}]
    if first_day:
        collection.append({"username": "vitor", "data": {"id": 2, "instance_id": 12, "folder_id": 1, "rating": 5,
                                                         "date_added": "2020-01-02T03:04:05-08:00"}})
    write_bronze(lake, "collection", ds, collection)
    write_bronze(lake, "wantlist", ds, [{"username": "vitor", "data": {"id": 2, "rating": 0,
                                                                       "date_added": "2021-01-01T00:00:00-00:00"}}])
    tracked = TrackedReleases(lake)
    tracked.add(1, "discovery:1991", ds)
    tracked.add(2, "collection:vitor", ds)
    tracked.save()
