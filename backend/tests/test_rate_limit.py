import threading

from app.core.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_requests_within_the_limit_are_allowed() -> None:
    limiter = RateLimiter(3, clock=Clock())

    assert [limiter.retry_after("a") for _ in range(3)] == [None, None, None]


def test_the_request_over_the_limit_is_refused_with_a_wait() -> None:
    clock = Clock()
    limiter = RateLimiter(2, clock=clock)
    limiter.retry_after("a")
    clock.now += 10
    limiter.retry_after("a")

    wait = limiter.retry_after("a")

    assert wait is not None
    assert 49 <= wait <= 51  # the first request leaves the window 50 seconds from now


def test_a_refused_request_does_not_extend_the_wait() -> None:
    clock = Clock()
    limiter = RateLimiter(1, clock=clock)
    limiter.retry_after("a")
    clock.now += 30
    limiter.retry_after("a")  # refused
    clock.now += 31  # 61 seconds after the only request that counted

    assert limiter.retry_after("a") is None


def test_the_window_slides() -> None:
    clock = Clock()
    limiter = RateLimiter(2, clock=clock)
    limiter.retry_after("a")
    clock.now += 40
    limiter.retry_after("a")
    clock.now += 21  # the first is now 61 seconds old, the second 21

    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") is not None


def test_each_client_has_its_own_allowance() -> None:
    limiter = RateLimiter(1, clock=Clock())

    assert limiter.retry_after("a") is None
    assert limiter.retry_after("b") is None
    assert limiter.retry_after("a") is not None


def test_zero_switches_the_limit_off() -> None:
    limiter = RateLimiter(0, clock=Clock())

    assert all(limiter.retry_after("a") is None for _ in range(1000))


def test_clients_that_have_gone_quiet_are_forgotten() -> None:
    clock = Clock()
    limiter = RateLimiter(5, clock=clock)
    for number in range(5_100):
        limiter.retry_after(f"client-{number}")
    clock.now += 61

    limiter.retry_after("late-arrival")

    assert len(limiter._seen) < 5_100


def test_concurrent_requests_never_exceed_the_limit() -> None:
    limiter = RateLimiter(50, clock=Clock())
    allowed: list[int] = []

    def worker() -> None:
        for _ in range(20):
            if limiter.retry_after("a") is None:
                allowed.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(allowed) == 50
