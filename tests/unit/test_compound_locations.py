"""A GenBank feature that crosses the origin must keep its true extent.

Audit finding H-2. Biopython reports ``CompoundLocation.start`` as the minimum
part start and ``.end`` as the maximum part end. For a feature expressed as
``join(5101..5243,1..180)`` — a 323 bp ORF crossing the origin of a 5,243 bp
plasmid — those are 0 and 5243, so reading them flattened a short feature into
the whole molecule. Nine ordinary features on the same record imported
exactly; this one appeared in the feature table as a 5,243 bp CDS, which is
the confidently-wrong category: the map still draws and the table still
populates.

The wrap is detected from the ORDER of the parts, not their number, because a
spliced CDS is also a compound location and does not wrap. Both cases are
pinned here.
"""

from __future__ import annotations

from io import StringIO

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import GeneticFeature

LENGTH = 5243

#: The wrap, as GenBank writes it: 5100..5243 then 0..180 = 323 bp.
WRAP_PARTS = ((5100, LENGTH), (0, 180))
WRAP_LENGTH = (LENGTH - 5100) + 180

#: A spliced CDS. Also a compound location; must not be read as wrapping.
SPLICE_PARTS = ((4400, 4500), (4600, 4700))


def _record() -> str:
    seq = "ACGT" * (LENGTH // 4) + "A" * (LENGTH % 4)
    record = SeqRecord(
        Seq(seq),
        id="pKARC",
        name="pKARC_TEST",
        description="origin-wrap fixture",
        annotations={"molecule_type": "DNA", "topology": "circular"},
    )

    def simple(start, end, kind, name, strand=1):
        return SeqFeature(
            FeatureLocation(start, end, strand=strand),
            type=kind,
            qualifiers={"label": [name]},
        )

    def compound(parts, name):
        return SeqFeature(
            CompoundLocation([FeatureLocation(a, b, strand=1) for a, b in parts]),
            type="CDS",
            qualifiers={"label": [name]},
        )

    record.features = [
        simple(350, 1100, "CDS", "gfp_reporter"),
        simple(1250, 2060, "CDS", "kanR", strand=-1),
        simple(3500, 4100, "rep_origin", "ori"),
        compound(WRAP_PARTS, "origin_spanning_orf"),
        compound(SPLICE_PARTS, "spliced_orf"),
    ]
    handle = StringIO()
    SeqIO.write(record, handle, "genbank")
    return handle.getvalue()


@pytest.fixture
def vector():
    return VectorAssemblyEngine.parse_sequence_file(_record(), file_format="genbank")


def _named(vector, name):
    return next(f for f in vector.features if f.name == name)


# ── The wrap survives import ───────────────────────────────────────────


@pytest.mark.unit
def test_an_origin_spanning_feature_keeps_its_true_length(vector):
    """323 bp, not 5,243."""
    feature = _named(vector, "origin_spanning_orf")

    assert feature.length == WRAP_LENGTH == 323
    assert feature.length < LENGTH, "a short ORF must not become the whole plasmid"


@pytest.mark.unit
def test_an_origin_spanning_feature_keeps_its_segments(vector):
    feature = _named(vector, "origin_spanning_orf")

    assert feature.segments == WRAP_PARTS
    assert feature.parts == WRAP_PARTS
    assert feature.wraps_origin is True


@pytest.mark.unit
def test_the_wrap_is_visible_from_start_and_end_alone(vector):
    """End < start says 'wraps' without consulting a flag, and makes a naive
    subtraction obviously wrong rather than confidently wrong.
    """
    feature = _named(vector, "origin_spanning_orf")

    assert feature.start == 5100
    assert feature.end == 180
    assert feature.end < feature.start
    assert feature.end - feature.start < 0, (
        "the old code returned 5243 here, which looked like a real length"
    )


@pytest.mark.unit
def test_the_sequence_is_the_concatenated_segments(vector):
    feature = _named(vector, "origin_spanning_orf")

    assert len(feature.sequence) == WRAP_LENGTH
    expected = vector.sequence[5100:LENGTH] + vector.sequence[0:180]
    assert feature.sequence == expected


# ── A spliced CDS is not a wrap ────────────────────────────────────────


@pytest.mark.unit
def test_a_spliced_feature_is_compound_but_does_not_wrap(vector):
    """Ascending parts are exons, not an origin crossing."""
    feature = _named(vector, "spliced_orf")

    assert feature.segments == SPLICE_PARTS
    assert feature.wraps_origin is False
    assert feature.length == 200, "the summed exons, not the 300 bp genomic span"
    assert feature.start == 4400
    assert feature.end == 4700


# ── Simple features are untouched ──────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "start", "end", "strand"),
    [("gfp_reporter", 350, 1100, 1), ("kanR", 1250, 2060, -1), ("ori", 3500, 4100, 1)],
)
def test_a_single_segment_feature_is_unaffected(vector, name, start, end, strand):
    feature = _named(vector, name)

    assert (feature.start, feature.end, feature.strand) == (start, end, strand)
    assert feature.segments == (), "a simple feature carries no segment list"
    assert feature.wraps_origin is False
    assert feature.length == end - start
    assert feature.parts == ((start, end),)


# ── Round trip ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_a_round_trip_preserves_the_wrap_and_the_length(vector):
    """Export used to flatten the wrap again on the way out."""
    exported = VectorAssemblyEngine.export_genbank(vector)
    back = VectorAssemblyEngine.parse_sequence_file(exported, file_format="genbank")

    feature = _named(back, "origin_spanning_orf")
    assert feature.wraps_origin is True
    assert feature.segments == WRAP_PARTS
    assert feature.length == WRAP_LENGTH


@pytest.mark.unit
def test_a_round_trip_preserves_a_spliced_feature(vector):
    exported = VectorAssemblyEngine.export_genbank(vector)
    back = VectorAssemblyEngine.parse_sequence_file(exported, file_format="genbank")

    feature = _named(back, "spliced_orf")
    assert feature.segments == SPLICE_PARTS
    assert feature.wraps_origin is False
    assert feature.length == 200


@pytest.mark.unit
def test_a_round_trip_leaves_sequence_and_topology_alone(vector):
    exported = VectorAssemblyEngine.export_genbank(vector)
    back = VectorAssemblyEngine.parse_sequence_file(exported, file_format="genbank")

    assert back.sequence == vector.sequence
    assert back.is_circular == vector.is_circular
    assert len(back.features) == len(vector.features)


@pytest.mark.unit
def test_the_feature_survives_a_dict_round_trip(vector):
    """State is persisted as dicts, so the segments must travel with it."""
    feature = _named(vector, "origin_spanning_orf")

    restored = GeneticFeature.from_dict(feature.to_dict())

    assert restored.segments == WRAP_PARTS
    assert restored.wraps_origin is True
    assert restored.length == WRAP_LENGTH


@pytest.mark.unit
def test_a_feature_from_an_older_payload_defaults_to_no_wrap():
    """A dict written before this change carries neither field."""
    restored = GeneticFeature.from_dict(
        {"id": "x", "name": "legacy", "feature_type": "cds", "start": 10, "end": 40}
    )

    assert restored.segments == ()
    assert restored.wraps_origin is False
    assert restored.length == 30


# ── The shared coordinate label ────────────────────────────────────────


@pytest.mark.unit
def test_the_span_label_writes_the_wrap_out(vector):
    feature = _named(vector, "origin_spanning_orf")

    assert feature.span_label() == "5,100-5,243 + 0-180 (wraps origin)"
    assert feature.span_label(note_wrap=False) == "5,100-5,243 + 0-180"


@pytest.mark.unit
def test_the_span_label_of_a_simple_feature_is_one_range(vector):
    assert _named(vector, "gfp_reporter").span_label() == "350-1,100"
