"""Unit tests for Vector Assembly Engine and Biopython integration."""

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine,
)
from karcytics_plugins.synthetic_biology.analysis.parts.components import (
    CDS,
    RBS,
    Promoter,
    Terminator,
)


@pytest.mark.unit
def test_calculate_tm():
    """Test Wallace / GC-based nearest-neighbor Tm calculations."""
    short_seq = "ATGCATGC"
    tm_short = VectorAssemblyEngine.calculate_tm(short_seq)
    assert tm_short > 0.0

    primer_seq = "GAATTCATGCATGCATGCATGC"
    tm_long = VectorAssemblyEngine.calculate_tm(primer_seq)
    assert 50.0 <= tm_long <= 75.0


@pytest.mark.unit
def test_design_primers():
    """Test automated PCR & assembly primer design algorithm."""
    target_seq = (
        "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"
        "AATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATAC"
    )
    fwd, rev = VectorAssemblyEngine.design_primers(
        target_sequence=target_seq,
        target_tm=60.0,
        fwd_overhang="GAATTC",
        rev_overhang="AAGCTT",
    )

    assert fwd.direction == "FWD"
    assert fwd.overhang == "GAATTC"
    assert fwd.sequence.startswith("GAATTC")
    assert abs(fwd.calculated_tm - 60.0) < 10.0

    assert rev.direction == "REV"
    assert rev.overhang == "AAGCTT"
    assert rev.sequence.startswith("AAGCTT")


@pytest.mark.unit
def test_assemble_vector():
    """Test stitching biological parts into a seamless PlasmidVector construct."""
    promoter = Promoter(id="p1", name="pTac", sequence="TTGACAATTAATCATCGGCTCGTATAATGTGTGG")
    rbs = RBS(id="r1", name="B0034", sequence="AAAGAGGAGAA")
    cds = CDS(id="c1", name="GFP", sequence="ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTT")
    term = Terminator(
        id="t1",
        name="B0015",
        sequence="CCAGGCATCAAATAAAACGAAAGGCTCAGTCGAAAGACTGGGCCTTTCGTTTTATCTGTTGTTTGTCGGTGAACGCTCTC",
    )

    vector = VectorAssemblyEngine.assemble_vector(
        vector_name="pTestVector",
        parts=[promoter, rbs, cds, term],
    )

    assert vector.name == "pTestVector"
    assert len(vector.features) == 4
    assert vector.features[0].name == "pTac"
    assert vector.features[1].name == "B0034"
    assert vector.features[2].name == "GFP"
    assert vector.features[3].name == "B0015"
    assert len(vector.sequence) == sum(len(p.sequence) for p in [promoter, rbs, cds, term])


@pytest.mark.unit
def test_genbank_export_import():
    """Test GenBank standard sequence import/export via Biopython."""
    promoter = Promoter(id="p1", name="pTac", sequence="TTGACAATTAATCATCGGCTCGTATAATGTGTGG")
    vector = VectorAssemblyEngine.assemble_vector(vector_name="pGBKTest", parts=[promoter])

    gbk_text = VectorAssemblyEngine.export_genbank(vector)
    assert "pGBKTest" in gbk_text
    assert "FEATURES" in gbk_text

    imported_vector = VectorAssemblyEngine.parse_sequence_file(gbk_text, file_format="genbank")
    assert imported_vector.length == vector.length
    assert len(imported_vector.features) >= 1
