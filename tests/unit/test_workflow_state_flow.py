"""Shared state is the single source of truth across the workflow tabs.

Each stage used to keep its own private copy of the design: the panel held a
``_parts_cache``, the assembly palette hardcoded four samples, and a restored
session rebound ``self.state`` while every view still pointed at the old
object. These tests pin the data flow those fixes established.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis.parts.components import (
    CDS,
    Promoter,
    part_from_dict,
)
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState


def _promoter() -> Promoter:
    return Promoter(
        id="pTet",
        name="pTet",
        sequence="TCCCTATCAG",
        y_min=0.02,
        y_max=10.0,
        K_d=0.5,
        n=2.4,
        repressors=["TetR"],
    )


@pytest.mark.unit
def test_design_parts_round_trip_through_state():
    """A part survives serialization with its kinetic parameters intact."""
    state = SynBioState()
    state.add_design_part(_promoter())

    restored = state.design_parts
    assert len(restored) == 1
    p = restored[0]
    assert isinstance(p, Promoter)
    assert p.y_max == pytest.approx(10.0)
    assert p.K_d == pytest.approx(0.5)
    assert p.n == pytest.approx(2.4)
    assert p.repressors == ["TetR"]


@pytest.mark.unit
def test_part_from_dict_does_not_consume_its_input():
    """Deserializing twice must yield a part both times.

    ``_deserialize_part`` used to ``pop`` the discriminator off the caller's
    dict, so the second read returned None.
    """
    data = _promoter().to_dict()

    first = part_from_dict(data)
    second = part_from_dict(data)

    assert first is not None
    assert second is not None
    assert data["part_type"] == "promoter"


@pytest.mark.unit
def test_part_from_dict_tolerates_unknown_and_extra_keys():
    assert part_from_dict({"part_type": "not_a_part", "id": "x", "name": "x"}) is None
    assert part_from_dict({}) is None

    data = _promoter().to_dict()
    data["some_future_field"] = 123
    assert part_from_dict(data) is not None


@pytest.mark.unit
def test_load_from_dict_mutates_in_place_so_views_see_it():
    """A restore must not rebind the object the views already hold."""
    state = SynBioState()
    held_reference = state  # stands in for a controller's reference

    snapshot = SynBioState()
    snapshot.add_design_part(_promoter())

    state.load_from_dict(snapshot.to_dict())

    assert held_reference is state
    assert len(held_reference.design_parts) == 1
    assert held_reference.design_parts[0].id == "pTet"


@pytest.mark.unit
def test_copy_from_adopts_contents_without_rebinding():
    state = SynBioState()
    other = SynBioState()
    other.add_design_part(_promoter())

    state.copy_from(other)

    assert len(state.design_parts) == 1
    # Self-copy is a no-op rather than a wipe.
    state.copy_from(state)
    assert len(state.design_parts) == 1


@pytest.mark.unit
def test_assembly_palette_reads_catalogue_and_design_parts(destroy_after):
    """The palette is no longer four hardcoded samples."""
    from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
        PlasmidAssemblyController,
    )
    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        PlasmidAssemblyView,
    )

    state = SynBioState()
    state.add_design_part(_promoter())
    state.add_design_part(CDS(id="cds_gfp", name="GFP CDS", sequence="ATGAGT", product="GFP"))

    class _Catalogue:
        def get_all_parts(self):
            return [CDS(id="cat_tetr", name="TetR CDS", sequence="ATGTCT", product="TetR")]

    view = destroy_after(
        PlasmidAssemblyView(state, PlasmidAssemblyController(state), catalogue=_Catalogue())
    )

    labels = [view.part_palette.item(i).text() for i in range(view.part_palette.count())]
    assert any("pTet" in t for t in labels)
    assert any("GFP CDS" in t for t in labels)
    assert any("TetR CDS" in t for t in labels)


@pytest.mark.unit
def test_assembly_palette_carries_full_part_data(destroy_after):
    """Assembly must not rebuild parts from id/name/sequence alone."""
    from PySide6.QtCore import Qt

    from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
        PlasmidAssemblyController,
    )
    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        PlasmidAssemblyView,
    )

    state = SynBioState()
    state.add_design_part(_promoter())

    view = destroy_after(PlasmidAssemblyView(state, PlasmidAssemblyController(state)))

    item = view.part_palette.item(0)
    stored = part_from_dict(item.data(Qt.ItemDataRole.UserRole))

    assert isinstance(stored, Promoter)
    assert stored.y_max == pytest.approx(10.0)
    assert stored.repressors == ["TetR"]


@pytest.mark.unit
def test_assembly_refuses_a_part_with_no_sequence():
    """A missing sequence would silently shift every downstream coordinate."""
    from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
        MissingPartSequenceError,
        VectorAssemblyEngine,
    )

    parts = [
        Promoter(id="p1", name="pGood", sequence="TTGACA"),
        CDS(id="c1", name="NoSequence", sequence="", product="X"),
    ]

    with pytest.raises(MissingPartSequenceError) as excinfo:
        VectorAssemblyEngine.assemble_vector(vector_name="pBroken", parts=parts)

    assert "NoSequence" in str(excinfo.value)
