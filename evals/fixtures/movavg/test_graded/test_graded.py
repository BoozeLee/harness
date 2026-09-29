from src.movavg import MovingAverage


def test_push_returns_window_mean() -> None:
    m = MovingAverage(2)
    assert m.push(1) == 1
    assert m.push(2) == 1.5
    assert m.push(3) == 2.5


def test_window_never_exceeds_n() -> None:
    m = MovingAverage(2)
    for x in (1, 2, 3, 4):
        m.push(x)
    assert m.push(10) == 7


def test_bad_window_raises_value_error() -> None:
    for n in (0, -1):
        try:
            MovingAverage(n)
        except ValueError:
            continue
        raise AssertionError(f"MovingAverage({n}) did not raise ValueError")
