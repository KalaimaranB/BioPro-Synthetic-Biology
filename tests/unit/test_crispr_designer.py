"""Unit tests for CRISPR/Cas9 Guide RNA Designer & CFD Off-Target Scorer."""

import pytest
from analysis.crispr.grna_designer import (
    CRISPRDesignEngine,
)
from analysis.models.domain import gRNACandidate


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
    score = CRISPRDesignEngine.score_off_targets(
        cand, reference_genome=genome_with_mismatch
    )
    assert 0.0 <= score <= 100.0
