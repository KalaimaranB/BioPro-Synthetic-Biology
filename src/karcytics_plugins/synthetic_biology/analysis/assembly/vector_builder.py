"""Vector Assembly Engine & Automated Primer Design Algorithm.

Utilizes Biopython (Bio.Seq, Bio.SeqRecord, Bio.SeqIO) for parsing
GenBank/FASTA files, stitching genetic components into a plasmid vector,
mapping features, and designing primers.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import replace
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from Bio.SeqUtils import MeltingTemp

from ..models.domain import GeneticFeature, PlasmidVector, Primer
from ..parts.base import BiologicalPart
from ..sequence_input import require_sequence
from .primer_rubric import PrimerRubric
from .primer_screen import (
    RubricCheck,
    gc_percent,
    product_length,
    score,
    screen_pair,
    screen_primer,
    summarise,
)


def _coverage_note(trimmed_5p: int, trimmed_3p: int, product_bp: int) -> str:
    """Say so when the best pair does not span the whole target.

    Returning a shorter product without saying anything is how a student ends
    up cloning a construct missing its start codon. The note names how much
    came off each end and what the product actually is, so the choice to
    accept it or to relax the limits is theirs.
    """
    if not trimmed_5p and not trimmed_3p:
        return ""
    return (
        "No acceptable primers at the exact target ends; best pair gives "
        f"{product_bp} bp, trimming {trimmed_5p} bp at 5' and {trimmed_3p} bp "
        "at 3'. Turn on \u201ckeep the whole target\u201d to force the ends, "
        "or relax the Tm and rubric limits."
    )


class MissingPartSequenceError(ValueError):
    """Raised when a part carries no DNA sequence and so cannot be assembled.

    Substituting a placeholder would silently shift every downstream feature
    coordinate, so assembly stops instead.
    """

    def __init__(self, part_name: str, part_id: str):
        self.part_name = part_name
        self.part_id = part_id
        super().__init__(
            f"Part '{part_name}' ({part_id}) has no DNA sequence. "
            "Import or enter its sequence before assembling the construct."
        )


class VectorAssemblyEngine:
    """Core domain service for sequence file parsing, vector construction,
    and primer design.
    """

    @staticmethod
    def parse_sequence_file(file_content: str, file_format: str = "genbank") -> PlasmidVector:
        """Parses FASTA or GenBank sequence content using Biopython.

        Args:
            file_content: Text string content of FASTA or GenBank file.
            file_format: 'genbank', 'gb', 'fasta', or 'fa'.

        Returns:
            PlasmidVector domain object with mapped features and full sequence.
        """
        fmt = file_format.lower()
        biopython_fmt = "fasta" if fmt in ["fa", "fasta"] else "genbank"

        handle = io.StringIO(file_content)
        record: SeqRecord = SeqIO.read(handle, biopython_fmt)

        sequence_str = str(record.seq).upper()
        features: list[GeneticFeature] = []

        # Color map by feature type
        type_color_map = {
            "promoter": "#E11D48",  # Vibrant Red
            "cds": "#2563EB",  # Royal Blue
            "rbs": "#059669",  # Emerald Green
            "terminator": "#7C3AED",  # Purple
            "origin": "#D97706",  # Amber
            "gene": "#2563EB",
            "rep_origin": "#D97706",
        }

        if hasattr(record, "features"):
            for feat in record.features:
                ftype = feat.type.lower()
                fname = feat.qualifiers.get("label", feat.qualifiers.get("gene", [feat.type]))[0]
                strand_val = 1
                if (
                    hasattr(feat, "location")
                    and feat.location is not None
                    and feat.location.strand is not None
                ):
                    strand_val = feat.location.strand
                color = type_color_map.get(ftype, "#3B82F6")

                features.append(
                    GeneticFeature(
                        id=str(uuid.uuid4())[:8],
                        name=fname,
                        feature_type=ftype,
                        start=int(feat.location.start),
                        end=int(feat.location.end),
                        strand=strand_val,
                        sequence=sequence_str[int(feat.location.start) : int(feat.location.end)],
                        color=color,
                        qualifiers={k: list(v) for k, v in feat.qualifiers.items()},
                    )
                )

        # Check topology metadata
        is_circular = True
        if "topology" in record.annotations:
            is_circular = str(record.annotations["topology"]).lower() == "circular"

        return PlasmidVector(
            id=str(uuid.uuid4())[:8],
            name=record.name if record.name != "<unknown id>" else "Imported_Vector",
            description=record.description if record.description != "<unknown description>" else "",
            sequence=sequence_str,
            is_circular=is_circular,
            features=features,
        )

    @staticmethod
    def export_genbank(vector: PlasmidVector) -> str:
        """Exports PlasmidVector construct into standard GenBank format string
        using Biopython.
        """
        seq_obj = Seq(vector.sequence)
        record = SeqRecord(
            seq_obj,
            id=vector.id,
            name=vector.name[:16].replace(" ", "_"),
            description=vector.description or "Synthetic construct assembled with Karcytics",
        )
        record.annotations["molecule_type"] = "DNA"
        if vector.is_circular:
            record.annotations["topology"] = "circular"

        bio_features = []
        for feat in vector.features:
            strand_val = 1 if feat.strand >= 0 else -1
            bio_feat = SeqFeature(
                FeatureLocation(feat.start, feat.end, strand=strand_val),
                type=feat.feature_type,
                qualifiers={"label": [feat.name], "note": [f"Color: {feat.color}"]},
            )
            bio_features.append(bio_feat)

        record.features = bio_features
        handle = io.StringIO()
        SeqIO.write(record, handle, "genbank")
        return handle.getvalue()

    @staticmethod
    def assemble_vector(
        vector_name: str,
        parts: list[BiologicalPart],
        backbone_sequence: str = "",
        is_circular: bool = True,
    ) -> PlasmidVector:
        """Stitches ordered biological parts into a seamless PlasmidVector construct.

        Calculates exact boundary offsets and strand positions for all features.
        """
        type_color_map = {
            "promoter": "#E11D48",
            "cds": "#2563EB",
            "rbs": "#059669",
            "terminator": "#7C3AED",
            "insulator": "#0891B2",
            "sgrna": "#D97706",
        }

        current_offset = 0
        full_seq_builder = []
        features: list[GeneticFeature] = []

        if backbone_sequence:
            full_seq_builder.append(backbone_sequence.upper())
            current_offset += len(backbone_sequence)
            features.append(
                GeneticFeature(
                    id=str(uuid.uuid4())[:8],
                    name="Vector_Backbone",
                    feature_type="origin",
                    start=0,
                    end=current_offset,
                    strand=1,
                    sequence=backbone_sequence.upper(),
                    color="#64748B",
                )
            )

        for part in parts:
            if not part.sequence:
                raise MissingPartSequenceError(part.name, part.id)
            part_seq = part.sequence.upper()
            seq_len = len(part_seq)
            start_pos = current_offset
            end_pos = start_pos + seq_len

            full_seq_builder.append(part_seq)
            color = type_color_map.get(part.part_type, "#3B82F6")

            features.append(
                GeneticFeature(
                    id=part.id,
                    name=part.name,
                    feature_type=part.part_type,
                    start=start_pos,
                    end=end_pos,
                    strand=1,
                    sequence=part_seq,
                    color=color,
                )
            )
            current_offset = end_pos

        full_sequence = "".join(full_seq_builder)
        return PlasmidVector(
            id=str(uuid.uuid4())[:8],
            name=vector_name,
            description=f"Assembled plasmid containing {len(parts)} genetic parts",
            sequence=full_sequence,
            is_circular=is_circular,
            features=features,
        )

    @staticmethod
    def calculate_tm(
        sequence: str,
        na_conc_mm: float = 50.0,
        mg_conc_mm: float = 1.5,
        primer_conc_nm: float = 250.0,
    ) -> float:
        """Calculates nearest-neighbor melting temperature (Tm) for primer sequences
        using the Allawi & SantaLucia (1997) parameters (Biopython DNA_NN3) and the
        Owczarzy et al. (2008) magnesium-aware salt correction.

        Args:
            sequence: Primer DNA sequence string.
            na_conc_mm: Monovalent sodium concentration in mM (default 50.0 mM).
            mg_conc_mm: Divalent magnesium concentration in mM (default 1.5 mM).
            primer_conc_nm: Total primer concentration in nM (default 250.0 nM).

        Returns:
            Calculated melting temperature in degrees Celsius (°C).
        """
        seq = sequence.upper().strip()
        if not seq:
            return 0.0

        # For very short oligos (< 6 bp), nearest-neighbor models are non-physical;
        # return basic Wallace approximation
        if len(seq) < 6:  # noqa: PLR2004
            n_at = seq.count("A") + seq.count("T")
            n_gc = seq.count("G") + seq.count("C")
            return float(n_at * 2 + n_gc * 4)

        try:
            tm_val = MeltingTemp.Tm_NN(
                seq,
                nn_table=MeltingTemp.DNA_NN3,  # Allawi & SantaLucia (1997), per Biopython
                Na=na_conc_mm,
                Mg=mg_conc_mm,
                dnac1=primer_conc_nm,
                dnac2=primer_conc_nm,
                saltcorr=7,  # Owczarzy et al. (2008) salt correction
            )
            return round(float(tm_val), 2)
        except Exception:
            # Fallback for degenerate/unusual sequences
            n_at = seq.count("A") + seq.count("T")
            n_gc = seq.count("G") + seq.count("C")
            n_total = len(seq)
            if n_total <= 14:  # noqa: PLR2004
                return float(n_at * 2 + n_gc * 4)
            return round(float(64.9 + 41.0 * (n_gc - 16.4) / n_total), 2)

    # ── Primer design ──────────────────────────────────────────────────
    #
    # Two defects in the original implementation are fixed here, and both
    # changed reported numbers:
    #
    # 1. GC content was computed over the full oligo including the 5'
    #    restriction tail. A GAATTC tail is 50% GC and drags the figure toward
    #    50% regardless of what the annealing region actually is, so a primer
    #    could pass a 40-60% rubric on the strength of its tail. GC is now
    #    measured on the annealing region, and tail GC is reported separately.
    # 2. The forward primer was pinned to target[:n] and the reverse to
    #    target[-n:]. With no way to slide, a poor GC or clamp at the exact end
    #    of the target had no remedy. Candidates are now generated over a
    #    bounded offset window as well as a length window.
    #
    # Tm is unchanged: still computed on the annealing region only, before the
    # tail is concatenated, by `calculate_tm`.

    @staticmethod
    def _build_primer(  # noqa: PLR0913 - a private constructor for one Primer; each value is already decided by the caller
        name: str,
        direction: str,
        binding: str,
        overhang: str,
        target_tm: float,
        region: tuple[int, int],
        rubric: PrimerRubric,
    ) -> Primer:
        """One primer, screened, with its annealing region already decided."""
        overhang = overhang.upper()
        full = overhang + binding
        checks = screen_primer(full, overhang, rubric)
        by_name = {c.name: c for c in checks}

        def dg(check_name: str) -> float | None:
            check = by_name.get(check_name)
            if check is None or check.observed_value is None:
                return None
            return float(check.observed_value)

        return Primer(
            id=str(uuid.uuid4())[:8],
            name=name,
            sequence=full,
            direction=direction,
            target_tm=target_tm,
            calculated_tm=round(VectorAssemblyEngine.calculate_tm(binding), 2),
            gc_content=round(gc_percent(binding), 1),
            length=len(full),
            overhang=overhang,
            target_region=region,
            overhang_gc_content=round(gc_percent(overhang), 1) if overhang else None,
            annealing_length=len(binding),
            hairpin_dg=dg("hairpin"),
            self_dimer_dg=dg("self_dimer"),
            rubric_checks=[c.to_dict() for c in checks],
            rubric_verdict=str(summarise(checks)["verdict"]),
            rubric_name=rubric.name,
        )

    @classmethod
    def _build_primer_grid(  # noqa: PLR0913 - an internal split of one loop; every value is already a parameter of the caller
        cls,
        target: str,
        rubric: PrimerRubric,
        max_len: int,
        max_offset: int,
        fwd_overhang: str,
        rev_overhang: str,
        wanted_tm: float,
    ) -> tuple[list[Primer], list[Primer]]:
        """Every forward and reverse primer across the length x offset grid."""
        forwards: list[Primer] = []
        reverses: list[Primer] = []
        for offset in range(max_offset + 1):
            for length in range(rubric.min_length, max_len + 1):
                fwd_binding = target[offset : offset + length]
                if len(fwd_binding) == length:
                    forwards.append(
                        cls._build_primer(
                            "Forward_Primer",
                            "FWD",
                            fwd_binding,
                            fwd_overhang,
                            wanted_tm,
                            (offset, offset + length),
                            rubric,
                        )
                    )
                end = len(target) - offset
                rev_region = target[end - length : end]
                if len(rev_region) == length:
                    rev_binding = str(Seq(rev_region).reverse_complement())
                    reverses.append(
                        cls._build_primer(
                            "Reverse_Primer",
                            "REV",
                            rev_binding,
                            rev_overhang,
                            wanted_tm,
                            (end - length, end),
                            rubric,
                        )
                    )
        return forwards, reverses

    @classmethod
    def generate_primer_candidates(  # noqa: PLR0913 - each argument is a distinct, independent search setting; bundling them would only relocate the list
        cls,
        target_sequence: str,
        rubric: PrimerRubric | None = None,
        *,
        fwd_overhang: str = "",
        rev_overhang: str = "",
        target_tm: float | None = None,
        limit: int = 20,
        require_full_target: bool = False,
        max_pool: int = 24,
    ) -> list[dict[str, Any]]:
        """Rank primer pairs for ``target_sequence`` against ``rubric``.

        Searches both the length window and an offset window at each end, so a
        bad base composition at the exact end of the target is recoverable.

        Args:
            max_pool: How many forward and reverse primers to carry into the
                pairwise stage. Pairing is quadratic — every forward is
                screened against every reverse — so the full length x offset
                grid is 169x169 at the default rubric and takes about seven
                seconds. Each primer is therefore screened on its own first
                (which is linear), ranked, and only the best ``max_pool`` of
                each are paired. This is a heuristic: a pair whose members are
                individually mediocre but complementary could be missed. Raise
                it to search harder, or set ``max_offset=0`` to make the grid
                small enough that it does not matter.
            require_full_target: Keep only pairs whose product spans the whole
                target. Sliding the annealing start inward trims the ends off
                the amplicon, which is fine when amplifying a region but drops
                the start codon when amplifying an ORF to clone. A caller that
                is going to ligate the product should set this.

        Returns:
            Up to ``limit`` candidates, best first, each a dict with
            ``forward``, ``reverse``, ``checks``, ``summary``, ``score``,
            ``product_bp`` and ``tm_delta``. Ordered by rubric score, then by
            how close the pair's Tm values sit to each other, then by how close
            they sit to the target — correctness first, then balance.

        Raises:
            ValueError: the target is too short, or the rubric is inconsistent.
        """
        # Validated here, at the engine boundary, rather than in a view: every
        # caller must be stopped from designing against a sequence the
        # thermodynamic model has no parameters for. Previously an mRNA or a
        # pasted ORIGIN block produced a confident Tm.
        target_sequence = require_sequence(target_sequence, label="Target sequence")
        fwd_overhang = (
            require_sequence(fwd_overhang, label="Forward 5' tail") if fwd_overhang else ""
        )
        rev_overhang = (
            require_sequence(rev_overhang, label="Reverse 5' tail") if rev_overhang else ""
        )

        rub = rubric or PrimerRubric()
        problems = rub.validate()
        if problems:
            raise ValueError("Unusable primer rubric: " + "; ".join(problems))

        target = target_sequence
        wanted_tm = rub.target_tm if target_tm is None else target_tm

        if len(target) < rub.min_length * 2:
            raise ValueError(f"Target sequence too short ({len(target)} bp) for primer design.")

        max_len = min(rub.max_length, len(target) // 2)
        if max_len < rub.min_length:
            raise ValueError(
                f"Target sequence too short ({len(target)} bp) for a "
                f"{rub.min_length} nt primer at each end."
            )
        # Never let the two primers overlap, however wide the offset window is.
        max_offset = max(0, min(rub.max_offset, len(target) // 2 - max_len))

        forwards, reverses = cls._build_primer_grid(
            target, rub, max_len, max_offset, fwd_overhang, rev_overhang, wanted_tm
        )

        # Narrow each end before pairing; see ``max_pool``. Ranked by how well
        # the primer does on its own, then by distance from the target Tm.
        def solo_rank(primer: Primer) -> tuple[float, float]:
            checks = [RubricCheck.from_dict(c) for c in primer.rubric_checks]
            return (-score(checks), abs(primer.calculated_tm - wanted_tm))

        if require_full_target:
            # Keep the pool honest: filtering to full coverage after the pool
            # was chosen could empty it even though valid pairs existed.
            forwards = [p for p in forwards if p.target_region and p.target_region[0] == 0]
            reverses = [
                p for p in reverses if p.target_region and p.target_region[1] == len(target)
            ]

        forwards = sorted(forwards, key=solo_rank)[:max_pool]
        reverses = sorted(reverses, key=solo_rank)[:max_pool]

        candidates: list[dict[str, Any]] = []
        for fwd in forwards:
            for rev in reverses:
                assert fwd.target_region is not None and rev.target_region is not None
                # One definition, shared with the amplification engine, so
                # every surface reports the same number for the same pair.
                product_bp = product_length(
                    fwd.target_region[0],
                    rev.target_region[1],
                    len(fwd_overhang),
                    len(rev_overhang),
                )
                pair_checks = screen_pair(
                    fwd.sequence,
                    rev.sequence,
                    fwd.calculated_tm,
                    rev.calculated_tm,
                    fwd_overhang=fwd.overhang,
                    rev_overhang=rev.overhang,
                    product_bp=product_bp,
                    template=target,
                    rubric=rub,
                )
                all_checks = [
                    *(type(pair_checks[0]).from_dict(c) for c in fwd.rubric_checks),
                    *(type(pair_checks[0]).from_dict(c) for c in rev.rubric_checks),
                    *pair_checks,
                ]
                tm_delta = abs(fwd.calculated_tm - rev.calculated_tm)
                candidates.append(
                    {
                        "forward": fwd,
                        "reverse": rev,
                        "checks": [c.to_dict() for c in all_checks],
                        "summary": summarise(all_checks),
                        "score": round(score(all_checks), 4),
                        "product_bp": product_bp,
                        "tm_delta": round(tm_delta, 2),
                        # Sliding the annealing start inward trims the ends of
                        # the target off the product. Harmless when amplifying
                        # a region, but it would drop a start codon when
                        # amplifying a full ORF for cloning, so it is reported
                        # rather than left for the reader to infer from
                        # coordinates.
                        "covers_full_target": fwd.target_region[0] == 0
                        and rev.target_region[1] == len(target),
                        "amplicon_region": (fwd.target_region[0], rev.target_region[1]),
                        "trimmed_5p": fwd.target_region[0],
                        "trimmed_3p": len(target) - rev.target_region[1],
                        "coverage_note": _coverage_note(
                            fwd.target_region[0],
                            len(target) - rev.target_region[1],
                            product_bp,
                        ),
                    }
                )

        # Rank: rubric score first, then how close the pair sits to the target
        # Tm, then full-target coverage, then pair balance.
        #
        # Target proximity outranks pair balance deliberately. Pair matching is
        # already a rubric check with its own tolerance, so ranking on it again
        # double-counts it — and it let a perfectly matched pair 5 °C off target
        # beat a pair 0.4 °C apart sitting on it. The annealing temperature of
        # the reaction is set from the target Tm, so proximity is what the
        # protocol actually depends on; tm_delta remains the final tie-break.
        if require_full_target and not candidates:
            raise ValueError(
                "No primer pair spans the full target within the rubric's length "
                "window. Widen min_length/max_length, or allow trimming."
            )

        candidates.sort(
            key=lambda c: (
                -c["score"],
                abs(c["forward"].calculated_tm - wanted_tm)
                + abs(c["reverse"].calculated_tm - wanted_tm),
                not c["covers_full_target"],
                c["tm_delta"],
            )
        )
        return candidates[:limit]

    @classmethod
    def design_primers(
        cls,
        target_sequence: str,
        target_tm: float = 60.0,
        min_length: int = 18,
        max_length: int = 30,
        fwd_overhang: str = "",
        rev_overhang: str = "",
        rubric: PrimerRubric | None = None,
    ) -> tuple[Primer, Primer]:
        """Design one Forward/Reverse primer pair for ``target_sequence``.

        Thin wrapper over :meth:`generate_primer_candidates` that returns the
        top-ranked pair, so existing callers keep working unchanged.

        ``min_length`` / ``max_length`` / ``target_tm`` override the rubric
        when given, which preserves the original keyword behaviour.
        """
        base = rubric or PrimerRubric()
        effective = replace(base, min_length=min_length, max_length=max_length, target_tm=target_tm)
        ranked = cls.generate_primer_candidates(
            target_sequence,
            rubric=effective,
            fwd_overhang=fwd_overhang,
            rev_overhang=rev_overhang,
            target_tm=target_tm,
            limit=1,
        )
        if not ranked:
            raise ValueError("No primer pair could be generated for this target.")
        return ranked[0]["forward"], ranked[0]["reverse"]
