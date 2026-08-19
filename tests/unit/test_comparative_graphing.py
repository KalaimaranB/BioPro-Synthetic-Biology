"""Unit tests for the comparative graphing module (WT reverse lookup, dual
parameter extraction, and curve generation).
"""

from matplotlib.figure import Figure

from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.analysis.prediction.graphing_utils import (
    generate_transfer_curve,
)
from karcytics_plugins.synthetic_biology.analysis.prediction.sequence_predictor import (
    compare_kinetics,
    identify_wildtype,
)


def test_identify_wildtype():
    """Test wild type reverse lookup finds part with lowest distance strictly > 0."""
    wt_seq = "CGTACTTGACAAGCTAGCTAGCTAGCTATATAATGCTAG"  # Baseline
    far_seq = "CGTACCCCACAAGCTAGCTAGCTAGCTATAGAATGCTAG"  # Multiple mutations (dist = 3)
    near_seq = (
        "CGTACTTGACAAGCTAGCTAGCTAGCTATATAATGCTAA"  # Single base swap at end (dist = 1)
    )
    mut_seq = "CGTACTTGACAAGCTAGCTAGCTAGCTATATAATGCTAG"  # Exact match (dist = 0)

    wt_part = Promoter(id="WT_P1", name="Wild Type 1", sequence=wt_seq)
    far_part = Promoter(id="WT_P2", name="Wild Type 2", sequence=far_seq)
    near_part = Promoter(id="WT_P3", name="Wild Type 3", sequence=near_seq)
    exact_part = Promoter(id="MUT_P", name="Exact Mutated", sequence=mut_seq)

    catalogue = [wt_part, far_part, near_part, exact_part]

    res = identify_wildtype(mut_seq, catalogue, part_type="promoter")

    assert res is not None
    # exact_part has distance 0, so it must be ignored!
    # Lowest distance strictly > 0 is near_part (dist = 1)
    assert res["id"] == "WT_P3"
    assert res["distance"] == 1

    assert res["distance"] == 1


def test_identify_wildtype_no_candidates():
    """Test identify_wildtype returns None if sequence is identical to all or
    database is empty.
    """
    seq = "CGTACTTGACAAGCTAGCTAGCTAGCTATATAATGCTAG"
    exact_part = Promoter(id="P1", name="P1", sequence=seq)

    res = identify_wildtype(seq, [exact_part], part_type="promoter")
    assert res is None  # Lowest distance strictly > 0 does not exist


def test_compare_kinetics_promoter():
    """Test dual parameter extraction for promoter sequences."""
    wt_seq = "CGTACTTGACAAGCTAGCTAGCTAGCTATATAATGCTAG"
    mut_seq = "CGTACTCGACAAGCTAGCTAGCTAGCTATAGAATGCTAG"  # 2 substitutions

    wt_part = Promoter(id="WT_Prom", name="WT Promoter", sequence=wt_seq)
    catalogue = [wt_part]

    res = compare_kinetics(mut_seq, catalogue, part_type="promoter")

    assert res["part_type"] == "promoter"
    assert res["wildtype_info"]["id"] == "WT_Prom"
    assert res["wildtype_info"]["distance"] == 2
    assert "wt_params" in res
    assert "mut_params" in res
    assert res["wt_params"]["y_max"] > res["mut_params"]["y_max"]
    assert res["wt_params"]["K_d"] < res["mut_params"]["K_d"]


def test_compare_kinetics_cds():
    """Test dual parameter extraction for CDS sequences."""
    wt_seq = "ATGCTGGCGACCCGT"  # Met-Leu-Ala-Thr-Arg
    mut_seq = "ATGCTAGCAACAAGA"  # Rare codons

    wt_part = CDS(
        id="WT_CDS",
        name="WT CDS",
        sequence=wt_seq,
        translation_rate=0.5,
        degradation_rate=0.01,
    )
    catalogue = [wt_part]

    res = compare_kinetics(mut_seq, catalogue, part_type="cds")

    assert res["part_type"] == "cds"
    assert res["wildtype_info"]["id"] == "WT_CDS"
    assert "wt_translation_rate" in res
    assert "mut_translation_rate" in res


def test_generate_transfer_curve_promoter():
    """Test Matplotlib transfer curve generation for promoters."""
    wt_params = {"K_d": 0.05, "y_max": 250.0, "y_min": 0.01, "n": 2.0}
    mut_params = {"K_d": 0.50, "y_max": 100.0, "y_min": 0.01, "n": 2.0}

    fig = generate_transfer_curve(wt_params, mut_params, part_type="promoter")

    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    assert ax.get_xlabel() == "Repressor Concentration ([R])"
    assert ax.get_ylabel() == "Output Expression (RPU)"
    assert len(ax.get_lines()) == 2
    wt_line, mut_line = ax.get_lines()
    assert wt_line.get_linestyle() in ["-", "solid"]
    assert mut_line.get_linestyle() in ["--", "dashed"]


def test_generate_transfer_curve_cds():
    """Test Matplotlib transfer curve generation for CDS protein accumulation."""
    wt_params = {"translation_rate": 0.8, "degradation_rate": 0.01}
    mut_params = {"translation_rate": 0.2, "degradation_rate": 0.05}

    fig = generate_transfer_curve(wt_params, mut_params, part_type="cds")

    assert isinstance(fig, Figure)
    ax = fig.axes[0]
    assert ax.get_xlabel() == "Time (min)"
    assert ax.get_ylabel() == "Protein Concentration (P)"
    assert len(ax.get_lines()) == 2


def test_compare_kinetics_missense_mutation():
    """Test missense mutation heavily penalizes degradation_rate and differentiates
    curves.
    """
    wt_seq = "ATGCTGGCGACCCGT"  # Met-Leu-Ala-Thr-Arg
    mut_seq = "ATGTGGGCGACCCGT"  # Met-Trp-Ala-Thr-Arg (Leu -> Trp missense mutation)

    wt_part = CDS(
        id="WT_CDS",
        name="WT CDS",
        sequence=wt_seq,
        translation_rate=0.5,
        degradation_rate=0.01,
    )
    catalogue = [wt_part]

    res = compare_kinetics(mut_seq, catalogue, part_type="cds")

    assert res["part_type"] == "cds"
    assert res["wt_degradation_rate"] == 0.01
    assert res["mut_degradation_rate"] > res["wt_degradation_rate"]
    assert res["mut_degradation_rate"] >= 0.15
