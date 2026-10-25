"""Unit tests for CRISPR/Cas9 Guide RNA Designer & CFD Off-Target Scorer."""

import pytest

from karcytics_plugins.synthetic_biology.analysis.crispr.grna_designer import (
    CRISPRDesignEngine,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import gRNACandidate


@pytest.mark.unit
def test_find_grna_candidates():
    """Test PAM scanner on both strands of target DNA."""
    target_dna = (
        "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"
        "AATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATAC"
    )
    candidates = CRISPRDesignEngine.find_grna_candidates(
        target_sequence=target_dna,
        pam_type="SpCas9 (NGG)",
        spacer_length=20,
    )

    assert len(candidates) > 0
    for cand in candidates:
        assert len(cand.protospacer) == 20
        assert 0.0 <= cand.gc_content <= 100.0
        assert 0.0 <= cand.efficiency_score <= 100.0
        assert 0.0 <= cand.off_target_score <= 100.0


@pytest.mark.unit
def test_find_grna_candidates_ascas12a():
    """Test AsCas12a (TTTV) 5' PAM scanner on target DNA."""
    # Contains TTTA (valid TTTV PAM) followed by a 20 bp protospacer
    target_dna = "GGGGGTTTAACGTACGTACGTACGTACGTCCCCC"
    candidates = CRISPRDesignEngine.find_grna_candidates(
        target_sequence=target_dna,
        pam_type="AsCas12a (TTTV)",
        spacer_length=20,
    )

    assert len(candidates) > 0
    ascas_cand = next((c for c in candidates if c.pam.startswith("TTT")), None)
    assert ascas_cand is not None
    assert len(ascas_cand.protospacer) == 20
    assert ascas_cand.protospacer == "ACGTACGTACGTACGTACGT"
    assert ascas_cand.pam == "TTTA"


@pytest.mark.unit
def test_cfd_off_target_scoring():
    """Test CFD mismatch penalty calculation."""
    cand = gRNACandidate(
        id="c1",
        target_id="t1",
        protospacer="ACTGGAGTTGTCCCAATTCT",
        pam="TGG",
        strand=1,
        start=0,
        end=23,
        gc_content=50.0,
        efficiency_score=80.0,
        off_target_score=100.0,
    )

    genome_with_mismatch = "AAAAAAAAAAAAAAAAACTGGAGTTGTCCCAATTCTCGGAAAAAAAAAAAAAAAA"
    score = CRISPRDesignEngine.score_off_targets(cand, reference_genome=genome_with_mismatch)
    assert 0.0 <= score <= 100.0


@pytest.mark.unit
def test_cfd_off_target_pam_filtering():
    """Test that candidate off-target loci are only scored if adjacent PAM (NGG) is present."""
    cand = gRNACandidate(
        id="c1",
        target_id="t1",
        protospacer="ACTGGAGTTGTCCCAATTCT",
        pam="TGG",
        strand=1,
        start=0,
        end=23,
        gc_content=50.0,
        efficiency_score=80.0,
        off_target_score=100.0,
    )

    # 1 mismatch at pos 18 (C->A), followed by valid SpCas9 PAM "CGG" -> should detect off-target
    genome_with_pam = "AAAAAAAAAAAAAAAAACTGGAGTTGTCCCAATTATCGGAAAAAAAAAAAAAAAA"
    score_pam = CRISPRDesignEngine.score_off_targets(cand, reference_genome=genome_with_pam)
    assert score_pam < 100.0
    assert len(cand.off_target_hits) == 1
    assert cand.off_target_hits[0]["pam"] == "CGG"

    # 1 mismatch at pos 18, but followed by invalid PAM "CAA" -> should NOT detect off-target
    genome_without_pam = "AAAAAAAAAAAAAAAAACTGGAGTTGTCCCAATTATCAAAAAAAAAAAAAAAAAA"
    score_no_pam = CRISPRDesignEngine.score_off_targets(cand, reference_genome=genome_without_pam)
    assert score_no_pam == 100.0
    assert len(cand.off_target_hits) == 0
