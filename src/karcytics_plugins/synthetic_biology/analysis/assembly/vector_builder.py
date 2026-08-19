"""Vector Assembly Engine & Automated Primer Design Algorithm.

Utilizes Biopython (Bio.Seq, Bio.SeqRecord, Bio.SeqIO) for parsing
GenBank/FASTA files, stitching genetic components into a plasmid vector,
mapping features, and designing primers.
"""

from __future__ import annotations

import io
import uuid
from typing import List, Tuple

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from ..models.domain import GeneticFeature, PlasmidVector, Primer
from ..parts.base import BiologicalPart


class VectorAssemblyEngine:
    """Core domain service for sequence file parsing, vector construction,
    and primer design.
    """

    @staticmethod
    def parse_sequence_file(
        file_content: str, file_format: str = "genbank"
    ) -> PlasmidVector:
        """Parses FASTA or GenBank sequence content using Biopython.

        Args:
            file_content: Text string content of FASTA or GenBank file.
            file_format: 'genbank', 'gb', 'fasta', or 'fa'.

        Returns:
            PlasmidVector domain object with mapped features and full sequence.
        """
        fmt = file_format.lower()
        if fmt in ["fa", "fasta"]:
            biopython_fmt = "fasta"
        else:
            biopython_fmt = "genbank"

        handle = io.StringIO(file_content)
        record: SeqRecord = SeqIO.read(handle, biopython_fmt)

        sequence_str = str(record.seq).upper()
        features: List[GeneticFeature] = []

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
                fname = feat.qualifiers.get(
                    "label", feat.qualifiers.get("gene", [feat.type])
                )[0]
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
                        sequence=sequence_str[
                            int(feat.location.start) : int(feat.location.end)
                        ],
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
            description=record.description
            if record.description != "<unknown description>"
            else "",
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
            description=vector.description
            or "Synthetic construct assembled with BioPro",
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
        parts: List[BiologicalPart],
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
        features: List[GeneticFeature] = []

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
            part_seq = part.sequence.upper() if part.sequence else "ATGC"
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
    def calculate_tm(sequence: str) -> float:
        """Calculates nearest-neighbor melting temperature (Tm) for primer
        sequences.

        Formula (Wallace / Marmur GC-based for short oligos
        & nearest-neighbor approximation):
        For oligos <= 14 bp: Tm = (A+T)*2 + (G+C)*4
        For oligos > 14 bp: Tm = 64.9 + 41.0 * (nG + nC - 16.4) / N
        """
        seq = sequence.upper()
        n_a = seq.count("A")
        n_t = seq.count("T")
        n_g = seq.count("G")
        n_c = seq.count("C")
        n_total = len(seq)

        if n_total == 0:
            return 0.0

        if n_total <= 14:
            return float((n_a + n_t) * 2 + (n_g + n_c) * 4)

        return float(64.9 + 41.0 * ((n_g + n_c) - 16.4) / n_total)

    @classmethod
    def design_primers(
        cls,
        target_sequence: str,
        target_tm: float = 60.0,
        min_length: int = 18,
        max_length: int = 30,
        fwd_overhang: str = "",
        rev_overhang: str = "",
    ) -> Tuple[Primer, Primer]:
        """Automated algorithm to design Forward and Reverse PCR primers
        for a target sequence.

        Finds optimal length to match target Tm, calculates GC %,
        and appends overhangs.
        """
        target_seq = target_sequence.upper()
        if len(target_seq) < min_length * 2:
            raise ValueError(
                f"Target sequence too short ({len(target_seq)} bp) for primer design."
            )

        # Design Forward Primer
        best_fwd_len = min_length
        best_fwd_diff = float("inf")
        best_fwd_tm = 0.0

        for primer_len in range(min_length, min(max_length + 1, len(target_seq) // 2)):
            binding_seq = target_seq[:primer_len]
            tm = cls.calculate_tm(binding_seq)
            diff = abs(tm - target_tm)
            if diff < best_fwd_diff:
                best_fwd_diff = diff
                best_fwd_len = primer_len
                best_fwd_tm = tm

        fwd_binding = target_seq[:best_fwd_len]
        fwd_full_seq = fwd_overhang.upper() + fwd_binding
        fwd_gc = (
            (fwd_full_seq.count("G") + fwd_full_seq.count("C"))
            / len(fwd_full_seq)
            * 100.0
        )

        fwd_primer = Primer(
            id=str(uuid.uuid4())[:8],
            name="Forward_Primer",
            sequence=fwd_full_seq,
            direction="FWD",
            target_tm=target_tm,
            calculated_tm=round(best_fwd_tm, 2),
            gc_content=round(fwd_gc, 1),
            length=len(fwd_full_seq),
            overhang=fwd_overhang.upper(),
            target_region=(0, best_fwd_len),
        )

        # Design Reverse Primer (reverse complement of target end)
        best_rev_len = min_length
        best_rev_diff = float("inf")
        best_rev_tm = 0.0

        for primer_len in range(min_length, min(max_length + 1, len(target_seq) // 2)):
            binding_region = target_seq[-primer_len:]
            binding_rc = str(Seq(binding_region).reverse_complement())
            tm = cls.calculate_tm(binding_rc)
            diff = abs(tm - target_tm)
            if diff < best_rev_diff:
                best_rev_diff = diff
                best_rev_len = primer_len
                best_rev_tm = tm

        rev_binding_region = target_seq[-best_rev_len:]
        rev_binding_rc = str(Seq(rev_binding_region).reverse_complement())
        rev_full_seq = rev_overhang.upper() + rev_binding_rc
        rev_gc = (
            (rev_full_seq.count("G") + rev_full_seq.count("C"))
            / len(rev_full_seq)
            * 100.0
        )

        rev_primer = Primer(
            id=str(uuid.uuid4())[:8],
            name="Reverse_Primer",
            sequence=rev_full_seq,
            direction="REV",
            target_tm=target_tm,
            calculated_tm=round(best_rev_tm, 2),
            gc_content=round(rev_gc, 1),
            length=len(rev_full_seq),
            overhang=rev_overhang.upper(),
            target_region=(len(target_seq) - best_rev_len, len(target_seq)),
        )

        return fwd_primer, rev_primer
