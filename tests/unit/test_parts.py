"""Unit tests for the Biological Parts domain model."""

import pytest

from analysis.parts.components import CDS, RBS, Promoter, Terminator


class TestPromoter:
    def test_initialization(self):
        promoter = Promoter(
            id="BBa_R0040",
            name="TetR repressible promoter",
            description="Repressed by TetR",
            sequence="TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC",
            y_max=2.5,
            repressors=["TetR"],
        )
        assert promoter.id == "BBa_R0040"
        assert promoter.part_type == "promoter"
        assert promoter.y_max == 2.5
        assert promoter.repressors == ["TetR"]

    def test_to_dict(self):
        promoter = Promoter(id="p1", name="P1", repressors=["LacI"])
        data = promoter.to_dict()
        assert data["id"] == "p1"
        assert data["part_type"] == "promoter"
        assert data["repressors"] == ["LacI"]
        assert "y_max" in data


class TestCDS:
    def test_initialization(self):
        cds = CDS(
            id="BBa_E0040",
            name="GFP",
            description="Green fluorescent protein",
            translation_rate=5.0,
            degradation_rate=0.05,
            product="GFP_protein",
        )
        assert cds.id == "BBa_E0040"
        assert cds.part_type == "cds"
        assert cds.translation_rate == 5.0
        assert cds.product == "GFP_protein"

    def test_to_dict(self):
        cds = CDS(id="c1", name="C1", product="TetR")
        data = cds.to_dict()
        assert data["id"] == "c1"
        assert data["part_type"] == "cds"
        assert data["product"] == "TetR"
        assert "degradation_rate" in data


class TestTerminator:
    def test_initialization(self):
        term = Terminator(id="BBa_B0015", name="Double terminator", termination_efficiency=0.99)
        assert term.id == "BBa_B0015"
        assert term.part_type == "terminator"
        assert term.termination_efficiency == 0.99


class TestRBS:
    def test_initialization(self):
        rbs = RBS(id="BBa_B0034", name="Strong RBS", translation_initiation_rate=1.5)
        assert rbs.id == "BBa_B0034"
        assert rbs.part_type == "rbs"
        assert rbs.translation_initiation_rate == 1.5
