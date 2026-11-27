"""Dublês da API do Discogs com payloads no formato documentado."""

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
