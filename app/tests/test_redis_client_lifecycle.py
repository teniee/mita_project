"""A Redis client must never outlive the event loop that created it.

app.core.security caches one redis.asyncio client in a module global. Those
clients bind their connections to the loop that opened them, so a cached client
that survives into another loop is unusable there - and worse, when it is
finally garbage-collected, AbstractConnection.__del__ calls writer.close() ->
loop.call_soon() on the dead loop and raises

    RuntimeError: Event loop is closed

as an *unraisable* exception, at whatever unrelated point the collector happens
to run. That surfaced as an intermittent failure of an unrelated test
(test_challenge_endpoints) in one full-suite run while passing in isolation.

These tests pin the lifecycle rather than the symptom: no sleeps, no retries,
no suppression.
"""

import asyncio
import gc
import sys

import pytest

from app.core import security

REDIS_URL_SET = bool(security.os.environ.get("REDIS_URL"))


def _run_in_fresh_loop(coro_fn):
    """Imitate pytest-asyncio: one loop per test, closed afterwards."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_fn()), loop
    finally:
        asyncio.set_event_loop(None)


def _armed_connections(client) -> int:
    """Connections still holding a stream writer, i.e. with a live __del__.

    AbstractConnection.__del__ only acts when _writer is set; that is what
    reaches into the (possibly dead) event loop. Zero means nothing can fire.
    """
    pool = getattr(client, "connection_pool", None)
    if pool is None:
        return 0
    conns = list(getattr(pool, "_available_connections", None) or [])
    conns += list(getattr(pool, "_in_use_connections", None) or [])
    return sum(1 for c in conns if getattr(c, "_writer", None) is not None)


class _CaptureUnraisable:
    """Collect exceptions escaping __del__, which never reach pytest normally."""

    def __enter__(self):
        self.seen = []
        self._prev = sys.unraisablehook
        sys.unraisablehook = lambda a: self.seen.append(
            f"{a.exc_type.__name__}: {a.exc_value}"
        )
        return self

    def __exit__(self, *exc):
        gc.collect()
        gc.collect()
        sys.unraisablehook = self._prev
        return False

    @property
    def event_loop_errors(self):
        return [s for s in self.seen if "Event loop is closed" in s]


@pytest.fixture(autouse=True)
def _clean_global():
    security.redis_client = None
    security._redis_client_loop = None
    security._redis_client_owned = False
    yield
    security.redis_client = None
    security._redis_client_loop = None
    security._redis_client_owned = False


class TestCacheIsLoopAware:
    def test_a_client_cached_on_a_closed_loop_is_not_handed_out_again(self):
        """The core defect: the global survived its loop and was reused.

        Also the regression guard for the dead-loop branch of
        close_redis_client(). Evicting the stale client must DEFUSE it, not
        merely drop the reference: dropping alone leaves
        AbstractConnection.__del__ armed to call transport.close() on the dead
        loop at some arbitrary later moment, which is the intermittent failure
        this whole file exists for. The unraisable capture below is what makes
        that observable - such errors never reach a normal assertion.
        """

        async def make():
            return await security.get_redis_client()

        first, loop_a = _run_in_fresh_loop(make)
        if first is None:
            pytest.skip("no Redis configured in this environment")
        assert security._redis_client_loop is loop_a
        loop_a.close()

        # get_redis_client() must notice the loop changed and evict.
        second, loop_b = _run_in_fresh_loop(make)
        try:
            assert (
                second is not first
            ), "a client bound to a closed loop must never be returned again"
            assert security._redis_client_loop is loop_b
        finally:
            loop_b.run_until_complete(security.close_redis_client())
            loop_b.close()

        # The evicted client must be DEFUSED, not merely dereferenced. A
        # connection that still holds a _writer has an armed
        # AbstractConnection.__del__ pointed at loop_a, which fires whenever
        # the collector next runs - the intermittent failure this file exists
        # for. Asserting the state is deterministic; asserting on GC timing is
        # not, which is exactly why the bug was so hard to pin down.
        assert (
            _armed_connections(first) == 0
        ), "evicting a client bound to a closed loop left its finaliser armed"

    def test_same_loop_reuses_the_cached_client(self):
        async def twice():
            a = await security.get_redis_client()
            b = await security.get_redis_client()
            return a, b

        (a, b), loop = _run_in_fresh_loop(twice)
        try:
            if a is None:
                pytest.skip("no Redis configured in this environment")
            assert a is b, "caching within one loop must still work"
        finally:
            loop.run_until_complete(security.close_redis_client())
            loop.close()


class TestNoExceptionEscapesFinalisation:
    @pytest.mark.skipif(not REDIS_URL_SET, reason="needs REDIS_URL")
    def test_dropping_a_client_after_its_loop_closed_raises_nothing(self):
        """Reproduces the observed failure, and asserts it no longer happens.

        Without close_redis_client() this leaves an open connection whose
        __del__ fires on the dead loop; the captured unraisable list then
        contains 'RuntimeError: Event loop is closed'.
        """

        async def make():
            return await security.get_redis_client()

        client, loop = _run_in_fresh_loop(make)
        if client is None:
            pytest.skip("no Redis configured in this environment")

        loop.run_until_complete(security.close_redis_client())
        loop.close()

        with _CaptureUnraisable() as cap:
            client = None
            security.redis_client = None
        assert (
            cap.event_loop_errors == []
        ), f"finalisation touched a dead event loop: {cap.event_loop_errors}"

    @pytest.mark.skipif(not REDIS_URL_SET, reason="needs REDIS_URL")
    def test_a_failed_ping_does_not_leave_an_unclosed_client(self):
        """from_url() allocates the pool BEFORE ping, so the error path must
        close it. Previously the global was set to None and the object was left
        to __del__."""

        async def make():
            real_wait_for = asyncio.wait_for

            async def boom(awaitable, timeout):
                # let the client open its connection, then fail like a timeout
                await real_wait_for(awaitable, timeout)
                raise asyncio.TimeoutError

            security.asyncio.wait_for = boom
            try:
                return await security.get_redis_client()
            finally:
                security.asyncio.wait_for = real_wait_for

        with _CaptureUnraisable() as cap:
            result, loop = _run_in_fresh_loop(make)
            loop.close()
        assert result is None, "a failed ping must yield the in-memory fallback"
        assert security.redis_client is None
        assert (
            cap.event_loop_errors == []
        ), f"the failure path leaked a live connection: {cap.event_loop_errors}"


class TestCloseRedisClient:
    def test_is_idempotent_and_safe_with_nothing_cached(self):
        async def close_twice():
            await security.close_redis_client()
            await security.close_redis_client()

        _, loop = _run_in_fresh_loop(close_twice)
        loop.close()
        assert security.redis_client is None

    def test_does_not_close_a_client_it_does_not_own(self):
        """get_redis_client() may return the client owned by limiter_setup via
        app.state; closing that would break rate limiting for its real owner."""

        class _Sentinel:
            closed = False

            async def aclose(self):
                type(self).closed = True

        async def scenario():
            security.redis_client = _Sentinel()
            security._redis_client_loop = asyncio.get_running_loop()
            security._redis_client_owned = False
            await security.close_redis_client()

        _, loop = _run_in_fresh_loop(scenario)
        loop.close()
        assert _Sentinel.closed is False
        assert security.redis_client is None, "the reference is still dropped"
