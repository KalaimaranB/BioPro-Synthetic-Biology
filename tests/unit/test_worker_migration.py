"""Tests validating that all 6 custom background workers inherit from the SDK AnalysisWorker architecture."""

from __future__ import annotations

import pytest
from karcytics_sdk.plugin.task_scheduler import AnalysisWorker

from karcytics_plugins.synthetic_biology.ui.controllers.empirical_controller import EmpiricalWorker
from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import ProtocolWorker
from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SimulateWorker
from karcytics_plugins.synthetic_biology.ui.workers.assembly_worker import AssemblyWorker
from karcytics_plugins.synthetic_biology.ui.workers.base_worker import BaseSDKWorker
from karcytics_plugins.synthetic_biology.ui.workers.crispr_worker import CRISPRWorker
from karcytics_plugins.synthetic_biology.ui.workers.simulation_worker import CircuitSimWorker


@pytest.mark.parametrize(
    "worker_cls",
    [
        EmpiricalWorker,
        SimulateWorker,
        ProtocolWorker,
    ],
)
def test_all_workers_inherit_from_analysis_worker(worker_cls: type) -> None:
    """Verify that migrated workers inherit from BaseSDKWorker and SDK AnalysisWorker."""
    assert issubclass(worker_cls, BaseSDKWorker)
    assert issubclass(worker_cls, AnalysisWorker)


@pytest.mark.parametrize(
    "worker_cls",
    [
        CRISPRWorker,
        AssemblyWorker,
        CircuitSimWorker,
    ],
)
def test_oneshot_workers(worker_cls: type) -> None:
    """Verify upstream worker threads inherit from SDK OneShotWorkerThread."""
    from karcytics_sdk.plugin import OneShotWorkerThread

    assert issubclass(worker_cls, OneShotWorkerThread)


def test_base_worker_cancellation_semantics() -> None:
    """Verify BaseSDKWorker cancellation, interruption, and running state."""
    worker = BaseSDKWorker()
    assert not worker.is_cancelled()
    assert not worker.isRunning()

    worker.cancel()
    assert worker.is_cancelled()
    assert not worker.isRunning()

    # Test interruption request (QThread compatibility)
    worker2 = BaseSDKWorker()
    worker2.requestInterruption()
    assert worker2.is_cancelled()


def test_simulate_worker_cancellation_flag() -> None:
    """Verify SimulateWorker cancellation flag is recognized."""
    worker = SimulateWorker(
        model_str="test_model",
        method="Deterministic",
        max_time=10,
        title="Test Simulation",
    )
    assert not worker.is_cancelled()
    worker.cancel()
    assert worker.is_cancelled()
