import pytest

from discogs_pipeline.api import DiscogsClient, DiscogsError


class Resp:
    def __init__(self, status, body=None, remaining="50"):
        self.status_code = status
        self._body = body or {}
        self.headers = {"X-Discogs-Ratelimit-Remaining": remaining}
        self.text = str(body)

    def json(self):
        return self._body


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.urls = []

    def get(self, url, params=None, timeout=None):
        self.urls.append((url, params))
        return self.responses.pop(0)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def make(responses):
    clock = Clock()
    session = Session(responses)
    client = DiscogsClient("tok", "Test/1.0", session=session, sleep=clock.sleep, clock=clock.time)
    return client, session, clock


def test_requires_token():
    with pytest.raises(DiscogsError):
        DiscogsClient("", "Test/1.0")


def test_sets_auth_and_user_agent():
    client, session, _ = make([])
    assert session.headers["Authorization"] == "Discogs token=tok"
    assert session.headers["User-Agent"] == "Test/1.0"


def test_404_returns_none():
    client, _, _ = make([Resp(404)])
    assert client.get("/releases/1") is None


def test_retries_429_after_waiting_a_minute():
    client, session, clock = make([Resp(429), Resp(200, {"id": 1})])
    assert client.get("/releases/1") == {"id": 1}
    assert 60 in clock.sleeps
    assert len(session.urls) == 2


def test_gives_up_after_max_retries():
    client, _, _ = make([Resp(503)] * 5)
    with pytest.raises(DiscogsError):
        client.get("/releases/1")


def test_client_error_is_not_retried():
    client, session, _ = make([Resp(401, {"message": "no"})])
    with pytest.raises(DiscogsError):
        client.get("/releases/1")
    assert len(session.urls) == 1


def test_throttles_to_one_request_per_interval():
    client, _, clock = make([Resp(200), Resp(200), Resp(200)])
    for _ in range(3):
        client.get("/x")
    assert clock.now >= 2 * 1.05


def test_paginate_follows_pages_and_respects_max_pages():
    pages = [Resp(200, {"pagination": {"pages": 3}, "results": [{"id": i}]}) for i in range(3)]
    client, session, _ = make(pages)
    assert [r["id"] for r in client.paginate("/database/search", "results")] == [0, 1, 2]
    assert [p["page"] for _, p in session.urls] == [1, 2, 3]

    client, _, _ = make([Resp(200, {"pagination": {"pages": 9}, "results": [{"id": 0}]})])
    assert len(list(client.paginate("/database/search", "results", max_pages=1))) == 1
