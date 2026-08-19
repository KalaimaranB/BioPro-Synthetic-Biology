"""Predictive Genetic Circuit Simulation Engine.

Architects network topology using NetworkX.DiGraph and compiles dynamic system ODEs
solved using scipy.integrate.solve_ivp for Hill kinetics, logic gates, and oscillators.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import networkx as nx
import numpy as np
from scipy.integrate import solve_ivp

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)


class CircuitSimulationEngine:
    """Core domain service for compiling and solving kinetic genetic circuit
    differential equations.
    """

    @classmethod
    def build_circuit_graph(
        cls,
        components: List[CircuitComponent],
        edges: List[CircuitEdge],
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
            )

        for edge in edges:
            graph.add_edge(
                edge.source_id,
                edge.target_id,
                interaction_type=edge.interaction_type,
                strength=edge.strength,
            )

        return graph

    @classmethod
    def create_preset_repressilator(
        cls,
    ) -> Tuple[List[CircuitComponent], List[CircuitEdge]]:
        """Constructs Elowitz & Leibler (2000) 3-gene Repressilator ring oscillator
        network.
        """
        tetR = CircuitComponent(
            id="TetR",
            name="TetR Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.1,
            degradation_rate=0.2,
            initial_concentration=5.0,
        )
        lacI = CircuitComponent(
            id="LacI",
            name="LacI Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.1,
            degradation_rate=0.2,
            initial_concentration=0.1,
        )
        cI = CircuitComponent(
            id="cI",
            name="cI Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=2.1,
            degradation_rate=0.2,
            initial_concentration=0.1,
        )

        edges = [
            CircuitEdge(
                source_id="TetR", target_id="LacI", interaction_type="repression"
            ),
            CircuitEdge(
                source_id="LacI", target_id="cI", interaction_type="repression"
            ),
            CircuitEdge(
                source_id="cI", target_id="TetR", interaction_type="repression"
            ),
        ]

        return [tetR, lacI, cI], edges

    @classmethod
    def simulate_circuit(
        cls,
        components: List[CircuitComponent],
        edges: List[CircuitEdge],
        params: Optional[SimulationParameters] = None,
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

        y0 = np.array(
            [graph.nodes[nid]["initial_concentration"] for nid in node_ids], dtype=float
        )

        def ode_system(t: float, y: np.ndarray) -> np.ndarray:
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
                    itype = edge_data["interaction_type"].lower()
                    K_d = node_data["K_d"]
                    n = node_data["n"]

                    if itype == "repression":
                        # Negative Hill function: 1 / (1 + (R / K_d)^n)
                        hill = 1.0 / (1.0 + (src_conc / max(1e-6, K_d)) ** n)
                        regulation_factor *= hill
                    elif itype == "activation":
                        # Positive Hill function: (A / K_d)^n / (1 + (A / K_d)^n)
                        ratio = (src_conc / max(1e-6, K_d)) ** n
                        hill = ratio / (1.0 + ratio)
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

            species_dict: Dict[str, List[float]] = {}
            for idx, nid in enumerate(node_ids):
                comp_name = graph.nodes[nid]["name"]
                species_dict[comp_name] = sol.y[idx].tolist()

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
