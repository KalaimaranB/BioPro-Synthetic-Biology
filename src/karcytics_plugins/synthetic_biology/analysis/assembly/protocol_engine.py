"""Protocol Calculation Engine for Synthetic Biology Assembly (Phase 2 Build Cycle).

Automates bench calculations for Gibson Assembly and Golden Gate Assembly,
including master mix preparation tables, insert-to-vector molar ratios,
pipetting volume validation against physical thresholds (>= 0.5 uL), and
thermal cycler programs formatted for PyQt6 GUI display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class PipettingVolumeError(ValueError):
    """Custom exception raised when a calculated pipetting volume is below the physical
    manual pipetting limit (0.5 uL).
    """

    def __init__(
        self, component_name: str, volume_ul: float, min_threshold_ul: float = 0.5
    ):
        self.component_name = component_name
        self.volume_ul = volume_ul
        self.min_threshold_ul = min_threshold_ul
        message = (
            f"Calculated volume for '{component_name}' ({volume_ul:.3f} µL) is below "
            f"the minimum manual pipetting threshold of {min_threshold_ul:.2f} µL. "
            "Please dilute stock concentration or scale up reaction volume."
        )
        super().__init__(message)


class AssemblyProtocolError(ValueError):
    """Custom exception raised for invalid assembly parameters or reaction capacity
    overflow.
    """

    pass


# Minimum physical volume for standard manual micropipettes (P2 / P10)
MIN_PIPETTING_VOLUME_UL: float = 0.5


@dataclass
class MasterMixResult:
    """Structured master mix calculation result formatted for PyQt6 tables."""

    assembly_type: str
    num_reactions: int
    overage_pct: float
    multiplier: float
    reaction_volume_ul: float
    component_volumes_per_rxn: Dict[str, float]
    master_mix_volumes_total: Dict[str, float]
    total_master_mix_volume_ul: float
    pipetting_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the MasterMixResult into a dictionary for PyQt6 UI models."""
        return {
            "assembly_type": self.assembly_type,
            "num_reactions": self.num_reactions,
            "overage_pct": self.overage_pct,
            "multiplier": round(self.multiplier, 3),
            "reaction_volume_ul": round(self.reaction_volume_ul, 2),
            "component_volumes_per_rxn": {
                k: round(v, 3) for k, v in self.component_volumes_per_rxn.items()
            },
            "master_mix_volumes_total": {
                k: round(v, 3) for k, v in self.master_mix_volumes_total.items()
            },
            "total_master_mix_volume_ul": round(self.total_master_mix_volume_ul, 2),
            "pipetting_warnings": self.pipetting_warnings,
        }


@dataclass
class FragmentPipettingSpec:
    """Pipetting specification for a single DNA fragment (vector or insert)."""

    name: str
    role: str  # 'vector' or 'insert'
    length_bp: int
    concentration_ng_ul: float
    molar_ratio: float
    target_mass_ng: float
    volume_ul: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "length_bp": self.length_bp,
            "concentration_ng_ul": round(self.concentration_ng_ul, 2),
            "molar_ratio": round(self.molar_ratio, 2),
            "target_mass_ng": round(self.target_mass_ng, 2),
            "volume_ul": round(self.volume_ul, 3),
        }


@dataclass
class ReactionRatioResult:
    """Structured reaction molar ratio calculation result for GUI consumption."""

    assembly_type: str
    vector_spec: FragmentPipettingSpec
    insert_specs: List[FragmentPipettingSpec]
    total_dna_volume_ul: float
    master_mix_volume_ul: float
    water_volume_ul: float
    total_reaction_volume_ul: float
    pipetting_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the ReactionRatioResult into a dictionary payload for PyQt6."""
        return {
            "assembly_type": self.assembly_type,
            "vector_spec": self.vector_spec.to_dict(),
            "insert_specs": [spec.to_dict() for spec in self.insert_specs],
            "total_dna_volume_ul": round(self.total_dna_volume_ul, 3),
            "master_mix_volume_ul": round(self.master_mix_volume_ul, 2),
            "water_volume_ul": round(self.water_volume_ul, 3),
            "total_reaction_volume_ul": round(self.total_reaction_volume_ul, 2),
            "pipetting_warnings": self.pipetting_warnings,
        }


@dataclass
class ThermalCyclerStep:
    """Represents a single thermal cycler incubation step."""

    step_number: int
    description: str
    temperature_c: float
    duration_seconds: int
    cycles: int = 1

    def to_dict(self) -> Dict[str, Any]:
        mins, secs = divmod(self.duration_seconds, 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        return {
            "step_number": self.step_number,
            "description": self.description,
            "temperature_c": self.temperature_c,
            "duration_seconds": self.duration_seconds,
            "duration_formatted": time_str,
            "cycles": self.cycles,
        }


@dataclass
class BenchProtocol:
    """Complete bench protocol data payload ready for PyQt6 visual rendering."""

    protocol_name: str
    assembly_type: str
    num_reactions: int
    master_mix: MasterMixResult
    reaction_ratio: ReactionRatioResult
    thermal_program: List[ThermalCyclerStep]
    instructions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_name": self.protocol_name,
            "assembly_type": self.assembly_type,
            "num_reactions": self.num_reactions,
            "master_mix": self.master_mix.to_dict(),
            "reaction_ratio": self.reaction_ratio.to_dict(),
            "thermal_program": [step.to_dict() for step in self.thermal_program],
            "instructions": self.instructions,
        }


class ProtocolEngine:
    """Core computational engine automating bench assembly protocols for synthetic
    biology. Supports Gibson Assembly (isothermal 50°C exonuclease-polymerase-ligase)
    and Golden Gate Assembly (restriction endonuclease-ligase thermocycling).
    """

    # Default master mix recipes per reaction (in uL for a 20 uL standard reaction)
    DEFAULT_GIBSON_RECIPE: Dict[str, float] = {
        "Gibson Assembly 2X Master Mix": 10.0,
    }

    DEFAULT_GOLDEN_GATE_RECIPE: Dict[str, float] = {
        "10X T4 DNA Ligase Buffer": 2.0,
        "Restriction Enzyme (BsaI/BsmBI)": 1.0,
        "T4 DNA Ligase (400 U/µL)": 1.0,
        "Nuclease-Free Water": 6.0,
    }

    def __init__(self, min_pipetting_ul: float = MIN_PIPETTING_VOLUME_UL) -> None:
        """Initializes the ProtocolEngine.

        Args:
            min_pipetting_ul: Minimum allowable manual pipetting threshold in uL.
        """
        self.min_pipetting_ul = min_pipetting_ul

    def calculate_master_mix(
        self,
        num_reactions: int,
        overage_pct: float = 10.0,
        assembly_type: str = "Gibson",
        reaction_volume_ul: float = 20.0,
        custom_recipe: Optional[Dict[str, float]] = None,
    ) -> MasterMixResult:
        """Calculates exact master mix component volumes including overage percentage.

        Args:
            num_reactions: Number of experimental reactions to prepare.
            overage_pct: Extra allowance for loss (default 10.0%).
            assembly_type: 'Gibson' or 'GoldenGate' (case-insensitive).
            reaction_volume_ul: Total reaction volume in uL (default 20.0 uL).
            custom_recipe: Optional custom recipe dict specifying component -> uL.

        Returns:
            MasterMixResult object containing per-reaction and total volumes.

        Raises:
            AssemblyProtocolError: If inputs are non-positive or invalid.
            PipettingVolumeError: If calculated volume is below physical threshold.
        """
        if num_reactions <= 0:
            raise AssemblyProtocolError(
                f"Number of reactions must be a positive integer (got {num_reactions})."
            )
        if overage_pct < 0:
            raise AssemblyProtocolError(
                f"Overage percentage cannot be negative (got {overage_pct})."
            )
        if reaction_volume_ul <= 0:
            raise AssemblyProtocolError(
                f"Reaction volume must be positive (got {reaction_volume_ul})."
            )

        norm_type = assembly_type.strip().lower()
        if custom_recipe is not None:
            per_rxn_recipe = dict(custom_recipe)
        elif "golden" in norm_type or "gate" in norm_type:
            per_rxn_recipe = dict(self.DEFAULT_GOLDEN_GATE_RECIPE)
        else:
            per_rxn_recipe = dict(self.DEFAULT_GIBSON_RECIPE)

        multiplier = num_reactions * (1.0 + (overage_pct / 100.0))
        total_volumes: Dict[str, float] = {}
        warnings: List[str] = []

        for component, vol_per_rxn in per_rxn_recipe.items():
            if vol_per_rxn < 0:
                raise AssemblyProtocolError(
                    f"Component '{component}' volume cannot be negative."
                )
            if vol_per_rxn < self.min_pipetting_ul and vol_per_rxn > 0:
                raise PipettingVolumeError(
                    component_name=f"{component} (per rxn)",
                    volume_ul=vol_per_rxn,
                    min_threshold_ul=self.min_pipetting_ul,
                )

            tot_vol = vol_per_rxn * multiplier
            if tot_vol < self.min_pipetting_ul and tot_vol > 0:
                raise PipettingVolumeError(
                    component_name=f"{component} (total master mix)",
                    volume_ul=tot_vol,
                    min_threshold_ul=self.min_pipetting_ul,
                )
            total_volumes[component] = tot_vol

        sum_master_mix = sum(total_volumes.values())

        display_type = (
            "Golden Gate Assembly"
            if "golden" in norm_type or "gate" in norm_type
            else "Gibson Assembly"
        )

        return MasterMixResult(
            assembly_type=display_type,
            num_reactions=num_reactions,
            overage_pct=overage_pct,
            multiplier=multiplier,
            reaction_volume_ul=reaction_volume_ul,
            component_volumes_per_rxn=per_rxn_recipe,
            master_mix_volumes_total=total_volumes,
            total_master_mix_volume_ul=sum_master_mix,
            pipetting_warnings=warnings,
        )

    def calculate_insert_to_vector_ratio(
        self,
        vector_bp: int,
        vector_conc_ng_ul: float,
        inserts: List[Dict[str, Any]],
        default_molar_ratio: float = 3.0,
        vector_mass_ng: float = 50.0,
        reaction_volume_ul: float = 20.0,
        master_mix_volume_ul: float = 10.0,
        vector_name: str = "Destination Vector",
        assembly_type: str = "Gibson",
    ) -> ReactionRatioResult:
        """Calculates molar ratios and exact pipetting volumes for vector and insert
        DNA fragments.

        Standard Molar Equation:
            mass_insert = ratio * mass_vector * (length_insert / length_vector)
            volume = mass / concentration

        Args:
            vector_bp: Length of vector plasmid backbone in base pairs.
            vector_conc_ng_ul: Concentration of vector stock in ng/uL.
            inserts: List of insert dicts (name, length_bp, conc, molar_ratio).
            default_molar_ratio: Molar insert:vector ratio if unspecified (3.0 for 3:1).
            vector_mass_ng: Fixed target mass of vector DNA in ng (default 50.0 ng).
            reaction_volume_ul: Total reaction volume in uL (default 20.0 uL).
            master_mix_volume_ul: Volume of master mix per reaction (default 10.0 uL).
            vector_name: Display label for vector fragment.
            assembly_type: 'Gibson' or 'GoldenGate'.

        Returns:
            ReactionRatioResult containing FragmentPipettingSpec for vector & inserts,
            total DNA volume, and required water balance.

        Raises:
            AssemblyProtocolError: If inputs invalid or total DNA exceeds capacity.
            PipettingVolumeError: If calculated volume of vector or insert is < 0.5 uL.
        """
        # Validate Vector inputs
        if vector_bp <= 0:
            raise AssemblyProtocolError(
                f"Vector length must be positive base pairs (got {vector_bp})."
            )
        if vector_conc_ng_ul <= 0:
            raise AssemblyProtocolError(
                f"Vector concentration must be positive ng/µL "
                f"(got {vector_conc_ng_ul})."
            )
        if vector_mass_ng <= 0:
            raise AssemblyProtocolError(
                f"Vector target mass must be positive ng (got {vector_mass_ng})."
            )
        if not inserts:
            raise AssemblyProtocolError(
                "At least one insert DNA fragment must be provided."
            )

        # Calculate Vector Volume
        vector_vol = vector_mass_ng / vector_conc_ng_ul
        if vector_vol < self.min_pipetting_ul:
            raise PipettingVolumeError(
                component_name=f"Vector '{vector_name}'",
                volume_ul=vector_vol,
                min_threshold_ul=self.min_pipetting_ul,
            )

        vector_spec = FragmentPipettingSpec(
            name=vector_name,
            role="vector",
            length_bp=vector_bp,
            concentration_ng_ul=vector_conc_ng_ul,
            molar_ratio=1.0,
            target_mass_ng=vector_mass_ng,
            volume_ul=vector_vol,
        )

        insert_specs: List[FragmentPipettingSpec] = []
        warnings: List[str] = []

        # Process Inserts
        for idx, ins in enumerate(inserts):
            name = str(ins.get("name", f"Insert_{idx + 1}"))
            ins_bp = int(ins.get("length_bp", 0))
            ins_conc = float(ins.get("concentration_ng_ul", 0.0))
            ratio = float(ins.get("molar_ratio", default_molar_ratio))

            if ins_bp <= 0:
                raise AssemblyProtocolError(
                    f"Insert '{name}' length_bp must be positive (got {ins_bp})."
                )
            if ins_conc <= 0:
                raise AssemblyProtocolError(
                    f"Insert '{name}' concentration_ng_ul must be positive "
                    f"(got {ins_conc})."
                )
            if ratio <= 0:
                raise AssemblyProtocolError(
                    f"Insert '{name}' molar_ratio must be positive (got {ratio})."
                )

            # mass_insert = ratio * mass_vector * (length_insert / length_vector)
            target_mass = ratio * vector_mass_ng * (float(ins_bp) / float(vector_bp))
            ins_vol = target_mass / ins_conc

            if ins_vol < self.min_pipetting_ul:
                raise PipettingVolumeError(
                    component_name=f"Insert '{name}'",
                    volume_ul=ins_vol,
                    min_threshold_ul=self.min_pipetting_ul,
                )

            insert_specs.append(
                FragmentPipettingSpec(
                    name=name,
                    role="insert",
                    length_bp=ins_bp,
                    concentration_ng_ul=ins_conc,
                    molar_ratio=ratio,
                    target_mass_ng=target_mass,
                    volume_ul=ins_vol,
                )
            )

        total_dna_vol = vector_vol + sum(s.volume_ul for s in insert_specs)
        available_vol = reaction_volume_ul - master_mix_volume_ul

        if total_dna_vol > available_vol:
            raise AssemblyProtocolError(
                f"Total calculated DNA volume ({total_dna_vol:.2f} µL) exceeds "
                f"reaction capacity ({available_vol:.2f} µL available in a "
                f"{reaction_volume_ul:.1f} µL reaction with {master_mix_volume_ul:.1f} "
                "µL master mix). Please concentrate your DNA stocks."
            )

        water_vol = available_vol - total_dna_vol
        if water_vol < self.min_pipetting_ul and water_vol > 0:
            warnings.append(
                f"Water volume ({water_vol:.3f} µL) is under 0.5 µL. "
                "Consider omitting water."
            )
            water_vol = 0.0

        norm_type = (
            "Golden Gate Assembly"
            if "golden" in assembly_type.lower() or "gate" in assembly_type.lower()
            else "Gibson Assembly"
        )

        return ReactionRatioResult(
            assembly_type=norm_type,
            vector_spec=vector_spec,
            insert_specs=insert_specs,
            total_dna_volume_ul=total_dna_vol,
            master_mix_volume_ul=master_mix_volume_ul,
            water_volume_ul=water_vol,
            total_reaction_volume_ul=reaction_volume_ul,
            pipetting_warnings=warnings,
        )

    def generate_bench_protocol(
        self,
        num_reactions: int,
        vector_bp: int,
        vector_conc_ng_ul: float,
        inserts: List[Dict[str, Any]],
        assembly_type: str = "Gibson",
        overage_pct: float = 10.0,
        vector_mass_ng: float = 50.0,
        default_molar_ratio: float = 3.0,
        reaction_volume_ul: float = 20.0,
    ) -> BenchProtocol:
        """Generates a complete, step-by-step laboratory bench protocol payload.

        Combines Master Mix preparation, insert:vector pipetting tables, thermal
        cycler programs, and bench execution instructions.

        Args:
            num_reactions: Number of assembly reactions to prepare.
            vector_bp: Length of vector backbone in base pairs.
            vector_conc_ng_ul: Concentration of vector stock in ng/uL.
            inserts: List of insert fragment specifications.
            assembly_type: 'Gibson' or 'GoldenGate'.
            overage_pct: Master mix overage percentage.
            vector_mass_ng: Vector target mass in ng.
            default_molar_ratio: Default insert:vector molar ratio.
            reaction_volume_ul: Reaction volume in uL.

        Returns:
            BenchProtocol object serialized and ready for PyQt6 GUI layout rendering.
        """
        is_golden = "golden" in assembly_type.lower() or "gate" in assembly_type.lower()
        disp_type = "Golden Gate Assembly" if is_golden else "Gibson Assembly"

        # 1. Master Mix
        mm_result = self.calculate_master_mix(
            num_reactions=num_reactions,
            overage_pct=overage_pct,
            assembly_type=disp_type,
            reaction_volume_ul=reaction_volume_ul,
        )

        # 2. Reaction Ratio
        mm_vol_per_rxn = (
            mm_result.component_volumes_per_rxn.get(
                "Gibson Assembly 2X Master Mix", 10.0
            )
            if not is_golden
            else sum(mm_result.component_volumes_per_rxn.values())
        )

        ratio_result = self.calculate_insert_to_vector_ratio(
            vector_bp=vector_bp,
            vector_conc_ng_ul=vector_conc_ng_ul,
            inserts=inserts,
            default_molar_ratio=default_molar_ratio,
            vector_mass_ng=vector_mass_ng,
            reaction_volume_ul=reaction_volume_ul,
            master_mix_volume_ul=mm_vol_per_rxn,
            assembly_type=disp_type,
        )

        # 3. Thermal Program
        if is_golden:
            thermal_program = [
                ThermalCyclerStep(
                    1, "Restriction & Ligation Cycles", 37.0, 180, cycles=30
                ),
                ThermalCyclerStep(2, "Ligation Shift", 16.0, 240, cycles=30),
                ThermalCyclerStep(3, "Final Ligation", 50.0, 300, cycles=1),
                ThermalCyclerStep(4, "Heat Inactivation", 80.0, 300, cycles=1),
                ThermalCyclerStep(5, "Hold", 4.0, 0, cycles=1),
            ]
        else:
            thermal_program = [
                ThermalCyclerStep(
                    1,
                    "Isothermal Exonuclease/Ligation Incubation",
                    50.0,
                    3600,
                    cycles=1,
                ),
                ThermalCyclerStep(2, "Hold", 4.0, 0, cycles=1),
            ]

        # 4. Instructions
        v_vol_str = f"{ratio_result.vector_spec.volume_ul:.2f}"
        w_vol_str = f"{ratio_result.water_volume_ul:.2f}"
        rxn_vol_str = f"{reaction_volume_ul:.1f}"

        instructions = [
            "1. Thaw all reagents on ice and vortex gently before use.",
            f"2. Prepare Master Mix for {num_reactions} reaction(s) "
            f"(+{overage_pct}% overage) according to the Master Mix table.",
            "3. Aliquot calculated Master Mix volume into PCR tube(s).",
            f"4. Add vector DNA ({v_vol_str} µL) and insert DNA to each tube "
            "according to the Pipetting Table.",
            f"5. Add Nuclease-Free Water ({w_vol_str} µL) to bring total reaction "
            f"volume to {rxn_vol_str} µL.",
            "6. Mix reaction by gentle pipetting, microcentrifuge briefly, and "
            "place in thermal cycler.",
            f"7. Execute the thermal cycler program for {disp_type}.",
            "8. Proceed directly to transformation or store reaction at -20°C.",
        ]

        return BenchProtocol(
            protocol_name=f"{disp_type} Bench Protocol",
            assembly_type=disp_type,
            num_reactions=num_reactions,
            master_mix=mm_result,
            reaction_ratio=ratio_result,
            thermal_program=thermal_program,
            instructions=instructions,
        )
