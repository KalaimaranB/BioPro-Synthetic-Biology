"""Unit tests for Phase 3 Empirical Analytics services and ML optimization loop."""

from karcytics_plugins.synthetic_biology.analysis.empirical.fcs_ingestion import (
    FCSDataIngestionService,
)
from karcytics_plugins.synthetic_biology.analysis.empirical.ml_optimizer import (
    CircuitMLOptimizationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.empirical.ngs_alignment import (
    NGSAlignmentService,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    GeneticFeature,
    PlasmidVector,
)


def test_fcs_ingestion_standalone(tmp_path):
    fcs_file = tmp_path / "sample.fcs"
    fcs_file.write_text("HEADER_FCS3.0_DATA")

    service = FCSDataIngestionService()
    res = service.ingest_fcs_file(str(fcs_file))

    assert res.is_valid is True
    assert res.total_events == 10000
    assert "FITC-A (GFP)" in res.channels
    assert res.channel_stats["FITC-A (GFP)"].mean_intensity > 0


def test_ngs_alignment():
    plasmid = PlasmidVector(
        id="pTET_01",
        name="TetR Expression Vector",
        sequence="ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC" * 10,
        features=[
            GeneticFeature(
                id="feat1",
                name="pTet Promoter",
                feature_type="promoter",
                start=0,
                end=50,
            ),
            GeneticFeature(
                id="feat2", name="tetR CDS", feature_type="cds", start=50, end=200
            ),
        ],
    )

    result = NGSAlignmentService.align_ngs_reads("sample_reads.fastq", plasmid)

    assert result.success is True
    assert result.total_reads_aligned > 0
    assert len(result.variants) >= 3
    valid_types = ["SNP", "Insertion", "Deletion", "CRISPR_OffTarget"]
    assert result.variants[0].variant_type in valid_types


def test_ml_optimization_loop():
    tetR = CircuitComponent(
        id="TetR",
        name="TetR",
        component_type="cds",
        y_min=0.001,
        y_max=10.0,
        K_d=1.0,
        n=2.0,
    )
    lacI = CircuitComponent(
        id="LacI",
        name="LacI",
        component_type="cds",
        y_min=0.001,
        y_max=10.0,
        K_d=1.0,
        n=2.0,
    )
    edges = [
        CircuitEdge(source_id="TetR", target_id="LacI", interaction_type="repression")
    ]

    service = FCSDataIngestionService()
    fcs_data = service.ingest_fcs_file("/dummy/path.fcs")

    opt_result = CircuitMLOptimizationEngine.fit_kinetic_parameters(
        components=[tetR, lacI],
        edges=edges,
        fcs_data=fcs_data,
    )

    assert opt_result.success is True
    assert opt_result.final_mse <= opt_result.initial_mse
    assert "TetR" in opt_result.parameter_deltas


def test_empirical_controller_teardown():
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.controllers.empirical_controller import (
        EmpiricalAnalyticsController,
    )

    state = SynBioState()
    controller = EmpiricalAnalyticsController(state)
    controller.teardown()
    assert len(controller._active_workers) == 0


def test_empirical_view_instantiation_and_teardown():
    import sys

    from PyQt6.QtWidgets import QApplication

    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.views.empirical_analytics_view import (
        EmpiricalAnalyticsView,
    )

    _ = QApplication.instance() or QApplication(sys.argv)
    state = SynBioState()
    view = EmpiricalAnalyticsView(state)
    assert view.fcs_tab is not None
    assert view.ngs_tab is not None
    assert view.ml_tab is not None

    view.teardown()
