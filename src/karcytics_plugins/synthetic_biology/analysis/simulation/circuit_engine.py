"""Predictive Genetic Circuit Simulation Engine.

Architects network topology using NetworkX.DiGraph and compiles dynamic system ODEs
solved using scipy.integrate.solve_ivp for Hill kinetics, logic gates, and oscillators.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.integrate import solve_ivp

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from ..provenance import CONVENTION, Provenance
from .kinetics import regulation_factor as regulation_factor_term
from .kinetics import resolve_edge_params

#: Where this simulator's model form comes from, in the same three-way scheme
#: the rest of the module uses (see ``analysis/provenance.py``). The topology is
#: published; the reduced one-species-per-gene dynamics are ours. Recording the
#: split here is what keeps the citation attached to the part of the claim the
#: paper actually supports - the same treatment the gel's log-linear mobility
#: form receives, where Southern (1979) supports the size dependence but not
#: that particular equation.
MODEL_PROVENANCE: dict[str, Provenance] = {
    "repressilator_topology": Provenance(
        kind=CONVENTION,
        explanation=(
            "The three-gene cyclic repressor ring is taken from the published "
            "design. The dynamics integrated here are a reduced, protein-only "
            "form of it and are this module's own modelling choice, not the "
            "published model."
        ),
        mechanism=("elowitz2000",),
        mechanism_claim=(
            "Elowitz & Leibler (2000) establish that a cyclic ring of three "
            "mutually repressing genes oscillates, and this preset reproduces "
            "that wiring. Their model carries three mRNA species in addition "
            "to the three proteins, and the transcription-translation delay it "
            "supplies is part of what drives the cycle. This simulator omits "
            "the mRNA stage, so the paper supports the topology and not these "
            "dynamics - in particular it does not support this system's Hopf "
            "threshold near n = 2.15, which is a property of the reduction."
        ),
    ),
}


class CircuitSimulationEngine:
    """Core domain service for compiling and solving kinetic genetic circuit
    differential equations.
    """

    @classmethod
    def build_circuit_graph(
        cls,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
    ) -> nx.DiGraph:
        """Constructs a NetworkX directed graph representation of the genetic circuit.

        Nodes represent promoters/CDSs/proteins, and edges represent regulatory
        connections.
        """
        graph = nx.DiGraph()

        for comp in components:
            graph.add_node(
                comp.id,
                name=comp.name,
                component_type=comp.component_type,
                y_min=comp.y_min,
                y_max=comp.y_max,
                K_d=comp.K_d,
                n=comp.n,
                degradation_rate=comp.degradation_rate,
                translation_rate=comp.translation_rate,
                initial_concentration=comp.initial_concentration,
                label=comp.display_label,
            )

        for edge in edges:
            # Skip dangling edges: adding one would make NetworkX create an
            # attribute-less node and the ODE assembly would then fail with a
            # bare KeyError instead of a usable message.
            if edge.source_id not in graph or edge.target_id not in graph:
                continue
            graph.add_edge(
                edge.source_id,
                edge.target_id,
                interaction_type=edge.interaction_type,
                strength=edge.strength,
                K_d=edge.K_d,
                n=edge.n,
            )

        return graph

    @classmethod
    def create_preset_repressilator(
        cls,
    ) -> tuple[list[CircuitComponent], list[CircuitEdge]]:
        """Build a reduced, protein-only form of the Elowitz & Leibler ring.

        The topology is theirs: the cyclic repressor ring
        TetR -| LacI -| cI -| TetR, in which each gene represses the next and
        the third closes the loop.

        **The dynamics are not theirs.** Elowitz & Leibler (2000) integrate six
        coupled equations - an mRNA species and a protein species for each of
        the three genes - and it is the transcription-translation step that
        supplies the delay driving the oscillation. This preset carries one
        species per gene. Production is a Hill function of the upstream
        repressor applied directly to the protein, with first-order decay, so
        the mRNA stage and its delay are absent.

        That reduction is deliberate and common, but it is a different
        dynamical system, and the difference is measurable here: removing the
        mRNA stage removes a lag from the feedback loop, so this system needs
        more cooperativity to oscillate than the published one does. Its Hopf
        threshold sits near n = 2.15. Do not read the numbers below as
        reproducing the paper.

        The Hill coefficient is 2.5 rather than the 2.1 this preset originally
        carried. A symmetric three-node repressor ring only holds its cycle
        above a threshold in n: integrating this reduced model at n = 2.1 gives a
        visibly damping trace (LacI amplitude 15.3 RPU over the first third of a
        400-min window, 1.4 RPU over the last), so the UI labelled it a
        sustained limit cycle while the engine was returning decay. At n = 2.5
        the amplitude holds (24.4 -> 23.1 RPU across the same window) with a
        period of about 35 min, which is the behaviour the preset's name
        promises. Lower n to see the Hopf threshold from the other side. These
        amplitudes were measured from this reduced model and are correct for
        it; the two-species system would place the threshold elsewhere.
        """
        tetR = CircuitComponent(  # noqa: N806
            id="TetR",
            name="TetR Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.5,
            degradation_rate=0.2,
            initial_concentration=5.0,
        )
        lacI = CircuitComponent(  # noqa: N806
            id="LacI",
            name="LacI Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.5,
            degradation_rate=0.2,
            initial_concentration=0.1,
        )
        cI = CircuitComponent(  # noqa: N806
            id="cI",
            name="cI Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.5,
            degradation_rate=0.2,
            initial_concentration=0.1,
        )

        edges = [
            CircuitEdge(
                source_id="TetR",
                target_id="LacI",
                interaction_type="repression",
                K_d=1.0,
                n=2.5,
            ),
            CircuitEdge(
                source_id="LacI",
                target_id="cI",
                interaction_type="repression",
                K_d=1.0,
                n=2.5,
            ),
            CircuitEdge(
                source_id="cI",
                target_id="TetR",
                interaction_type="repression",
                K_d=1.0,
                n=2.5,
            ),
        ]

        return [tetR, lacI, cI], edges

    @classmethod
    def simulate_circuit(  # noqa: C901
        cls,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
        params: SimulationParameters | None = None,
    ) -> SimulationResult:
        """Solves the differential equation system for the network topology.

        Models transcription and translation with non-linear Hill functions:
        d[P_i]/dt = y_min + (y_max - y_min) * Prod_repressors(1 / (1 + (R_j/K_d)^n))
                    * Prod_activators((A_k/K_d)^n / (1 + (A_k/K_d)^n))
                    - degradation * [P_i]
        """
        if params is None:
            params = SimulationParameters()

        if not components:
            return SimulationResult(
                status_message="No components in circuit topology", success=False
            )

        graph = cls.build_circuit_graph(components, edges)
        node_ids = list(graph.nodes())
        node_index_map = {nid: idx for idx, nid in enumerate(node_ids)}
        target_components = {c.id: c for c in components}

        y0 = np.array([graph.nodes[nid]["initial_concentration"] for nid in node_ids], dtype=float)

        def ode_system(_t: float, y: np.ndarray) -> np.ndarray:
            dydt = np.zeros_like(y)

            for idx, nid in enumerate(node_ids):
                node_data = graph.nodes[nid]
                y_min = node_data["y_min"]
                y_max = node_data["y_max"]
                deg = node_data["degradation_rate"]

                current_conc = y[idx]

                # Find incoming regulatory edges
                in_edges = graph.in_edges(nid, data=True)
                regulation_factor = 1.0

                for src_id, _, edge_data in in_edges:
                    src_idx = node_index_map[src_id]
                    src_conc = y[src_idx]

                    # Parameter resolution is shared with the Antimony compiler
                    # so both simulators agree on the same circuit.
                    k_d, hill_n = resolve_edge_params(
                        CircuitEdge(
                            source_id=src_id,
                            target_id=nid,
                            interaction_type=edge_data["interaction_type"],
                            K_d=edge_data.get("K_d"),
                            n=edge_data.get("n"),
                        ),
                        target=target_components.get(nid),
                    )
                    hill = regulation_factor_term(
                        edge_data["interaction_type"], src_conc, k_d, hill_n
                    )
                    if hill is not None:
                        regulation_factor *= hill

                production_rate = y_min + (y_max - y_min) * regulation_factor
                degradation_term = deg * current_conc
                dydt[idx] = production_rate - degradation_term

            return dydt

        # Solve ODE using SciPy solve_ivp
        t_eval = np.linspace(params.t_start, params.t_end, params.num_points)

        try:
            sol = solve_ivp(
                fun=ode_system,
                t_span=(params.t_start, params.t_end),
                y0=y0,
                method=params.solver_method,
                t_eval=t_eval,
                rtol=params.rtol,
                atol=params.atol,
            )

            if not sol.success:
                return SimulationResult(
                    status_message=f"ODE Solver failed: {sol.message}", success=False
                )

            # Label traces by the component's display label — its name, plus the
            # source organism where the part declares one — and fall back to the
            # id where two components would label identically, otherwise one
            # trace silently overwrites the other.
            name_counts: dict[str, int] = {}
            for nid in node_ids:
                nm = graph.nodes[nid]["label"]
                name_counts[nm] = name_counts.get(nm, 0) + 1

            species_dict: dict[str, list[float]] = {}
            for idx, nid in enumerate(node_ids):
                comp_label = graph.nodes[nid]["label"]
                label = (
                    comp_label if name_counts.get(comp_label, 0) == 1 else f"{comp_label} ({nid})"
                )
                species_dict[label] = sol.y[idx].tolist()

            return SimulationResult(
                time_points=sol.t.tolist(),
                species_concentrations=species_dict,
                status_message="Simulation completed successfully",
                success=True,
            )
        except Exception as ex:
            return SimulationResult(
                status_message=f"Simulation Exception: {str(ex)}", success=False
            )
