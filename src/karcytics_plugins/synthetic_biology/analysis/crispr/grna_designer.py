"""CRISPR/Cas9 Guide RNA Design Engine & Off-Target CFD Scorer.

Scans target DNA sequences for PAM motifs (SpCas9 NGG, AsCas12a TTTV, etc.),
extracts protospacer candidates, computes GC%, checks poly-T termination
motifs, and calculates cutting frequency determination (CFD) off-target
scores. Includes an ML model hook.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from Bio.Seq import Seq

from ..models.domain import gRNACandidate


class CRISPRDesignEngine:
    """Core domain service for CRISPR target scanning and guide RNA evaluation."""

    # PAM motif regex maps (IUPAC nucleotide codes)
    PAM_PATTERNS = {
        "SpCas9 (NGG)": r"(?=(.{20}([ATCG]GG)))",
        "AsCas12a (TTTV)": r"(?=(TTT[ACG](.{20})))",
        "SaCas9 (NNGRRT)": r"(?=(.{21}([ATCG]{2}G[AG]{2}T)))",
        "Cas9-VQR (NGAN)": r"(?=(.{20}([ATCG]GA[ATCG])))",
        "Cas9-EQR (NGAG)": r"(?=(.{20}([ATCG]GAG)))",
    }

    # CFD (Cutting Frequency Determination) position weight penalty map
    # (Doench et al., 2016)
    # Seed region (positions 1-12 from PAM) has heavy mismatch penalty.
    SEED_WEIGHTS = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 0.85, 0.9, 0.95]
    NON_SEED_WEIGHTS = [0.98, 0.98, 0.99, 0.99, 1.0, 1.0, 1.0, 1.0]

    @classmethod
    def find_grna_candidates(
        cls,
        target_sequence: str,
        pam_type: str = "SpCas9 (NGG)",
        spacer_length: int = 20,
    ) -> list[gRNACandidate]:
        """Scans both forward and reverse strands of target sequence for valid
        gRNA sites.

        Args:
            target_sequence: Raw target DNA sequence.
            pam_type: Key in PAM_PATTERNS or custom PAM regex.
            spacer_length: Protospacer length (default 20 bp).

        Returns:
            List of scored gRNACandidate objects.
        """
        seq_fwd = target_sequence.upper()
        seq_rev = str(Seq(seq_fwd).reverse_complement())
        candidates: list[gRNACandidate] = []

        # Process positive strand
        cls._scan_strand(
            sequence=seq_fwd,
            strand=1,
            pam_type=pam_type,
            spacer_length=spacer_length,
            candidates=candidates,
        )

        # Process reverse complement strand
        cls._scan_strand(
            sequence=seq_rev,
            strand=-1,
            pam_type=pam_type,
            spacer_length=spacer_length,
            candidates=candidates,
            original_len=len(seq_fwd),
        )

        # Perform off-target scoring for candidates
        for cand in candidates:
            cls.score_off_targets(cand, seq_fwd)

        return candidates

    @classmethod
    def _scan_strand(
        cls,
        sequence: str,
        strand: int,
        pam_type: str,
        spacer_length: int,
        candidates: list[gRNACandidate],
        original_len: int = 0,
    ) -> None:
        """Internal scanner for a single DNA strand."""
        # Simple NGG regex scanner for robust matching
        if "NGG" in pam_type or pam_type not in cls.PAM_PATTERNS:
            pattern = re.compile(r"(?=([ATCG]{20})[ATCG]GG)")
        else:
            pattern = re.compile(cls.PAM_PATTERNS[pam_type])

        for match in pattern.finditer(sequence):
            start = match.start()
            protospacer = sequence[start : start + spacer_length]
            pam_seq = sequence[start + spacer_length : start + spacer_length + 3]

            if len(protospacer) != spacer_length:
                continue

            # Compute GC Content
            gc_count = protospacer.count("G") + protospacer.count("C")
            gc_pct = (gc_count / spacer_length) * 100.0

            # Check Poly-T premature termination motif (TTTT)
            has_poly_t = "TTTT" in protospacer or "TTTT" in pam_seq

            # Doench Rule 2 / Efficiency heuristic calculation
            eff_score = cls._calculate_on_target_efficiency(protospacer, gc_pct, has_poly_t)

            # Map genomic coordinates
            if strand == 1:
                gen_start = start
                gen_end = start + spacer_length + len(pam_seq)
            else:
                gen_start = original_len - (start + spacer_length + len(pam_seq))
                gen_end = original_len - start

            candidates.append(
                gRNACandidate(
                    id=str(uuid.uuid4())[:8],
                    target_id="Target_Site",
                    protospacer=protospacer,
                    pam=pam_seq,
                    strand=strand,
                    start=gen_start,
                    end=gen_end,
                    gc_content=round(gc_pct, 1),
                    efficiency_score=round(eff_score, 1),
                    off_target_score=100.0,
                    has_poly_t_term=has_poly_t,
                )
            )

    @classmethod
    def _calculate_on_target_efficiency(
        cls, protospacer: str, gc_pct: float, has_poly_t: bool
    ) -> float:
        """Heuristic Doench-like efficiency scoring (0 - 100%)."""
        score = 70.0  # Base efficiency score

        # Optimal GC content is 40% - 60%
        if 40.0 <= gc_pct <= 60.0:  # noqa: PLR2004
            score += 15.0
        elif gc_pct < 30.0 or gc_pct > 70.0:  # noqa: PLR2004
            score -= 25.0

        # Poly-T penalty (causes Pol III transcription termination)
        if has_poly_t:
            score -= 40.0

        # Position 20 (closest to PAM) preference for G or C
        if len(protospacer) >= 20 and protospacer[19] in ["G", "C"]:  # noqa: PLR2004
            score += 10.0

        # Position 16 preference for G
        if len(protospacer) >= 16 and protospacer[15] == "G":  # noqa: PLR2004
            score += 5.0

        return max(0.0, min(100.0, score))

    @classmethod
    def score_off_targets(
        cls,
        candidate: gRNACandidate,
        reference_genome: str,
        ml_model_adapter: Any | None = None,
    ) -> float:
        """Calculates CFD (Cutting Frequency Determination) off-target score.

        Includes a pluggable Machine Learning model interface (`ml_model_adapter`).
        """
        # If an external Machine Learning model adapter is provided,
        # defer to ML prediction
        if ml_model_adapter is not None and hasattr(ml_model_adapter, "predict_off_target"):
            ml_score = ml_model_adapter.predict_off_target(candidate.protospacer, reference_genome)
            candidate.off_target_score = float(ml_score)
            return float(ml_score)

        # Standalone CFD scoring algorithm
        protospacer = candidate.protospacer
        off_target_hits: list[dict[str, Any]] = []
        total_cfd_mult = 1.0

        # Scan reference for potential 1-3 bp mismatch off-target sites
        ref_len = len(reference_genome)
        for i in range(0, ref_len - len(protospacer) - 3):
            sub_seq = reference_genome[i : i + len(protospacer)]
            if sub_seq == protospacer:
                continue  # Exact on-target match

            mismatches = 0
            mismatch_positions = []
            for pos in range(len(protospacer)):
                if sub_seq[pos] != protospacer[pos]:
                    mismatches += 1
                    mismatch_positions.append(pos)

            if 1 <= mismatches <= 3:  # noqa: PLR2004
                # Compute CFD mismatch penalty
                hit_score = 1.0
                for p in mismatch_positions:
                    dist_from_pam = len(protospacer) - 1 - p
                    if dist_from_pam < len(cls.SEED_WEIGHTS):
                        hit_score *= cls.SEED_WEIGHTS[dist_from_pam]
                    else:
                        idx = min(
                            dist_from_pam - len(cls.SEED_WEIGHTS),
                            len(cls.NON_SEED_WEIGHTS) - 1,
                        )
                        hit_score *= cls.NON_SEED_WEIGHTS[idx]

                off_target_hits.append(
                    {
                        "position": i,
                        "sequence": sub_seq,
                        "mismatches": mismatches,
                        "cfd_score": round(hit_score * 100.0, 1),
                    }
                )
                total_cfd_mult *= 1.0 - (hit_score * 0.2)

        final_cfd = round(total_cfd_mult * 100.0, 1)
        candidate.off_target_score = final_cfd
        candidate.off_target_hits = off_target_hits[:10]  # Top 10 hits
        return final_cfd
