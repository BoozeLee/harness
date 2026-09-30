from src.wordcount import counts, words


def test_words_splits_on_any_whitespace() -> None:
    assert words(" a  b\tc\n") == ["a", "b", "c"]


def test_counts_tallies_occurrences() -> None:
    assert counts("a b a") == {"a": 2, "b": 1}


def test_empty_and_whitespace_only() -> None:
    assert words("") == []
    assert words("   ") == []
    assert counts("") == {}


def test_non_str_raises_type_error() -> None:
    for bad in (None, 7, ["a"]):
        try:
            words(bad)
        except TypeError:
            continue
        raise AssertionError(f"words({bad!r}) did not raise TypeError")
