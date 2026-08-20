"""Unit tests for the SequencePredictor (PromoterBiophysicsStrategy,
CDSStructuralStrategy & k-NN fallback).
"""

import os
import sys
from unittest.mock import MagicMock

# Mock sbol3 if not present in environment
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

from karcytics_plugins.synthetic_biology.analysis.catalogue.repository import (
    JsonPartRepository,
)
from karcytics_plugins.synthetic_biology.analysis.catalogue.service import (
    PartsCatalogueService,
)
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.analysis.prediction.sequence_predictor import (
    SequencePredictor,
    levenshtein_distance,
    translate_dna_to_protein,
)


def test_levenshtein_distance():
    """Test string edit distance calculation."""
    assert levenshtein_distance("ATGC", "ATGC") == 0
    assert levenshtein_distance("ATGC", "ATGA") == 1
    assert levenshtein_distance("ATGC", "ATG") == 1
    assert levenshtein_distance("", "ATGC") == 4
    assert levenshtein_distance("atgc", "ATGC") == 0  # Case insensitivity


def test_translate_dna_to_protein():
    """Test DNA sequence translation into amino acids using standard genetic code."""
    # ATG (M) GCG (A) TTC (F) TAA (*)
    dna = "ATGGCGTTCTAA"
    protein = translate_dna_to_protein(dna)
    assert protein == "MAF"


def test_promoter_biophysics_perfect_consensus():
    """Test biophysical PWM prediction for a promoter with perfect -35 and -10
    consensus motifs.
    """
    spacer_17 = "AGCTAGCTAGCTAGCTA"  # 17 bp
    perfect_seq = "CGTAC" + "TTGACA" + spacer_17 + "TATAAT" + "GCTAG"

    res = SequencePredictor.predict(perfect_seq, [], part_type="promoter")

    assert res["is_predicted"] is True
    assert res["model_type"] == "Thermodynamic PWM Model"
    assert res["details"]["hexamer_35"] == "TTGACA"
    assert res["details"]["hexamer_10"] == "TATAAT"
    assert res["details"]["spacer_len"] == 17
    assert res["details"]["binding_penalty_kB_T"] == 0.0

    assert res["parameters"]["y_max"] == 250.0
    assert res["parameters"]["K_d"] == 0.05
    assert res["parameters"]["n"] == 2.0


def test_promoter_biophysics_mutated_sequence():
    """Test that mutations in -35/-10 motifs reduce y_max and increase K_d."""
    spacer_17 = "AGCTAGCTAGCTAGCTA"
    perfect_seq = "CGTAC" + "TTGACA" + spacer_17 + "TATAAT" + "GCTAG"
    res_perfect = SequencePredictor.predict(perfect_seq, [], part_type="promoter")

    mutated_seq = "CGTAC" + "TCGACA" + spacer_17 + "TAGAAT" + "GCTAG"
    res_mutated = SequencePredictor.predict(mutated_seq, [], part_type="promoter")

    assert res_mutated["is_predicted"] is True
    assert res_mutated["details"]["binding_penalty_kB_T"] > 0.0
    assert res_mutated["parameters"]["y_max"] < res_perfect["parameters"]["y_max"]
    assert res_mutated["parameters"]["K_d"] > res_perfect["parameters"]["K_d"]


def test_promoter_biophysics_spacer_strain():
    """Test that deviations from optimal 17bp spacer length add structural strain
    penalty.
    """
    spacer_17 = "AGCTAGCTAGCTAGCTA"
    spacer_15 = "AGCTAGCTAGCTAGC"

    seq_17 = "CGTAC" + "TTGACA" + spacer_17 + "TATAAT" + "GCTAG"
    seq_15 = "CGTAC" + "TTGACA" + spacer_15 + "TATAAT" + "GCTAG"

    res_17 = SequencePredictor.predict(seq_17, [], part_type="promoter")
    res_15 = SequencePredictor.predict(seq_15, [], part_type="promoter")

    assert res_17["details"]["spacer_len"] == 17
    assert res_15["details"]["spacer_len"] == 15
    assert res_15["details"]["binding_penalty_kB_T"] > res_17["details"]["binding_penalty_kB_T"]


def test_cds_cai_translation_rate():
    """Test that optimal codon usage (high CAI) predicts higher translation_rate than
    rare codons.
    """
    # Optimal E. coli codons: ATG CTG GCG ACC CGT (Met Leu Ala Thr Arg)
    optimal_cds = "ATGCTGGCGACCCGT"
    # Rare E. coli codons: ATG CTA GCA ACA AGA (Met Leu Ala Thr Arg)
    rare_cds = "ATGCTAGCAACAAGA"

    res_opt = SequencePredictor.predict(optimal_cds, [], part_type="cds")
    res_rare = SequencePredictor.predict(rare_cds, [], part_type="cds")

    assert res_opt["is_predicted"] is True
    assert res_opt["model_type"] == "CAI & BLOSUM62 Stability Model"
    assert res_opt["details"]["cai_score"] > res_rare["details"]["cai_score"]
    assert res_opt["parameters"]["translation_rate"] > res_rare["parameters"]["translation_rate"]


def test_cds_blosum62_degradation_rate():
    """Test BLOSUM62 stability scoring for protein degradation rate."""
    # Reference CDS: ATG CTG AAA GGC (Met Leu Lys Gly) -> Protein "MLKG"
    ref_seq = "ATGCTGAAAGGC"
    ref_cds = CDS(
        id="C1",
        name="C1",
        sequence=ref_seq,
        translation_rate=0.5,
        degradation_rate=0.01,
    )

    # Conservative mutation: ATG ATC AAA GGC (L -> I) -> Protein "MIKG"
    cons_seq = "ATGATCAAAGGC"
    res_cons = SequencePredictor.predict(cons_seq, [ref_cds], part_type="cds")

    # Non-conservative mutation: ATG TGG AAA GGC (L -> W) -> Protein "MWKG"
    noncons_seq = "ATGTGGAAAGGC"
    res_noncons = SequencePredictor.predict(noncons_seq, [ref_cds], part_type="cds")

    assert res_cons["is_predicted"] is True
    assert res_noncons["is_predicted"] is True
    # Non-conservative mutation should have higher structural penalty and higher
    # degradation_rate
    assert (
        res_noncons["details"]["structural_penalty_norm"]
        > res_cons["details"]["structural_penalty_norm"]
    )
    assert (
        res_noncons["parameters"]["degradation_rate"] > res_cons["parameters"]["degradation_rate"]
    )


def test_cds_frameshift_fallback_to_knn():
    """Test that non-triplet CDS DNA length (frameshift error) safely falls back to
    k-NN strategy.
    """
    invalid_cds = "ATGAAATTTGG"  # 11 bp (not divisible by 3)
    c1 = CDS(
        id="C1",
        name="C1",
        sequence="ATGAAATTTGGG",
        translation_rate=0.5,
        degradation_rate=0.01,
    )

    res = SequencePredictor.predict(invalid_cds, [c1], part_type="cds", k=1)

    assert res["is_predicted"] is True
    assert res["model_type"] == "k-NN Distance Alignment"
    assert res["parameters"]["translation_rate"] == 0.5


def test_exact_sequence_match():
    """Test that an exact characterized candidate match returns exact parameters."""
    p1 = Promoter(
        id="P1",
        name="P1",
        sequence="TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC",
        y_max=250.0,
        y_min=0.5,
        K_d=40.0,
        n=2.0,
    )
    res = SequencePredictor.predict(p1.sequence, [p1], part_type="promoter", k=3)

    assert res["is_predicted"] is True
    assert res["top_match_id"] == "P1"
    assert res["parameters"]["y_max"] == 250.0
    assert res["parameters"]["K_d"] == 40.0


def test_empty_sequence_handling():
    """Test handling of empty sequence."""
    p1 = Promoter(id="P1", name="P1", sequence="ATGC", y_max=10.0)
    res = SequencePredictor.predict("", [p1], part_type="promoter")
    assert res["is_predicted"] is False
    assert "Empty sequence" in res["error"]


def test_catalogue_service_integration():
    """Test PartsCatalogueService.predict_part_parameters integration."""
    test_file = "temp_test_cat.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    try:
        repo = JsonPartRepository(test_file)
        service = PartsCatalogueService(repo)
        service.initialize_cello_parts()

        query_seq = "TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC"
        result = service.predict_part_parameters(query_seq, part_type="promoter", k=3)

        assert result["is_predicted"] is True
        assert result["top_match_id"] is not None
        assert "y_max" in result["parameters"]
        assert "K_d" in result["parameters"]
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
