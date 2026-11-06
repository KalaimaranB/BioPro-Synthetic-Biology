"""The gel migration model: ordering, co-migration, intensity and honesty.

The model is log-linear in fragment size, which is a *convention* — Southern
(1979) showed mobility is not strictly linear in log(size). These tests pin the
properties a renderer and a student depend on, and pin the labelling so the
approximation cannot be presented as a published result.
"""

from __future__ import annotations

import math

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly import gel
from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst

from .sequence_fixtures import DIGEST_TEMPLATE

# ── The model ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_bigger_fragments_migrate_less():
    """Monotonic: a larger fragment is always closer to the well."""
    sizes = [200, 500, 1000, 2000, 5000]
    mobilities = [gel.relative_mobility(s) for s in sizes]
    assert mobilities == sorted(mobilities, reverse=True)
    assert all(0.0 <= m <= 1.0 for m in mobilities)


@pytest.mark.unit
def test_mobility_is_linear_in_log_size():
    """The stated model, pinned: equal size ratios give equal spacing."""
    a = gel.relative_mobility(1000)
    b = gel.relative_mobility(2000)
    c = gel.relative_mobility(4000)
    assert (a - b) == pytest.approx(b - c)


@pytest.mark.unit
def test_mobility_matches_the_documented_equation():
    size, lo, hi = 1500, 100, 10_000
    expected = (math.log10(hi) - math.log10(size)) / (math.log10(hi) - math.log10(lo))
    assert gel.relative_mobility(size, min_bp=lo, max_bp=hi) == pytest.approx(expected)


@pytest.mark.unit
def test_the_window_edges_pin_to_the_well_and_the_gel_end():
    assert gel.relative_mobility(10_000) == 0.0
    assert gel.relative_mobility(100) == 1.0


@pytest.mark.unit
def test_fragments_outside_the_window_are_clamped_and_marked():
    """A clamped position is not a measurement and must say so."""
    lane = gel.digest_lane([50, 50_000, 1000])
    by_size = {b.size_bp: b for b in lane.bands}

    assert by_size[50_000].relative_mobility == 0.0
    assert by_size[50_000].out_of_range is True
    assert by_size[50].relative_mobility == 1.0
    assert by_size[50].out_of_range is True
    assert by_size[1000].out_of_range is False


@pytest.mark.unit
def test_a_gel_with_clamped_bands_carries_a_warning():
    built = gel.build_gel([gel.digest_lane([50_000])], ladder=None)
    assert any("resolving window" in n for n in built.notes)


@pytest.mark.unit
def test_a_different_window_moves_the_same_fragment():
    """Agarose percentage changes the window, so position is gel-relative."""
    wide = gel.relative_mobility(1000, min_bp=100, max_bp=10_000)
    narrow = gel.relative_mobility(1000, min_bp=100, max_bp=2000)
    assert wide != narrow


@pytest.mark.unit
@pytest.mark.parametrize("bad", [0, -1, -500])
def test_a_non_positive_size_is_rejected(bad):
    with pytest.raises(ValueError, match="must be positive"):
        gel.relative_mobility(bad)


@pytest.mark.unit
@pytest.mark.parametrize(("lo", "hi"), [(0, 100), (500, 500), (1000, 100)])
def test_an_invalid_window_is_rejected(lo, hi):
    with pytest.raises(ValueError, match="resolving window"):
        gel.relative_mobility(500, min_bp=lo, max_bp=hi)


@pytest.mark.unit
def test_distance_scales_with_lane_length():
    short = gel.product_lane(1000, lane_length_mm=50).bands[0]
    long = gel.product_lane(1000, lane_length_mm=100).bands[0]
    assert long.distance_mm == pytest.approx(2 * short.distance_mm)
    assert long.relative_mobility == pytest.approx(short.relative_mobility)


# ── Ladders ────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(gel.LADDERS))
def test_every_ladder_is_ordered_and_migrates_monotonically(name):
    lane = gel.ladder_lane(name)
    sizes = [b.size_bp for b in lane.bands]
    assert sizes == sorted(sizes, reverse=True), "bands must be largest first"

    mobilities = [b.relative_mobility for b in lane.bands]
    assert mobilities == sorted(mobilities), "mobility must increase as size falls"


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(gel.LADDERS))
def test_ladder_sizes_are_unique_and_positive(name):
    sizes = gel.LADDERS[name].sizes
    assert len(sizes) == len(set(sizes))
    assert all(s > 0 for s in sizes)


@pytest.mark.unit
def test_a_reference_band_is_brighter_than_its_neighbours():
    """Suppliers overload one band as an orientation marker."""
    ladder = gel.LADDERS["1kb_plus"]
    lane = gel.ladder_lane("1kb_plus")
    marker = next(b for b in lane.bands if b.size_bp in ladder.reference_bands)
    neighbour = next(b for b in lane.bands if b.size_bp == 2000)
    assert marker.intensity > neighbour.intensity


@pytest.mark.unit
def test_the_ladder_lane_is_labelled_as_a_ladder():
    lane = gel.ladder_lane("1kb")
    assert lane.kind == "ladder"
    assert lane.name == gel.LADDERS["1kb"].name


@pytest.mark.unit
def test_ladder_sizes_are_sourced_not_convention():
    """A supplier's fragment list is a fact about a product."""
    kind, _ = gel.THRESHOLD_PROVENANCE["ladder_sizes"]
    assert kind == "sourced"


# ── Co-migration ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_two_fragments_of_equal_size_co_migrate_as_one_band():
    """A gel cannot resolve equal lengths, so one band, not two."""
    lane = gel.digest_lane([1000, 1000, 500])
    assert len(lane.bands) == 2
    assert sorted(b.size_bp for b in lane.bands) == [500, 1000]


@pytest.mark.unit
def test_a_co_migrating_band_is_brighter_and_says_how_many():
    lane = gel.digest_lane([1000, 1000])
    band = lane.bands[0]
    assert "x2" in band.label
    assert any("co-migrate" in n for n in lane.notes)


@pytest.mark.unit
def test_co_migration_doubles_the_mass_not_the_band_count():
    single = gel.digest_lane([1000, 300])
    doubled = gel.digest_lane([1000, 1000, 300])

    one = next(b for b in single.bands if b.size_bp == 300)
    two = next(b for b in doubled.bands if b.size_bp == 300)
    # The 1000 bp band carries twice the mass, so the 300 bp band is relatively
    # dimmer against it.
    assert two.intensity < one.intensity


# ── Intensity ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_intensity_follows_mass_not_molar_count():
    """Intercalating dye binds along the duplex: a 3 kb band outshines a 1 kb one."""
    lane = gel.digest_lane([3000, 1000])
    big = next(b for b in lane.bands if b.size_bp == 3000)
    small = next(b for b in lane.bands if b.size_bp == 1000)

    assert big.intensity == pytest.approx(1.0)
    assert small.intensity == pytest.approx(1 / 3, rel=1e-6)


@pytest.mark.unit
def test_intensity_is_normalised_to_the_brightest_band():
    lane = gel.digest_lane([800, 400, 200])
    assert max(b.intensity for b in lane.bands) == pytest.approx(1.0)
    assert all(0 < b.intensity <= 1.0 for b in lane.bands)


# ── The two cases it has to serve ──────────────────────────────────────


@pytest.mark.unit
def test_a_pcr_product_lane_has_exactly_one_band():
    lane = gel.product_lane(1234, name="PCR product")
    assert lane.kind == "pcr_product"
    assert len(lane.bands) == 1
    assert lane.bands[0].size_bp == 1234


@pytest.mark.unit
def test_a_digest_lane_takes_a_digest_result_directly():
    """No translation layer between engine 1 and engine 3."""
    digest = rst.double_digest(DIGEST_TEMPLATE, "EcoRI", "HindIII")
    lane = gel.digest_lane(digest, name="EcoRI + HindIII")

    assert lane.kind == "digest"
    assert sorted(lane.sizes) == sorted(set(digest.fragment_lengths))


@pytest.mark.unit
def test_a_digest_lane_also_takes_plain_lengths():
    assert gel.digest_lane([500, 1500]).sizes == (1500, 500)


@pytest.mark.unit
def test_a_gel_puts_the_ladder_first():
    built = gel.build_gel([gel.product_lane(900)], ladder="1kb")
    assert built.lanes[0].kind == "ladder"
    assert built.lanes[1].kind == "pcr_product"


@pytest.mark.unit
def test_a_gel_can_be_built_without_a_ladder():
    built = gel.build_gel([gel.product_lane(900)], ladder=None)
    assert [lane.kind for lane in built.lanes] == ["pcr_product"]


@pytest.mark.unit
def test_a_product_and_a_digest_share_one_window():
    """Both lanes must be comparable, so the window is the gel's, not the lane's."""
    digest = rst.double_digest(DIGEST_TEMPLATE, "EcoRI", "HindIII")
    built = gel.build_gel([gel.product_lane(1200), gel.digest_lane(digest)], min_bp=50, max_bp=5000)
    assert built.min_bp == 50
    assert built.max_bp == 5000
    for lane in built.lanes:
        assert lane.min_bp == 50
        assert lane.max_bp == 5000


# ── Honesty about the model ────────────────────────────────────────────


@pytest.mark.unit
def test_the_mobility_model_is_labelled_a_convention():
    """Southern (1979) is cited for size dependence, not for this equation."""
    kind, explanation = gel.THRESHOLD_PROVENANCE["mobility_model"]
    assert kind == "convention"
    assert "not strictly log-linear" in explanation


@pytest.mark.unit
def test_the_resolving_window_is_labelled_a_convention():
    kind, _ = gel.THRESHOLD_PROVENANCE["resolving_window"]
    assert kind == "convention"


@pytest.mark.unit
def test_every_provenance_entry_is_explained():
    for name, (kind, explanation) in gel.THRESHOLD_PROVENANCE.items():
        assert kind in ("convention", "sourced"), name
        assert explanation.strip(), name


@pytest.mark.unit
def test_lanes_and_gels_serialise_for_a_renderer():
    built = gel.build_gel([gel.product_lane(900)])
    data = built.to_dict()
    assert data["model"] == "log-linear"
    assert data["lanes"][0]["kind"] == "ladder"
    assert "relative_mobility" in data["lanes"][0]["bands"][0]
