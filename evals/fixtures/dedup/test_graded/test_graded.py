from src.dedup import dedup


def test_preserves_first_occurrence_order() -> None:
    assert dedup(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


def test_does_not_mutate_input() -> None:
    items = [1, 2, 1]
    dedup(items)
    assert items == [1, 2, 1]


def test_empty_returns_empty_list() -> None:
    assert dedup([]) == []


def test_unhashable_raises_type_error() -> None:
    try:
        dedup([[1], [2]])
    except TypeError:
        return
    raise AssertionError("dedup of unhashable items did not raise TypeError")
