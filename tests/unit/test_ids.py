from __future__ import annotations

import re
import time
import uuid

import pytest

from bikematch.ids import (
    is_case_alias,
    is_check_alias,
    new_case_alias,
    new_check_alias,
    new_id,
    uuid7,
)


def test_uuid7_has_correct_version_and_variant():
    for _ in range(200):
        u = uuid7()
        assert u.version == 7
        assert (u.int >> 62) & 0b11 == 0b10, "RFC 9562 variant bits"


def test_uuid7_timestamps_are_non_decreasing():
    ids = [uuid7() for _ in range(500)]
    timestamps = [u.int >> 80 for u in ids]
    assert timestamps == sorted(timestamps)


def test_uuid7_sorts_lexicographically_across_milliseconds():
    """UUIDv7 orders by time only between distinct milliseconds.

    Within a single millisecond the random bits decide, so ordering is
    guaranteed across a time gap, not within a tight generation loop. This is
    the property the database actually relies on.
    """
    batches = []
    for _ in range(5):
        batches.append(uuid7())
        time.sleep(0.002)
    assert [str(u) for u in batches] == sorted(str(u) for u in batches)


def test_uuid7_is_unique_and_parses_back():
    ids = {new_id() for _ in range(2000)}
    assert len(ids) == 2000
    for value in list(ids)[:20]:
        assert uuid.UUID(value).version == 7


def test_case_alias_shape_and_roundtrip():
    alias = new_case_alias(2026)
    assert re.fullmatch(r"EDB-2026-[0-9A-HJ-KM-NP-TV-Z]{6}", alias), alias
    assert is_case_alias(alias)
    assert not is_check_alias(alias)


def test_check_alias_is_distinct_namespace():
    alias = new_check_alias(2026)
    assert alias.startswith("CHK-2026-")
    assert is_check_alias(alias)
    assert not is_case_alias(alias)


def test_alias_alphabet_excludes_ambiguous_characters():
    bodies = "".join(new_case_alias().split("-")[2] for _ in range(500))
    assert not (set(bodies) & set("ILOU")), "ambiguous characters must not appear"


def test_alias_validation_is_lenient_about_whitespace_and_case():
    assert is_case_alias("  edb-2026-8f3k2q  ")


def test_alias_validation_rejects_malformed():
    for bad in [
        "",
        "EDB-2026",
        "EDB-2026-8F3K2",  # too short
        "EDB-2026-8F3K2QQ",  # too long
        "EDB-26-8F3K2Q",  # short year
        "EDB-YEAR-8F3K2Q",
        "CHK-2026-8F3K2Q",  # wrong namespace
        "EDB-2026-8F3K2I",  # excluded character
        "EDB-2026-8F3-K2Q",  # extra separator
    ]:
        assert not is_case_alias(bad), bad



def test_generated_aliases_have_canonical_four_digit_years():
    for generate, validate in (
        (new_case_alias, is_case_alias),
        (new_check_alias, is_check_alias),
    ):
        assert validate(generate())
        assert validate(generate(2026))
        for invalid_year in (-1, 0, 999, 10000, True, "2026", 2026.0):
            with pytest.raises(ValueError, match="four-digit calendar year"):
                generate(invalid_year)


def test_alias_validation_rejects_non_ascii_digits_and_impossible_years():
    for validate, prefix in (
        (is_case_alias, "EDB"),
        (is_check_alias, "CHK"),
    ):
        for noncanonical in (
            f"{prefix}-٢٠٢٦-8F3K2Q",  # Arabic-Indic numeral sequence
            f"{prefix}-\uFF12\uFF10\uFF12\uFF16-8F3K2Q",  # full-width Unicode numerals
            f"{prefix}-0000-8F3K2Q",  # cannot be generated
            f"{prefix}-0999-8F3K2Q",
        ):
            assert not validate(noncanonical), noncanonical


@pytest.mark.parametrize(
    ("unicode_body", "folds_to"),
    [
        ("8F3\u017f2Q", "8F3S2Q"),  # long s -> ASCII S under .upper()
        ("8F3\ufb05Q", "8F3STQ"),  # two-letter ST ligature expansion
    ],
)
def test_unicode_case_expansions_cannot_match_ascii_aliases(unicode_body, folds_to):
    # The *old* parser uppercased first, turning these untrusted strings
    # into accepted six-character ASCII aliases. That risks attaching an
    # emailed response to a different, legitimate case or check.
    assert unicode_body.upper() == folds_to
    for prefix, validate in (("EDB", is_case_alias), ("CHK", is_check_alias)):
        assert validate(f"{prefix}-2026-{folds_to}")
        assert not validate(f"{prefix}-2026-{unicode_body}")


@pytest.mark.parametrize(
    "alias",
    [
        "EDB-2026-8F3\u017f2Q",
        "EDB-2026-8F3\ufb05Q",
        "EDB-2026-8F3K2Q\u00a0",  # non-ASCII space must not bypass validation
        "\u00a0EDB-2026-8F3K2Q",
        "EDB-2026-\uff18F3K2Q",  # full-width digit
        "CHK-2026-8F3\u017f2Q",
        "CHK-2026-8F3\ufb05Q",
    ],
)
def test_non_ascii_alias_text_rejected_before_normalization(alias):
    assert not is_case_alias(alias)
    assert not is_check_alias(alias)


def test_untrusted_non_string_case_identifiers_fail_closed():
    for check in (is_case_alias, is_check_alias):
        for malformed in (None, 2026, True, b"EDB-2026-8F3K2Q", [], {}):
            assert not check(malformed)
