"""The part selector must accept typed IDs, and must not block the GUI thread.

``IGemClient.fetch_part`` is a blocking HTTP call with a 10 s timeout. Called
from a slot it freezes the application for as long as the registry takes, so
the fetch has to go through a worker.

Note on the worker assertions: conftest replaces the SDK's
``OneShotWorkerThread`` with a stub whose ``start()`` calls ``_execute()``
inline, so a fetch completes synchronously here. That makes the end-to-end
assertions easy but means "it ran" proves nothing about threading — hence
``test_the_registry_call_is_handed_to_a_worker``, which substitutes a
non-running spy and checks the slot itself never calls the client.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.parts.components import Promoter
from karcytics_plugins.synthetic_biology.ui.ribbons import design_ribbon as dr
from karcytics_plugins.synthetic_biology.ui.ribbons.design_ribbon import DesignRibbon
from karcytics_plugins.synthetic_biology.ui.workers import RegistryFetchWorker


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class FakeCatalogue:
    def __init__(self, parts=None):
        self._parts = {p.id: p for p in (parts or [])}

    def get_all_parts(self):
        return list(self._parts.values())

    def get_part(self, part_id):
        return self._parts.get(part_id)


class RecordingClient:
    """Stands in for IGemClient and records that it was called."""

    def __init__(self, result=None):
        self.result = result
        self.calls: list[str] = []

    def fetch_part(self, part_id):
        self.calls.append(part_id)
        return self.result


class FakeFactory:
    def __init__(self, catalogue=None, client=None):
        self._services = {"parts_catalogue": catalogue, "igem_client": client}

    def get(self, name):
        return self._services.get(name)


def _ribbon(destroy_after, catalogue=None, client=None):
    return destroy_after(DesignRibbon(FakeFactory(catalogue, client)))


# ── Defect 4: the combo was never editable ─────────────────────────────


@pytest.mark.unit
def test_the_part_selector_is_editable(app, destroy_after):
    """Without this a student cannot type a registry ID at all."""
    ribbon = _ribbon(destroy_after)
    assert ribbon.part_selector_combo.isEditable()


@pytest.mark.unit
def test_typing_does_not_silently_insert_a_row(app, destroy_after):
    ribbon = _ribbon(destroy_after)
    assert (
        ribbon.part_selector_combo.insertPolicy()
        == ribbon.part_selector_combo.InsertPolicy.NoInsert
    )


@pytest.mark.unit
def test_a_typed_id_reaches_the_registry(app, destroy_after):
    """The free-text branch used to be unreachable because the combo was fixed."""
    client = RecordingClient(result=Promoter(id="BBa_K1234", name="Typed"))
    ribbon = _ribbon(destroy_after, FakeCatalogue(), client)

    ribbon.part_selector_combo.setCurrentText("BBa_K1234")
    ribbon._on_fetch()

    assert client.calls == ["BBa_K1234"]


@pytest.mark.unit
def test_a_typed_id_wins_over_a_stale_selection(app, destroy_after):
    """An editable combo keeps currentData() from the previously chosen row."""
    client = RecordingClient()
    ribbon = _ribbon(destroy_after, FakeCatalogue(), client)

    ribbon.part_selector_combo.clear()
    ribbon.part_selector_combo.addItem("BBa_R0040 - TetR promoter", userData="BBa_R0040")
    ribbon.part_selector_combo.setCurrentIndex(0)
    ribbon.part_selector_combo.setCurrentText("BBa_J23100")

    ribbon._on_fetch()

    assert client.calls == ["BBa_J23100"], "the stale selection was used instead"


@pytest.mark.unit
def test_selecting_a_row_still_uses_its_id(app, destroy_after):
    client = RecordingClient()
    ribbon = _ribbon(destroy_after, FakeCatalogue(), client)

    ribbon.part_selector_combo.clear()
    ribbon.part_selector_combo.addItem("BBa_R0040 - TetR promoter", userData="BBa_R0040")
    ribbon.part_selector_combo.setCurrentIndex(0)

    ribbon._on_fetch()

    assert client.calls == ["BBa_R0040"]


@pytest.mark.unit
def test_an_empty_selection_does_nothing(app, destroy_after):
    client = RecordingClient()
    ribbon = _ribbon(destroy_after, FakeCatalogue(), client)

    ribbon.part_selector_combo.clear()
    ribbon.part_selector_combo.setCurrentText("")
    ribbon._on_fetch()

    assert client.calls == []


# ── Defect 5: the fetch ran on the UI thread ───────────────────────────


@pytest.mark.unit
def test_the_registry_call_is_handed_to_a_worker(app, destroy_after, monkeypatch):
    """The slot must not call the client; it must construct a worker.

    A non-running spy stands in for the worker, so if the slot still called
    ``fetch_part`` itself the client would record it.
    """
    created = {}

    class SpyWorker:
        def __init__(self, client, part_id, parent=None):
            created["client"] = client
            created["part_id"] = part_id
            created["started"] = False
            self.part_fetched = _Sig()
            self.error_occurred = _Sig()

        def start(self):
            created["started"] = True

    class _Sig:
        def connect(self, _):
            return None

    monkeypatch.setattr(dr, "RegistryFetchWorker", SpyWorker)

    client = RecordingClient(result=Promoter(id="BBa_K1", name="Remote"))
    ribbon = _ribbon(destroy_after, FakeCatalogue(), client)
    ribbon.part_selector_combo.setCurrentText("BBa_K1")

    ribbon._on_fetch()

    assert created["part_id"] == "BBa_K1"
    assert created["client"] is client
    assert created["started"] is True
    assert client.calls == [], "the slot called the registry on the UI thread"


@pytest.mark.unit
def test_the_button_shows_progress_while_a_fetch_is_in_flight(app, destroy_after, monkeypatch):
    class SpyWorker:
        def __init__(self, client, part_id, parent=None):
            self.part_fetched = _Sig()
            self.error_occurred = _Sig()

        def start(self):
            return None

    class _Sig:
        def connect(self, _):
            return None

    monkeypatch.setattr(dr, "RegistryFetchWorker", SpyWorker)

    ribbon = _ribbon(destroy_after, FakeCatalogue(), RecordingClient())
    ribbon.part_selector_combo.setCurrentText("BBa_slow")
    ribbon._on_fetch()

    assert not ribbon.fetch_btn.isEnabled()
    assert ribbon.fetch_btn.text() == "Fetching..."


@pytest.mark.unit
def test_a_local_hit_never_touches_the_registry(app, destroy_after):
    """A dict lookup needs no thread and no network."""
    local = Promoter(id="local_p", name="Local Part")
    client = RecordingClient()
    ribbon = _ribbon(destroy_after, FakeCatalogue([local]), client)

    received = []
    ribbon.part_fetched.connect(received.append)

    ribbon.part_selector_combo.setCurrentText("local_p")
    ribbon._on_fetch()

    assert client.calls == []
    assert ribbon._active_worker is None
    assert received == [local]


@pytest.mark.unit
def test_the_button_is_restored_after_a_miss(app, destroy_after):
    """A registry miss must not leave the button stuck on 'Fetching...'."""
    ribbon = _ribbon(destroy_after, FakeCatalogue(), RecordingClient(None))

    ribbon.part_selector_combo.setCurrentText("BBa_missing")
    ribbon._on_fetch()

    assert ribbon.fetch_btn.isEnabled()
    assert ribbon.fetch_btn.text() == "Fetch Part"
    assert ribbon._active_worker is None


@pytest.mark.unit
def test_a_successful_fetch_emits_the_part(app, destroy_after):
    remote = Promoter(id="BBa_K1", name="Remote")
    ribbon = _ribbon(destroy_after, FakeCatalogue(), RecordingClient(result=remote))

    received = []
    ribbon.part_fetched.connect(received.append)

    ribbon.part_selector_combo.setCurrentText("BBa_K1")
    ribbon._on_fetch()

    assert received == [remote]
    assert ribbon.fetch_btn.isEnabled()


# ── The worker itself ──────────────────────────────────────────────────


@pytest.mark.unit
def test_the_worker_passes_a_miss_through_as_none(app):
    """None is a legitimate result and must survive the signal."""
    worker = RegistryFetchWorker(client=RecordingClient(None), part_id="nope")
    received = []
    worker.part_fetched.connect(received.append)

    worker._execute()

    assert received == [None]


@pytest.mark.unit
def test_the_worker_emits_the_part_it_fetched(app):
    part = Promoter(id="BBa_K1", name="Remote")
    worker = RegistryFetchWorker(client=RecordingClient(part), part_id="BBa_K1")
    received = []
    worker.part_fetched.connect(received.append)

    worker._execute()

    assert received == [part]
