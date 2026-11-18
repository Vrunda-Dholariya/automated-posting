import asyncio

from app.platforms.base import Platform, PlatformError
from app.services.posting_service import post_everywhere


class Fake(Platform):
    def __init__(self, name, delay=0.0, error=None, tracker=None):
        self.name = name
        self.delay = delay
        self.error = error
        self.tracker = tracker

    def is_configured(self):
        return True

    async def _send(self, client, message):
        if self.tracker is not None:
            self.tracker["now"] += 1
            self.tracker["peak"] = max(self.tracker["peak"], self.tracker["now"])
        try:
            await asyncio.sleep(self.delay)
            if self.error:
                raise PlatformError(self.error)
            return f"https://example.com/{self.name}"
        finally:
            if self.tracker is not None:
                self.tracker["now"] -= 1

    async def _is_public(self, client, url):
        return True


class Exploding(Fake):
    """Breaks the 'publish never raises' promise, to test the second safety net."""

    async def publish(self, client, message):
        raise RuntimeError("bug in publish")


def run(platforms):
    return asyncio.run(post_everywhere("hello https://example.com", platforms))


def test_platforms_really_run_at_the_same_time():
    tracker = {"now": 0, "peak": 0}
    platforms = [Fake(f"P{i}", delay=0.05, tracker=tracker) for i in range(5)]

    response = run(platforms)

    assert response.success is True
    assert all(r.status == "success" for r in response.results)
    assert tracker["peak"] == 5  # one after another would give a peak of 1


def test_one_failure_does_not_stop_the_others():
    response = run([Fake("A"), Fake("B", error="Authentication failed"), Fake("C")])
    statuses = {r.platform: r.status for r in response.results}

    assert statuses == {"A": "success", "B": "failed", "C": "success"}
    assert response.success is True
    assert response.results[1].error == "Authentication failed"


def test_success_is_false_when_everything_fails():
    response = run([Fake("A", error="boom"), Fake("B", error="boom")])
    assert response.success is False
    assert len(response.results) == 2


def test_results_keep_the_platform_order():
    response = run([Fake("slow", delay=0.2), Fake("fast", delay=0.0)])
    assert [r.platform for r in response.results] == ["slow", "fast"]


def test_a_bug_escaping_publish_is_contained():
    response = run([Fake("A"), Exploding("B"), Fake("C")])
    statuses = {r.platform: r.status for r in response.results}

    assert statuses == {"A": "success", "B": "failed", "C": "success"}
    assert response.results[1].error == "Unexpected internal error"