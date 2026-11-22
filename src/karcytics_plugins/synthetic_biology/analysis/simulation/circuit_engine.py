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
from ..provenance import CONVENTION, SOURCED, Provenance
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
            "threshold of n = 2.4514, nor the preset's n = 3.5, which is above "
            "the cooperativity the real repressors provide. Both are properties "
            "of the reduction."
        ),
    ),
}


#: Where each number in ``create_preset_repressilator`` comes from. The split
#: that matters for citing this tool: y_min/y_max are Cello UCF output levels,
#: while K_d, n, gamma and the initial conditions are chosen - and for the
#: chosen ones, this records the constraint they were chosen to satisfy rather
#: than leaving a reader to assume they were measured.
PRESET_PROVENANCE: dict[str, Provenance] = {
    "y_min": Provenance(
        kind=SOURCED,
        explanation=(
            "0.001 RPU basal output. Relative promoter units as defined by the "
            "Cello UCF, whose signal_carrier_units is RPU; the leakiness floor "
            "is the UCF's own order of magnitude for a repressed promoter."
        ),
    ),
    "y_max": Provenance(
        kind=SOURCED,
        explanation=(
            "10.0 RPU fully derepressed output, a Cello UCF output level. Now "
            "that production is scaled by the degradation rate this is also "
            "the level a fully derepressed gene settles at, which is the "
            "invariant the unit fix restored."
        ),
    ),
    "K_d": Provenance(
        kind=CONVENTION,
        explanation=(
            "1.0 RPU. Chosen, not measured: it sets the repression midpoint at "
            "the same scale as y_max so the ring operates on the steep part of "
            "its Hill curve, where the demo is legible. The oscillation "
            "criterion does not depend on it - sup(loop gain) = n for every "
            "K_d - so it trades no scientific claim for that legibility."
        ),
    ),
    "n": Provenance(
        kind=CONVENTION,
        explanation=(
            "3.5, chosen to sit 42.8% above this reduced model's Hopf "
            "threshold of 2.4514 so the limit cycle is visibly sustained "
            "across a 400-min window. Above the ~2 that LacI, TetR and cI "
            "actually provide: a three-node protein-only ring cannot oscillate "
            "at any parameters unless n > 2, so no physiological value would "
            "work here. Stated rather than hidden."
        ),
        mechanism=("elowitz2000",),
        mechanism_claim=(
            "Elowitz & Leibler (2000) establish that the three-gene repressor "
            "ring oscillates, which is why a Hill coefficient exists to tune "
            "at all. They do not supply this value: their model carries an "
            "mRNA species whose transcription-translation lag provides phase "
            "margin that this reduction replaces with extra cooperativity. The "
            "paper supports the existence of the oscillation, not n = 3.5."
        ),
    ),
    "degradation_rate": Provenance(
        kind=CONVENTION,
        explanation=(
            "0.2 min^-1, a ~3.5-min protein half-life. Chosen to set the "
            "timescale: it now sets the period (27.8 min at n = 3.5) without "
            "moving the Hopf threshold, because scaling production by gamma "
            "removes gamma from the loop gain entirely."
        ),
    ),
    "initial_concentration": Provenance(
        kind=CONVENTION,
        explanation=(
            "5.0 / 0.1 / 0.1 RPU. Chosen asymmetric on purpose: the symmetric "
            "fixed point is an equilibrium, so equal initial values sit on it "
            "and nothing oscillates however high n is. The asymmetry is what "
            "perturbs the system off that point."
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
        species per gene: production is a Hill function of the upstream
        repressor applied directly to the protein, scaled by the degradation
        rate so a gene settles at the output level its Cello parameters
        describe. The mRNA stage and its delay are absent.

        That reduction is deliberate and common, but it is a different
        dynamical system, and the difference is measurable here. Do not read
        the numbers below as reproducing the paper.

        Why n = 3.5, and why that is a finding rather than a tuning
        ----------------------------------------------------------
        For a symmetric three-node ring the loop gain is ``|f'(P*)|`` at the
        symmetric fixed point ``P* = f(P*)``, and the cycle is unstable - it
        oscillates - exactly when that gain exceeds 2. Writing
        ``u = (P*/K_d)^n``, ``m = y_min`` and ``D = y_max - y_min``:

            gain = D * n * u / [ (1 + u) * (m * (1 + u) + D) ]

        which is bounded above by ``n * u / (1 + u) < n``, approached as
        ``y_min -> 0`` and ``K_d -> 0``. So

            **sup(loop gain) over every K_d, y_max and y_min = n, exactly.**

        A three-node protein-only ring therefore **cannot oscillate at any
        parameter choice unless n > 2**. Confirmed numerically to six decimal
        places over a grid in all three parameters.

        Measured Hill coefficients for LacI, TetR and lambda cI are all around
        2. **This reduced model consequently cannot oscillate at physiological
        cooperativity**, and n = 3.5 is above what the real repressors supply.
        That is a property of the reduction, not of the biology, and it is the
        quantitative reason Elowitz & Leibler carry an mRNA species: the
        transcription-translation lag buys the phase margin that extra
        cooperativity is standing in for here. A preset that silently used
        non-physiological cooperativity to make a demo oscillate would make
        this tool unciteable, so it is stated instead.

        The numbers
        -----------
        With production scaled by gamma, the analytic Hopf threshold for this
        preset is **n* = 2.4514** (root of ``loop gain = 2``; it was 2.1484
        before the scaling, which is the figure the H-1 note quoted). Measured
        on this engine over a 400-min window, LacI peak-to-trough amplitude in
        the first third versus the last:

            n = 3.5   7.208 -> 6.439 RPU   89% retained, period 27.8 min
                      sustained; +42.8% above n*
            n = 2.0   4.023 -> 0.000 RPU   damps to flat
                      -18.4% below n*, and at the hard bound above

        Both margins exceed 15%. n = 2.2 was rejected: it damps, but sits only
        10.3% below the threshold. Note the finite-time threshold is higher
        than the analytic one - bisecting "still oscillating after 400 min"
        against this engine gives n = 2.6572, because just above n* the growth
        rate is too small to show inside the plotted window. Both figures are
        correct; they answer different questions, and a demo needs the
        finite-time one.

        Method, so this is reproducible: amplitude is peak-to-trough of the
        LacI trace over the first and last third of ``t_end = 400`` min at
        1600 points; period is the mean peak-to-peak spacing over the last
        half; the threshold is ``brentq`` on ``loop gain - 2`` using the
        analytic derivative above, cross-checked by bisection on the engine.
        See ``PRESET_PROVENANCE`` for where each parameter came from.
        """
        tetR = CircuitComponent(  # noqa: N806
            id="TetR",
            name="TetR Repressor",
            component_type="cds",
            y_min=0.001,
            y_max=10.0,
            K_d=1.0,
            n=3.5,
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
            n=3.5,
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
            n=3.5,
            degradation_rate=0.2,
            initial_concentration=0.1,
        )

        edges = [
            CircuitEdge(
                source_id="TetR",
                target_id="LacI",
                interaction_type="repression",
                K_d=1.0,
                n=3.5,
            ),
            CircuitEdge(
                source_id="LacI",
                target_id="cI",
                interaction_type="repression",
                K_d=1.0,
                n=3.5,
            ),
            CircuitEdge(
                source_id="cI",
                target_id="TetR",
                interaction_type="repression",
                K_d=1.0,
                n=3.5,
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
        d[P_i]/dt = gamma_i * (y_i([R], [A]) - [P_i])
        where
        y_i = y_min + (y_max - y_min) * Prod_repressors(1 / (1 + (R_j/K_d)^n))
                                      * Prod_activators((A_k/K_d)^n / (1 + (A_k/K_d)^n))

        Production is scaled by the degradation rate gamma, so the steady state
        of a gene is the output level y its Cello parameters describe:
        [P_i]* = y_i, in RPU. Without that scaling [P_i]* = y_i / gamma_i,
        which is RPU x min and not what any axis in this application claims to
        show. The returned :class:`SimulationResult` carries its own ``unit``.
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

                # Production is scaled by the degradation rate, so the fixed
                # point is the promoter's own output level: [P]* = y, in RPU.
                # Unscaled this read [P]* = y / gamma, i.e. RPU x min, while
                # four axes called it RPU -- the category error that let this
                # preset peak at 24.5 on an axis whose promoters cap at 10.
                # See analysis/units.py. Scaling moves the Hopf threshold
                # (2.1484 -> 2.4514 for a symmetric 3-ring) because it changes
                # the Jacobian; the preset below is retuned for the new one.
                target_level = y_min + (y_max - y_min) * regulation_factor
                dydt[idx] = deg * (target_level - current_conc)

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
