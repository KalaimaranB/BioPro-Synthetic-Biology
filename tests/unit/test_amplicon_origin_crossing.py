"""A product that crosses the origin must say so, wherever the crossing falls.

Audit finding E-8. ``_build_amplicon`` read the crossing off the *interior*
between the two primers::

    wraps_origin=circular and (interior_end > length or fwd.wraps_origin)

The interior stops at the reverse primer's 3' terminus, so a product whose
crossing fell inside the reverse primer's own footprint — the last ~20 bases of
the product — was reported as not wrapping, and the amplification track drew no
origin annotation for it. The forward footprint had been patched for
separately; the reverse one was never added.

The determination now runs over the product's whole template extent, both
footprints included (:func:`_product_extent`). Each of the three places a
crossing can fall is pinned below, together with the two cases that must stay
negative, and the track's annotation is checked by painting for real rather
than by re-reading the flag.

Geometry
--------
``SYNTHETIC_TEMPLATE`` is 137 bp and the primers span its 117 bp ORF at
[10, 127). Rotating the template by ``r`` moves the product to
``(10 - r) mod 137`` and so slides the origin to a chosen point of the product.
Every rotation below must still yield exactly ``SYNTHETIC_ORF``: the product is
the same molecule each time, only the coordinates move.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
from karcytics_plugins.synthetic_biology.ui.widgets.amplification_track import (
    AmplificationTrack,
)

from .sequence_fixtures import SYNTHETIC_ORF, SYNTHETIC_TEMPLATE, primers_for

FWD, REV = primers_for(SYNTHETIC_ORF)
LENGTH = len(SYNTHETIC_TEMPLATE)

#: Rotation -> where the origin then falls within the product. Derived in the
#: module docstring; the assertions below re-check the geometry rather than
#: trusting these names.
INSIDE_FORWARD_FOOTPRINT = 20
INSIDE_REVERSE_FOOTPRINT = 117
INSIDE_THE_INTERIOR = 47
OUTSIDE_THE_PRODUCT = 0

WRAPPING_ROTATIONS = (
    INSIDE_FORWARD_FOOTPRINT,
    INSIDE_REVERSE_FOOTPRINT,
    INSIDE_THE_INTERIOR,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _rotated(by: int) -> str:
    return SYNTHETIC_TEMPLATE[by:] + SYNTHETIC_TEMPLATE[:by]


def _product(by: int, *, circular: bool = True):
    result = amp.amplify(_rotated(by), FWD, REV, circular=circular)
    assert result.outcome == amp.PRODUCT, f"rotation {by} gave {result.outcome}"
    return result.product


def _straddles(site) -> bool:
    """True when the origin falls strictly inside this footprint."""
    return site.start < LENGTH < site.end


# ── The geometry is what the names claim ───────────────────────────────


@pytest.mark.unit
def test_the_three_rotations_put_the_crossing_where_the_names_say():
    """Guards the fixtures: a wrong rotation would make the rest vacuous."""
    forward = _product(INSIDE_FORWARD_FOOTPRINT)
    assert _straddles(forward.forward_site)
    assert not _straddles(forward.reverse_site)

    reverse = _product(INSIDE_REVERSE_FOOTPRINT)
    assert _straddles(reverse.reverse_site)
    assert not _straddles(reverse.forward_site), (
        "this is the case the interior test missed; the forward footprint must "
        "be clean or the old code would have caught it by accident"
    )

    interior = _product(INSIDE_THE_INTERIOR)
    assert not _straddles(interior.forward_site)
    assert not _straddles(interior.reverse_site)
    assert interior.forward_site.end < LENGTH < interior.reverse_site.start + LENGTH


# ── A crossing anywhere in the product is a crossing ───────────────────


@pytest.mark.unit
@pytest.mark.parametrize("rotation", WRAPPING_ROTATIONS)
def test_a_product_crossing_the_origin_reports_it(rotation):
    assert _product(rotation).wraps_origin is True


@pytest.mark.unit
@pytest.mark.parametrize("rotation", WRAPPING_ROTATIONS)
def test_the_wrapping_product_is_still_the_same_molecule(rotation):
    """The flag must not be bought with a changed product."""
    assert _product(rotation).sequence == SYNTHETIC_ORF


@pytest.mark.unit
def test_the_reverse_footprint_case_is_the_one_that_regressed():
    """Named on its own so a regression says which case broke.

    Before the fix this product reported ``wraps_origin is False`` while its
    reverse primer sat across the origin.
    """
    product = _product(INSIDE_REVERSE_FOOTPRINT)

    assert product.reverse_site.wraps_origin is True
    assert product.wraps_origin is True, "the reverse primer's footprint is part of the product too"


# ── And a product that does not cross must not claim to ────────────────


@pytest.mark.unit
def test_a_circular_product_clear_of_the_origin_does_not_report_a_crossing():
    product = _product(OUTSIDE_THE_PRODUCT)

    assert product.forward_site.start < product.reverse_site.end <= LENGTH
    assert product.wraps_origin is False


@pytest.mark.unit
@pytest.mark.parametrize("rotation", [*WRAPPING_ROTATIONS, OUTSIDE_THE_PRODUCT])
def test_a_linear_template_never_reports_a_crossing(rotation):
    """A linear molecule has no origin to cross, whatever the coordinates look
    like. Three of these rotations yield no product at all on a linear
    template, which is itself correct — the ORF is split across the ends.
    """
    result = amp.amplify(_rotated(rotation), FWD, REV, circular=False)

    for amplicon in result.amplicons:
        assert amplicon.wraps_origin is False


# ── The track draws the annotation ─────────────────────────────────────


class _TextRecorder(QPainter):
    """A painter that keeps every string drawn through it.

    The flag being right while the annotation stays absent is the same defect,
    so this drives the widget's real paint path rather than re-reading the
    flag. ``_paint`` is the same entry point ``paintEvent`` uses.
    """

    def __init__(self, device: QImage) -> None:
        super().__init__(device)
        self.strings: list[str] = []

    def drawText(self, *args) -> None:  # noqa: N802 - Qt override
        for arg in args:
            if isinstance(arg, str):
                self.strings.append(arg)
        super().drawText(*args)


def _painted_text(track: AmplificationTrack, result, template_bp: int) -> str:
    track.show_result(result, template_bp)
    canvas = track.canvas
    canvas.resize(900, 400)

    image = QImage(900, 400, QImage.Format.Format_ARGB32)
    recorder = _TextRecorder(image)
    try:
        canvas._paint(recorder)
    finally:
        recorder.end()
    return " | ".join(recorder.strings)


@pytest.mark.unit
@pytest.mark.parametrize("rotation", WRAPPING_ROTATIONS)
def test_the_track_annotates_every_wrapping_product(app, destroy_after, rotation):
    track = destroy_after(AmplificationTrack())
    result = amp.amplify(_rotated(rotation), FWD, REV, circular=True)

    drawn = _painted_text(track, result, LENGTH)

    assert "spans the origin" in drawn, drawn


@pytest.mark.unit
def test_the_track_leaves_a_non_wrapping_product_unannotated(app, destroy_after):
    track = destroy_after(AmplificationTrack())
    result = amp.amplify(_rotated(OUTSIDE_THE_PRODUCT), FWD, REV, circular=True)

    drawn = _painted_text(track, result, LENGTH)

    assert "Product 1" in drawn, "the product label must still be drawn"
    assert "spans the origin" not in drawn


# ── The extent helper itself ───────────────────────────────────────────


@pytest.mark.unit
def test_the_extent_covers_both_footprints_not_just_the_interior():
    product = _product(INSIDE_REVERSE_FOOTPRINT)
    start, end = amp._product_extent(LENGTH, product.forward_site, product.reverse_site)

    assert start == product.forward_site.start
    assert end == product.reverse_site.end
    assert end > LENGTH, "the overshoot past the origin is what the flag reads"


@pytest.mark.unit
def test_the_extent_unwraps_a_reverse_primer_behind_the_forward_one():
    product = _product(INSIDE_THE_INTERIOR)
    fwd, rev = product.forward_site, product.reverse_site
    assert rev.start < fwd.start, "the fixture must put the reverse primer behind"

    _, end = amp._product_extent(LENGTH, fwd, rev)

    assert end == rev.end + LENGTH


@pytest.mark.unit
def test_the_extent_spans_exactly_the_bases_the_product_covers():
    """Tails add no template coordinates, so the extent is the untailed length."""
    product = _product(OUTSIDE_THE_PRODUCT)
    start, end = amp._product_extent(LENGTH, product.forward_site, product.reverse_site)

    assert end - start == len(SYNTHETIC_ORF) == product.length


# ── A 5' tail does not move the crossing ───────────────────────────────


@pytest.mark.unit
def test_a_tail_lengthens_the_product_without_changing_the_crossing():
    """A tail does not anneal, so it occupies no position on the template and
    cannot create or remove an origin crossing. Both tailed products below are
    longer than their untailed selves and carry the same verdict.
    """
    tail_f, tail_r = "GAATTC", "AAGCTT"

    for rotation, expected in [(INSIDE_REVERSE_FOOTPRINT, True), (OUTSIDE_THE_PRODUCT, False)]:
        plain = _product(rotation)
        tailed = amp.amplify(
            _rotated(rotation),
            tail_f + FWD,
            tail_r + REV,
            forward_tail=tail_f,
            reverse_tail=tail_r,
            circular=True,
        ).product

        assert tailed.length == plain.length + len(tail_f) + len(tail_r)
        assert tailed.wraps_origin is expected
