"""The rubric is configuration, and the screening layer must own no thresholds."""

from __future__ import annotations

import json
from dataclasses import fields

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import (
    CONVENTION,
    DEFAULT_RUBRIC,
    NON_THRESHOLD_FIELDS,
    SOURCED,
    THRESHOLD_PROVENANCE,
    PrimerRubric,
)


@pytest.mark.unit
def test_every_threshold_declares_its_provenance():
    """A new threshold cannot be added without saying where it came from.

    The distinction is not cosmetic: a convention dressed up as a published
    result would misrepresent the standard a student is being marked against.
    """
    declared = set(THRESHOLD_PROVENANCE)
    actual = {f.name for f in fields(PrimerRubric)} - set(NON_THRESHOLD_FIELDS)
    assert actual - declared == set(), f"undeclared provenance: {sorted(actual - declared)}"
    assert declared - actual == set(), f"provenance for unknown fields: {sorted(declared - actual)}"


@pytest.mark.unit
def test_provenance_values_are_valid_and_explained():
    for name, (kind, explanation) in THRESHOLD_PROVENANCE.items():
        assert kind in (CONVENTION, SOURCED), f"{name}: unknown provenance {kind!r}"
        assert explanation.strip(), f"{name}: provenance needs an explanation"


@pytest.mark.unit
def test_the_gc_window_is_labelled_a_convention():
    """40-60% GC is practice, not a finding, and must never claim otherwise."""
    for field_name in ("gc_min_percent", "gc_max_percent"):
        kind, explanation = THRESHOLD_PROVENANCE[field_name]
        assert kind == CONVENTION
        assert "not a measured result" in explanation


@pytest.mark.unit
def test_defaults_are_self_consistent():
    assert DEFAULT_RUBRIC.validate() == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"gc_min_percent": 70.0, "gc_max_percent": 30.0}, "gc_min_percent is above"),
        ({"clamp_min_gc": 4, "clamp_max_gc": 1}, "clamp_min_gc is above"),
        ({"clamp_window": 0}, "clamp_window must be at least 1"),
        ({"clamp_window": 2, "clamp_max_gc": 5}, "exceeds clamp_window"),
        ({"min_length": 40, "max_length": 20}, "min_length is above"),
        ({"product_min_bp": 500, "product_max_bp": 100}, "product_min_bp is above"),
        ({"max_offset": -1}, "max_offset cannot be negative"),
        ({"max_poly_run": 0}, "max_poly_run must be at least 1"),
        ({"hairpin_min_dg": 2.0}, "should be a negative free energy"),
    ],
)
def test_validate_catches_inconsistent_rubrics(overrides, expected_fragment):
    problems = PrimerRubric(**overrides).validate()
    assert any(expected_fragment in p for p in problems), problems


@pytest.mark.unit
def test_round_trips_through_json(tmp_path):
    rubric = PrimerRubric(name="BIOL341", gc_min_percent=45.0, max_offset=3)
    path = tmp_path / "rubric.json"
    path.write_text(json.dumps(rubric.to_dict()), encoding="utf-8")

    loaded = PrimerRubric.from_json(path)
    assert loaded == rubric


@pytest.mark.unit
def test_unknown_keys_are_ignored_rather_than_fatal():
    """A rubric written for a later version still loads, minus what is new."""
    loaded = PrimerRubric.from_dict({"gc_min_percent": 35.0, "a_future_threshold": 1})
    assert loaded.gc_min_percent == 35.0
    assert loaded.gc_max_percent == PrimerRubric().gc_max_percent


@pytest.mark.unit
def test_from_dict_of_nothing_gives_the_default():
    assert PrimerRubric.from_dict(None) == PrimerRubric()
    assert PrimerRubric.from_dict({}) == PrimerRubric()


@pytest.mark.unit
def test_rubric_is_immutable():
    """Screening must not be able to edit the standard it is judging against."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        DEFAULT_RUBRIC.gc_min_percent = 10.0  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("overrides", "sequence", "check_name"),
    [
        # Each pair of rubrics differs only in the threshold under test, and
        # the same sequence must pass one and fail the other. A threshold that
        # was hardcoded at the call site could not produce both answers.
        ({"gc_min_percent": 0.0, "gc_max_percent": 100.0}, "ATATATATATATATATAT", "gc_content"),
        ({"clamp_min_gc": 0, "clamp_max_gc": 5}, "ATATATATATATATATAT", "three_prime_clamp"),
        ({"max_poly_run": 20}, "AAAAAAAAAACGTACGTACG", "poly_run"),
    ],
)
def test_thresholds_are_read_from_the_rubric_not_hardcoded(overrides, sequence, check_name):
    """Loosening a threshold must flip that check from fail to pass.

    Behavioural rather than a source grep: this is the property that actually
    matters — a course supplying its own rubric genuinely changes the verdict.
    """
    from karcytics_plugins.synthetic_biology.analysis.assembly.primer_screen import screen_primer

    def verdict(rubric: PrimerRubric) -> bool | None:
        checks = {c.name: c for c in screen_primer(sequence, "", rubric)}
        return checks[check_name].passed

    assert verdict(PrimerRubric()) is False, "fixture should fail under the default rubric"
    assert verdict(PrimerRubric(**overrides)) is True, (
        f"{check_name} ignored the rubric override {overrides}"
    )
