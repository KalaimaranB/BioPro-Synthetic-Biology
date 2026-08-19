"""Biologically aware sequence prediction engine for BioPro Synthetic Biology.

Uses the Strategy Pattern to route prediction queries:
1. PromoterBiophysicsStrategy: Calculates thermodynamic binding affinity scores
   based on RNA Polymerase sigma-70 Position Weight Matrices (PWM) for the -35
   and -10 consensus motifs and spacer length strain penalties. Maps binding energy
   to transfer curve parameters (K_d, y_max, y_min, n).
2. CDSStructuralStrategy: Predicts translation_rate using a host-specific Codon
   Adaptation Index (CAI) and degradation_rate using BLOSUM62 amino acid
   substitution matrix scoring (protein folding stability proxy).
3. KNNPredictionStrategy: Legacy sequence similarity approach using Levenshtein
   distance alignment and inverse-distance weighting across characterized parts
   catalogue as a safe fallback.
"""

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


def levenshtein_distance(seq1: str, seq2: str) -> int:
    """Computes the Levenshtein (edit) distance between two DNA sequences."""
    s1 = seq1.upper().strip()
    s2 = seq2.upper().strip()

    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (0 if c1 == c2 else 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


# Standard Bacterial Genetic Code Table
STANDARD_GENETIC_CODE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}


def translate_dna_to_protein(dna_seq: str) -> str:
    """Translates a DNA coding sequence into an amino acid string using standard
    genetic code.
    """
    seq = dna_seq.upper().strip()
    if not seq or len(seq) % 3 != 0:
        raise ValueError(f"CDS DNA length ({len(seq)}) is not a multiple of 3.")

    protein = []
    for i in range(0, len(seq), 3):
        codon = seq[i : i + 3]
        aa = STANDARD_GENETIC_CODE.get(codon)
        if aa is None:
            raise ValueError(f"Invalid codon '{codon}' in CDS sequence.")
        if aa == "*":
            # Stop codon encountered
            break
        protein.append(aa)

    if not protein:
        raise ValueError("Translation produced an empty amino acid chain.")

    return "".join(protein)


# E. coli Codon Relative Adaptiveness Values (w_i) for CAI Model
ECOLI_CODON_W = {
    # Ala (A)
    "GCG": 1.00,
    "GCC": 0.75,
    "GCT": 0.55,
    "GCA": 0.40,
    # Arg (R)
    "CGT": 1.00,
    "CGC": 0.88,
    "CGG": 0.08,
    "CGA": 0.05,
    "AGA": 0.04,
    "AGG": 0.02,
    # Asn (N)
    "AAC": 1.00,
    "AAT": 0.35,
    # Asp (D)
    "GAC": 1.00,
    "GAT": 0.45,
    # Cys (C)
    "TGC": 1.00,
    "TGT": 0.40,
    # Gln (Q)
    "CAG": 1.00,
    "CAA": 0.20,
    # Glu (E)
    "GAA": 1.00,
    "GAG": 0.25,
    # Gly (G)
    "GGC": 1.00,
    "GGT": 0.90,
    "GGG": 0.15,
    "GGA": 0.10,
    # His (H)
    "CAC": 1.00,
    "CAT": 0.45,
    # Ile (I)
    "ATC": 1.00,
    "ATT": 0.80,
    "ATA": 0.08,
    # Leu (L)
    "CTG": 1.00,
    "CTC": 0.25,
    "CTT": 0.12,
    "TTA": 0.06,
    "TTG": 0.12,
    "CTA": 0.04,
    # Lys (K)
    "AAA": 1.00,
    "AAG": 0.25,
    # Met (M)
    "ATG": 1.00,
    # Phe (F)
    "TTC": 1.00,
    "TTT": 0.60,
    # Pro (P)
    "CCG": 1.00,
    "CCA": 0.20,
    "CCT": 0.15,
    "CCC": 0.10,
    # Ser (S)
    "TCC": 1.00,
    "AGC": 0.95,
    "TCT": 0.85,
    "TCG": 0.20,
    "TCA": 0.15,
    "AGT": 0.15,
    # Thr (T)
    "ACC": 1.00,
    "ACG": 0.70,
    "ACT": 0.55,
    "ACA": 0.15,
    # Trp (W)
    "TGG": 1.00,
    # Tyr (Y)
    "TAC": 1.00,
    "TAT": 0.45,
    # Val (V)
    "GTG": 1.00,
    "GTT": 0.85,
    "GTC": 0.45,
    "GTA": 0.20,
}


# BLOSUM62 Amino Acid Substitution Matrix (Unrolled Pair Dictionary)
BLOSUM62_SCORES = {
    ("A", "A"): 4,
    ("A", "R"): -1,
    ("A", "N"): -2,
    ("A", "D"): -2,
    ("A", "C"): 0,
    ("A", "Q"): -1,
    ("A", "E"): -1,
    ("A", "G"): 0,
    ("A", "H"): -2,
    ("A", "I"): -1,
    ("A", "L"): -1,
    ("A", "K"): -1,
    ("A", "M"): -1,
    ("A", "F"): -2,
    ("A", "P"): -1,
    ("A", "S"): 1,
    ("A", "T"): 0,
    ("A", "W"): -3,
    ("A", "Y"): -2,
    ("A", "V"): 0,
    ("R", "R"): 5,
    ("R", "N"): 0,
    ("R", "D"): -2,
    ("R", "C"): -3,
    ("R", "Q"): 1,
    ("R", "E"): 0,
    ("R", "G"): -2,
    ("R", "H"): 0,
    ("R", "I"): -3,
    ("R", "L"): -2,
    ("R", "K"): 2,
    ("R", "M"): -1,
    ("R", "F"): -3,
    ("R", "P"): -2,
    ("R", "S"): -1,
    ("R", "T"): -1,
    ("R", "W"): -3,
    ("R", "Y"): -2,
    ("R", "V"): -3,
    ("N", "N"): 6,
    ("N", "D"): 1,
    ("N", "C"): -3,
    ("N", "Q"): 0,
    ("N", "E"): 0,
    ("N", "G"): 0,
    ("N", "H"): 1,
    ("N", "I"): -3,
    ("N", "L"): -3,
    ("N", "K"): 0,
    ("N", "M"): -2,
    ("N", "F"): -3,
    ("N", "P"): -2,
    ("N", "S"): 1,
    ("N", "T"): 0,
    ("N", "W"): -4,
    ("N", "Y"): -2,
    ("N", "V"): -3,
    ("D", "D"): 6,
    ("D", "C"): -3,
    ("D", "Q"): 0,
    ("D", "E"): 2,
    ("D", "G"): -1,
    ("D", "H"): -1,
    ("D", "I"): -3,
    ("D", "L"): -4,
    ("D", "K"): -1,
    ("D", "M"): -3,
    ("D", "F"): -3,
    ("D", "P"): -1,
    ("D", "S"): 0,
    ("D", "T"): -1,
    ("D", "W"): -4,
    ("D", "Y"): -3,
    ("D", "V"): -3,
    ("C", "C"): 9,
    ("C", "Q"): -3,
    ("C", "E"): -4,
    ("C", "G"): -3,
    ("C", "H"): -3,
    ("C", "I"): -1,
    ("C", "L"): -1,
    ("C", "K"): -3,
    ("C", "M"): -1,
    ("C", "F"): -2,
    ("C", "P"): -3,
    ("C", "S"): -1,
    ("C", "T"): -1,
    ("C", "W"): -2,
    ("C", "Y"): -2,
    ("C", "V"): -1,
    ("Q", "Q"): 5,
    ("Q", "E"): 2,
    ("Q", "G"): -2,
    ("Q", "H"): 0,
    ("Q", "I"): -3,
    ("Q", "L"): -2,
    ("Q", "K"): 1,
    ("Q", "M"): 0,
    ("Q", "F"): -3,
    ("Q", "P"): -1,
    ("Q", "S"): 0,
    ("Q", "T"): -1,
    ("Q", "W"): -2,
    ("Q", "Y"): -1,
    ("Q", "V"): -2,
    ("E", "E"): 5,
    ("E", "G"): -2,
    ("E", "H"): 0,
    ("E", "I"): -3,
    ("E", "L"): -3,
    ("E", "K"): 1,
    ("E", "M"): -2,
    ("E", "F"): -3,
    ("E", "P"): -1,
    ("E", "S"): 0,
    ("E", "T"): -1,
    ("E", "W"): -3,
    ("E", "Y"): -2,
    ("E", "V"): -2,
    ("G", "G"): 6,
    ("G", "H"): -2,
    ("G", "I"): -4,
    ("G", "L"): -4,
    ("G", "K"): -2,
    ("G", "M"): -3,
    ("G", "F"): -3,
    ("G", "P"): -2,
    ("G", "S"): 0,
    ("G", "T"): -2,
    ("G", "W"): -2,
    ("G", "Y"): -3,
    ("G", "V"): -3,
    ("H", "H"): 8,
    ("H", "I"): -3,
    ("H", "L"): -3,
    ("H", "K"): -1,
    ("H", "M"): -2,
    ("H", "F"): -1,
    ("H", "P"): -2,
    ("H", "S"): -1,
    ("H", "T"): -2,
    ("H", "W"): -2,
    ("H", "Y"): 2,
    ("H", "V"): -3,
    ("I", "I"): 4,
    ("I", "L"): 2,
    ("I", "K"): -3,
    ("I", "M"): 1,
    ("I", "F"): 0,
    ("I", "P"): -3,
    ("I", "S"): -2,
    ("I", "T"): -1,
    ("I", "W"): -3,
    ("I", "Y"): -1,
    ("I", "V"): 3,
    ("L", "L"): 4,
    ("L", "K"): -2,
    ("L", "M"): 2,
    ("L", "F"): 0,
    ("L", "P"): -3,
    ("L", "S"): -2,
    ("L", "T"): -1,
    ("L", "W"): -2,
    ("L", "Y"): -1,
    ("L", "V"): 1,
    ("K", "K"): 5,
    ("K", "M"): -1,
    ("K", "F"): -3,
    ("K", "P"): -1,
    ("K", "S"): 0,
    ("K", "T"): -1,
    ("K", "W"): -3,
    ("K", "Y"): -2,
    ("K", "V"): -2,
    ("M", "M"): 5,
    ("M", "F"): 0,
    ("M", "P"): -2,
    ("M", "S"): -1,
    ("M", "T"): -1,
    ("M", "W"): -1,
    ("M", "Y"): -1,
    ("M", "V"): 1,
    ("F", "F"): 6,
    ("F", "P"): -4,
    ("F", "S"): -2,
    ("F", "T"): -2,
    ("F", "W"): 1,
    ("F", "Y"): 3,
    ("F", "V"): -1,
    ("P", "P"): 7,
    ("P", "S"): -1,
    ("P", "T"): -1,
    ("P", "W"): -4,
    ("P", "Y"): -3,
    ("P", "V"): -2,
    ("S", "S"): 4,
    ("S", "T"): 1,
    ("S", "W"): -3,
    ("S", "Y"): -2,
    ("S", "V"): -2,
    ("T", "T"): 5,
    ("T", "W"): -2,
    ("T", "Y"): -2,
    ("T", "V"): 0,
    ("W", "W"): 11,
    ("W", "Y"): 2,
    ("W", "V"): -3,
    ("Y", "Y"): 7,
    ("Y", "V"): -1,
    ("V", "V"): 4,
}


def get_blosum62_score(aa1: str, aa2: str) -> int:
    """Retrieve BLOSUM62 score for an amino acid pair (symmetric lookup)."""
    a1, a2 = aa1.upper(), aa2.upper()
    if (a1, a2) in BLOSUM62_SCORES:
        return BLOSUM62_SCORES[(a1, a2)]
    if (a2, a1) in BLOSUM62_SCORES:
        return BLOSUM62_SCORES[(a2, a1)]
    return -4  # Default score for non-standard amino acid substitution


class PredictionStrategy(ABC):
    """Abstract base class for sequence parameter prediction strategies."""

    @abstractmethod
    def predict(
        self,
        query_sequence: str,
        candidate_parts: List[Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute parameter prediction for the given query sequence."""
        pass


class KNNPredictionStrategy(PredictionStrategy):
    """k-Nearest Neighbors prediction strategy using Levenshtein distance.

    Useful for non-promoters/non-CDS parts or as a safe fallback when biophysical
    scanning fails.
    """

    def predict(
        self,
        query_sequence: str,
        candidate_parts: List[Any],
        part_type: str = "promoter",
        k: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        clean_query = query_sequence.upper().strip()
        if not clean_query:
            return {
                "is_predicted": False,
                "error": "Empty sequence provided.",
                "parameters": {},
            }

        target_type = part_type.lower()

        # Filter candidate parts matching target part_type with non-empty sequence
        valid_candidates = []
        for part in candidate_parts:
            p_type = getattr(part, "part_type", "").lower()
            p_seq = getattr(part, "sequence", "")
            if p_type == target_type and p_seq and p_seq.strip():
                valid_candidates.append(part)

        if not valid_candidates:
            return {
                "is_predicted": False,
                "error": (
                    f"No candidate parts with sequence found for type '{part_type}'."
                ),
                "parameters": {},
            }

        # Calculate Levenshtein distance for each candidate
        distances: List[Tuple[Any, int]] = []
        for part in valid_candidates:
            dist = levenshtein_distance(clean_query, part.sequence)
            distances.append((part, dist))

        # Sort candidates by distance ascending
        distances.sort(key=lambda item: item[1])

        # Pick top-k
        top_k = distances[: max(1, k)]

        # Check for exact match (distance == 0)
        exact_match = [item for item in top_k if item[1] == 0]

        if target_type == "promoter":
            param_names = ["K_d", "y_max", "y_min", "n"]
        elif target_type == "cds":
            param_names = ["translation_rate", "degradation_rate"]
        else:
            param_names = []

        predicted_params: Dict[str, float | None] = {}

        if exact_match:
            best_part = exact_match[0][0]
            for pname in param_names:
                val = getattr(best_part, pname, None)
                predicted_params[pname] = float(val) if val is not None else None
            weights_info = [
                {
                    "id": best_part.id,
                    "name": getattr(best_part, "name", best_part.id),
                    "distance": 0,
                    "weight": 1.0,
                }
            ]
        else:
            weights = [1.0 / dist for _, dist in top_k]
            total_weight = sum(weights)

            weights_info = [
                {
                    "id": part.id,
                    "name": getattr(part, "name", part.id),
                    "distance": dist,
                    "weight": round(w / total_weight, 4),
                }
                for (part, dist), w in zip(top_k, weights)
            ]

            for pname in param_names:
                weighted_sum = 0.0
                valid_weight_sum = 0.0

                for (part, dist), w in zip(top_k, weights):
                    val = getattr(part, pname, None)
                    if val is not None:
                        try:
                            fval = float(val)
                            weighted_sum += fval * w
                            valid_weight_sum += w
                        except (ValueError, TypeError):
                            pass

                if valid_weight_sum > 0:
                    predicted_params[pname] = round(weighted_sum / valid_weight_sum, 4)
                else:
                    predicted_params[pname] = None

        top_id = top_k[0][0].id if top_k else "N/A"
        top_dist = top_k[0][1] if top_k else "N/A"

        return {
            "is_predicted": True,
            "model_type": "k-NN Distance Alignment",
            "prediction_method": "k-NN Distance Alignment",
            "query_sequence_len": len(clean_query),
            "k_neighbors_used": len(top_k),
            "top_match_id": top_id,
            "top_match_distance": top_dist,
            "status_message": (
                f"⚡ [Predicted via {len(top_k)}-NN] Top match: {top_id} "
                f"(distance: {top_dist})"
            ),
            "parameters": predicted_params,
            "neighbors": weights_info,
        }


class PromoterBiophysicsStrategy(PredictionStrategy):
    """Biologically aware Position Weight Matrix (PWM) prediction strategy for
    Promoters.

    Biophysical Rationale:
    1. Bacterial transcription initiation by RNA Polymerase (sigma-70 holoenzyme)
       requires recognition of two specific hexameric DNA motifs:
       - -35 Box: Consensus 'TTGACA' (positions -35 to -30)
       - -10 Box (Pribnow box): Consensus 'TATAAT' (positions -12 to -7)
    2. Optimal spacer distance between the -35 and -10 hexamers is 17 bp
       (acceptable range: 15 to 19 bp). Deviations from 17 bp introduce torsional
       and structural strain on the sigma-70 subdomains (sigma_4 and sigma_2).
    3. The sliding window algorithm scans the query DNA string to locate the window
       minimizing total binding penalty:
       Penalty_total = Penalty_-35(PWM) + Penalty_-10(PWM) + Penalty_spacer
    4. Thermodynamic Parameter Mapping:
       - y_max: RNAP open-complex formation rate. High binding affinity (low penalty)
         -> High y_max (up to ~250 RPU). Weak binding (high penalty) -> Exponentially
         suppressed y_max.
       - K_d: Repression threshold / dissociation constant. Strong RNAP binding
         (low penalty) -> Low K_d (~0.05 RPU). Weak RNAP binding -> Higher K_d
         needed for repressor competition.
       - y_min: Basal leakiness (relatively stable around 0.01 - 0.05 RPU).
       - n: Hill coefficient / cooperativity (default 2.0).
    """

    MIN_WINDOW_LEN = 27  # 6 (-35) + 15 (min spacer) + 6 (-10)
    CONSENSUS_35 = "TTGACA"
    CONSENSUS_10 = "TATAAT"
    OPTIMAL_SPACER = 17
    ALLOWED_SPACERS = [15, 16, 17, 18, 19]

    # Position Weight Matrix (PWM) energy penalties (in kB*T) for nucleotide deviations
    PWM_35_PENALTIES = [
        {"T": 0.0, "C": 1.8, "A": 2.2, "G": 2.5},  # Pos 0: T (Highly conserved)
        {"T": 0.0, "C": 1.8, "A": 2.0, "G": 2.3},  # Pos 1: T (Highly conserved)
        {"G": 0.0, "A": 1.5, "T": 2.2, "C": 2.2},  # Pos 2: G (Highly conserved)
        {"A": 0.0, "C": 1.0, "T": 1.2, "G": 1.2},  # Pos 3: A (Moderately conserved)
        {"C": 0.0, "T": 1.0, "A": 1.2, "G": 1.4},  # Pos 4: C (Moderately conserved)
        {"A": 0.0, "G": 0.8, "T": 1.0, "C": 1.0},  # Pos 5: A (Less conserved)
    ]

    PWM_10_PENALTIES = [
        {
            "T": 0.0,
            "C": 2.2,
            "A": 2.5,
            "G": 2.5,
        },  # Pos 0: T (Crucial at -12 for un-winding)
        {"A": 0.0, "G": 1.8, "T": 2.0, "C": 2.2},  # Pos 1: A (Crucial at -11)
        {"T": 0.0, "C": 1.2, "A": 1.4, "G": 1.5},  # Pos 2: T (Moderately conserved)
        {"A": 0.0, "G": 1.0, "T": 1.2, "C": 1.4},  # Pos 3: A (Moderately conserved)
        {"A": 0.0, "G": 1.0, "T": 1.2, "C": 1.4},  # Pos 4: A (Moderately conserved)
        {"T": 0.0, "C": 2.2, "A": 2.5, "G": 2.5},  # Pos 5: T (Crucial at -7 TSS anchor)
    ]

    SPACER_PENALTIES = {
        17: 0.0,  # Optimal spacing
        16: 1.8,  # 1 bp compression strain
        18: 1.8,  # 1 bp extension strain
        15: 4.5,  # 2 bp compression strain
        19: 4.5,  # 2 bp extension strain
    }

    def _compute_hexamer_penalty(
        self, hexamer: str, pwm_table: List[Dict[str, float]]
    ) -> float:
        """Compute thermodynamic penalty for a 6 bp hexamer sequence against PWM
        matrix.
        """
        penalty = 0.0
        clean_hex = hexamer.upper()
        for i in range(min(len(clean_hex), 6)):
            nuc = clean_hex[i]
            pos_dict = pwm_table[i]
            penalty += pos_dict.get(nuc, 2.5)  # Default penalty for N or unknown base
        return penalty

    def _scan_sliding_window(self, sequence: str) -> Optional[Dict[str, Any]]:
        """Scan input DNA string across all sliding window positions and spacer
        lengths.

        Returns the best matching window minimizing the total thermodynamic
        binding penalty.
        """
        seq = sequence.upper()
        seq_len = len(seq)

        if seq_len < self.MIN_WINDOW_LEN:
            return None

        best_penalty = float("inf")
        best_details = None

        # Iterate over all starting positions for the -35 hexamer
        for i in range(seq_len - self.MIN_WINDOW_LEN + 1):
            hex_35 = seq[i : i + 6]
            pen_35 = self._compute_hexamer_penalty(hex_35, self.PWM_35_PENALTIES)

            # Test each allowed spacer length
            for spacer_len in self.ALLOWED_SPACERS:
                window_end = i + 6 + spacer_len + 6
                if window_end > seq_len:
                    continue

                hex_10 = seq[i + 6 + spacer_len : window_end]
                pen_10 = self._compute_hexamer_penalty(hex_10, self.PWM_10_PENALTIES)
                pen_spacer = self.SPACER_PENALTIES.get(spacer_len, 6.0)

                total_penalty = pen_35 + pen_10 + pen_spacer

                if total_penalty < best_penalty:
                    best_penalty = total_penalty
                    best_details = {
                        "start_index": i,
                        "hexamer_35": hex_35,
                        "spacer_len": spacer_len,
                        "hexamer_10": hex_10,
                        "penalty_35": pen_35,
                        "penalty_10": pen_10,
                        "penalty_spacer": pen_spacer,
                        "total_penalty": total_penalty,
                    }

        return best_details

    def _map_penalty_to_parameters(self, penalty: float) -> Dict[str, float]:
        """Map thermodynamic binding penalty (kB*T) to transfer curve parameters:

        - y_max: Exponential decay with penalty from reference maximum (250 RPU)
          down to floor (0.05 RPU).
        - K_d: Exponential increase with penalty from base threshold (0.05 RPU) up
          to ceiling (100 RPU).
        - y_min: Basal leakiness, relatively stable around 0.01 - 0.05 RPU.
        - n: Hill coefficient, default 2.0.
        """
        y_max_ref = 250.0
        y_max_floor = 0.05
        decay_rate_ymax = 0.35
        y_max = y_max_floor + (y_max_ref - y_max_floor) * math.exp(
            -decay_rate_ymax * penalty
        )

        kd_base = 0.05
        growth_rate_kd = 0.4
        kd = min(100.0, kd_base * math.exp(growth_rate_kd * penalty))

        y_min = max(0.005, 0.01 + 0.4 * math.exp(-decay_rate_ymax * penalty))
        n = 2.0

        return {
            "K_d": round(kd, 4),
            "y_max": round(y_max, 4),
            "y_min": round(y_min, 4),
            "n": round(n, 4),
        }

    def predict(
        self,
        query_sequence: str,
        candidate_parts: List[Any],
        **kwargs,
    ) -> Dict[str, Any]:
        clean_query = "".join(c for c in query_sequence.upper() if c in "ACGTN")
        if not clean_query or len(clean_query) < self.MIN_WINDOW_LEN:
            raise ValueError(
                f"Promoter sequence length ({len(clean_query)} bp) is below the "
                f"minimum required window size ({self.MIN_WINDOW_LEN} bp) for "
                "-35/-10 biophysical scanning."
            )

        # Check for exact characterized candidate match first
        for part in candidate_parts:
            p_type = getattr(part, "part_type", "").lower()
            p_seq = getattr(part, "sequence", "")
            if p_type == "promoter" and p_seq and p_seq.upper().strip() == clean_query:
                val_kd = getattr(part, "K_d", None)
                val_ymax = getattr(part, "y_max", None)
                if val_kd is not None and val_ymax is not None:
                    return {
                        "is_predicted": True,
                        "model_type": "Thermodynamic PWM Model",
                        "prediction_method": "Characterized Part Match",
                        "query_sequence_len": len(clean_query),
                        "k_neighbors_used": "Thermodynamic PWM Model",
                        "top_match_id": part.id,
                        "top_match_distance": 0,
                        "status_message": "⚡ [Predicted via Thermodynamic PWM Model]",
                        "parameters": {
                            "K_d": float(val_kd),
                            "y_max": float(val_ymax),
                            "y_min": float(getattr(part, "y_min", 0.01) or 0.01),
                            "n": float(getattr(part, "n", 2.0) or 2.0),
                        },
                    }

        # Run PWM sliding window alignment
        window_match = self._scan_sliding_window(clean_query)
        if not window_match:
            raise ValueError(
                "Failed to locate valid -35/-10 promoter window in sequence."
            )

        penalty = window_match["total_penalty"]
        params = self._map_penalty_to_parameters(penalty)

        affinity_score = max(0.0, min(100.0, 100.0 * (1.0 - (penalty / 25.0))))
        hex_35 = window_match["hexamer_35"]
        hex_10 = window_match["hexamer_10"]
        spacer = window_match["spacer_len"]

        top_match_id = f"-35: {hex_35} | Spacer: {spacer}bp | -10: {hex_10}"
        top_match_dist = f"Penalty={penalty:.2f} kB*T (Affinity={affinity_score:.1f}%)"

        return {
            "is_predicted": True,
            "model_type": "Thermodynamic PWM Model",
            "prediction_method": "Thermodynamic PWM Model",
            "query_sequence_len": len(clean_query),
            "k_neighbors_used": "Thermodynamic PWM Model",
            "top_match_id": top_match_id,
            "top_match_distance": top_match_dist,
            "status_message": "⚡ [Predicted via Thermodynamic PWM Model]",
            "parameters": params,
            "details": {
                "binding_penalty_kB_T": round(penalty, 3),
                "affinity_score_percent": round(affinity_score, 1),
                "hexamer_35": hex_35,
                "hexamer_10": hex_10,
                "spacer_len": spacer,
                "start_index": window_match["start_index"],
            },
        }


class CDSStructuralStrategy(PredictionStrategy):
    """Biologically aware CDS prediction strategy using CAI and BLOSUM62
    stability models.

    Biochemical Rationale:
    1. Translation Rate (Codon Adaptation Index - CAI Model):
       In E. coli, highly expressed proteins use optimal codons corresponding
       to abundant tRNAs. CAI is calculated as the geometric mean of relative
       adaptiveness values w_i for all sense codons:
       CAI = exp( (1 / N_sense) * sum( ln(w_i) ) )
       High CAI -> Fast ribosomal translation rate (translation_rate ~ 0.5 - 1.0
       min^-1).
       Low CAI -> Translational bottlenecks due to rare tRNAs (translation_rate
       ~ 0.01 - 0.1 min^-1).

    2. Degradation Rate (BLOSUM62 Folding Stability Proxy Model):
       Structural stability (Delta Delta G) of the translated amino acid chain is
       evaluated by comparing the query protein sequence against characterized CDS
       reference parts using BLOSUM62 matrix scores.
       - Conservative substitutions (e.g. Leucine <-> Isoleucine, Lysine <-> Arginine)
         have positive/mild scores, imposing minimal folding penalty and maintaining
         baseline degradation rates (~0.01 min^-1).
       - Non-conservative substitutions (e.g. Glycine <-> Tryptophan, Aspartate <->
         Phenylalanine) disrupt hydrophobic cores or salt-bridges, yielding massive
         structural instability penalties. Misfolded proteins are recognized by host
         intracellular proteases (ClpXP/Lon) and rapidly degraded (degradation_rate
         up to ~0.5 min^-1).
    """

    def _calculate_cai(self, dna_seq: str) -> float:
        """Calculate E. coli Codon Adaptation Index (CAI) across all 3-bp codon
        windows.
        """
        seq = dna_seq.upper().strip()
        w_values = []
        for i in range(0, len(seq), 3):
            codon = seq[i : i + 3]
            if codon in ("TAA", "TAG", "TGA"):
                continue  # Stop codons excluded from CAI calculation
            w = ECOLI_CODON_W.get(codon, 0.01)
            w_values.append(max(0.01, float(w)))

        if not w_values:
            return 0.5

        log_sum = sum(math.log(w) for w in w_values)
        cai = math.exp(log_sum / len(w_values))
        return max(0.01, min(1.0, cai))

    def _map_cai_to_translation_rate(self, cai: float) -> float:
        """Map CAI score (0.01 - 1.0) to continuous translation_rate parameter
        (min^-1).
        """
        rate_min = 0.005
        rate_max = 1.0
        rate = rate_min + (rate_max - rate_min) * (cai**1.5)
        return round(max(rate_min, min(rate_max, rate)), 4)

    def _compute_blosum62_penalty(
        self, aa_query: str, aa_ref: str
    ) -> Tuple[float, int]:
        """Compute protein structural instability penalty using BLOSUM62 matrix.

        For substituted position i:
        Delta S_i = max(1.0, BLOSUM62(ref_i, ref_i) - BLOSUM62(query_i, ref_i))
        """
        min_len = min(len(aa_query), len(aa_ref))
        if min_len == 0:
            return 5.0, 0

        total_penalty = 0.0
        substitutions = 0

        for i in range(min_len):
            q_aa = aa_query[i]
            r_aa = aa_ref[i]

            if q_aa != r_aa:
                substitutions += 1
                ref_self_score = get_blosum62_score(r_aa, r_aa)
                sub_score = get_blosum62_score(q_aa, r_aa)
                penalty_i = max(1.0, float(ref_self_score - sub_score))
                total_penalty += penalty_i

        # Add length discrepancy penalty for truncations or insertions
        length_diff = abs(len(aa_query) - len(aa_ref))
        total_penalty += length_diff * 4.0

        penalty_norm = (total_penalty / float(max(1, len(aa_ref)))) + (
            substitutions * 0.8
        )
        return penalty_norm, substitutions

    def _map_penalty_to_degradation_rate(
        self,
        penalty_norm: float,
        substitutions: int = 0,
        base_deg_rate: float = 0.01,
    ) -> float:
        """Map structural instability penalty to protein degradation_rate (min^-1).

        Biophysical Rationale:
        When a missense mutation alters the translated amino acid sequence
        (substitutions > 0), protein folding stability is compromised, exposing
        hydrophobic residues to intracellular proteases (Lon/ClpXP). A structural
        degradation penalty scales with BLOSUM62 mismatch score to significantly
        increase degradation_rate (e.g., 0.10 - 0.45 min^-1 for missense mutations),
        resulting in a flattened steady-state expression curve.
        """
        if substitutions > 0 or penalty_norm > 0:
            boost = 0.8 * float(substitutions) + 1.2 * float(penalty_norm)
            deg_rate = base_deg_rate * math.exp(boost)
            min_mut_deg = 0.08 if substitutions > 0 else base_deg_rate
            return round(min(0.5, max(min_mut_deg, deg_rate)), 4)

        return round(max(0.001, base_deg_rate), 4)

    def predict(
        self,
        query_sequence: str,
        candidate_parts: List[Any],
        **kwargs,
    ) -> Dict[str, Any]:
        clean_query = "".join(c for c in query_sequence.upper() if c in "ACGTN")
        if not clean_query:
            raise ValueError("Empty sequence provided for CDS prediction.")

        if len(clean_query) % 3 != 0:
            raise ValueError(
                f"CDS DNA sequence length ({len(clean_query)} bp) is not a "
                "multiple of 3."
            )

        # Translate query DNA to amino acid string using standard bacterial genetic code
        protein_query = translate_dna_to_protein(clean_query)

        # Check if an explicit reference sequence was provided
        # (e.g. from compare_kinetics)
        ref_seq_arg = kwargs.get("ref_sequence") or kwargs.get("wildtype_sequence")

        # If no explicit reference is provided, check candidate parts for exact
        # characterized match
        if not ref_seq_arg:
            for part in candidate_parts:
                p_type = getattr(part, "part_type", "").lower()
                p_seq = getattr(part, "sequence", "")
                if p_type == "cds" and p_seq and p_seq.upper().strip() == clean_query:
                    val_trans = getattr(part, "translation_rate", None)
                    val_deg = getattr(part, "degradation_rate", None)
                    if val_trans is not None or val_deg is not None:
                        return {
                            "is_predicted": True,
                            "model_type": "CAI & BLOSUM62 Stability Model",
                            "prediction_method": "Characterized Part Match",
                            "query_sequence_len": len(clean_query),
                            "k_neighbors_used": "CAI & BLOSUM62 Stability Model",
                            "top_match_id": part.id,
                            "top_match_distance": 0,
                            "status_message": (
                                "⚡ [Predicted via CAI & BLOSUM62 Stability Model]"
                            ),
                            "parameters": {
                                "translation_rate": float(val_trans)
                                if val_trans is not None
                                else 0.1,
                                "degradation_rate": float(val_deg)
                                if val_deg is not None
                                else 0.01,
                            },
                        }

        # Calculate CAI score and mapped translation rate
        cai_score = self._calculate_cai(clean_query)
        translation_rate = self._map_cai_to_translation_rate(cai_score)

        top_match_id = "Baseline Reference"
        top_match_dist = "N/A"
        base_deg_rate = 0.01
        structural_penalty = 0.0
        sub_count = 0

        # Case A: Explicit reference sequence provided
        if ref_seq_arg:
            clean_ref_dna = "".join(c for c in ref_seq_arg.upper() if c in "ACGTN")
            if clean_ref_dna and len(clean_ref_dna) % 3 == 0:
                try:
                    protein_ref = translate_dna_to_protein(clean_ref_dna)
                    top_match_id = "WildType Baseline"
                    top_match_dist = str(
                        levenshtein_distance(clean_query, clean_ref_dna)
                    )
                    structural_penalty, sub_count = self._compute_blosum62_penalty(
                        protein_query, protein_ref
                    )
                except Exception:
                    structural_penalty = 0.0
                    sub_count = 0

        # Case B: Find closest CDS candidate in repository for BLOSUM62 structural
        # comparison
        else:
            valid_cds_candidates = [
                p
                for p in candidate_parts
                if getattr(p, "part_type", "").lower() == "cds"
                and getattr(p, "sequence", "").strip()
            ]

            if valid_cds_candidates:
                # Prefer candidates with distance > 0 so query sequence isn't
                # compared against itself
                non_self = [
                    p
                    for p in valid_cds_candidates
                    if p.sequence.upper().strip() != clean_query
                ]
                pool = non_self if non_self else valid_cds_candidates

                best_candidate = None
                best_dist = float("inf")

                for candidate in pool:
                    d = levenshtein_distance(clean_query, candidate.sequence)
                    if d < best_dist:
                        best_dist = d
                        best_candidate = candidate

                if best_candidate:
                    top_match_id = best_candidate.id
                    top_match_dist = str(best_dist)
                    cand_deg = getattr(best_candidate, "degradation_rate", None)
                    if cand_deg is not None:
                        try:
                            base_deg_rate = float(cand_deg)
                        except (ValueError, TypeError):
                            pass

                    try:
                        protein_ref = translate_dna_to_protein(best_candidate.sequence)
                        structural_penalty, sub_count = self._compute_blosum62_penalty(
                            protein_query, protein_ref
                        )
                    except Exception:
                        structural_penalty = 0.0
                        sub_count = 0

        degradation_rate = self._map_penalty_to_degradation_rate(
            structural_penalty, substitutions=sub_count, base_deg_rate=base_deg_rate
        )

        return {
            "is_predicted": True,
            "model_type": "CAI & BLOSUM62 Stability Model",
            "prediction_method": "CAI & BLOSUM62 Stability Model",
            "query_sequence_len": len(clean_query),
            "k_neighbors_used": "CAI & BLOSUM62 Stability Model",
            "top_match_id": top_match_id,
            "top_match_distance": top_match_dist,
            "status_message": "⚡ [Predicted via CAI & BLOSUM62 Stability Model]",
            "parameters": {
                "translation_rate": translation_rate,
                "degradation_rate": degradation_rate,
            },
            "details": {
                "cai_score": round(cai_score, 4),
                "protein_len": len(protein_query),
                "structural_penalty_norm": round(structural_penalty, 4),
                "substitutions": sub_count,
                "matched_ref_id": top_match_id,
            },
        }


class SequencePredictor:
    """Central prediction routing facade using the Strategy Pattern.

    Routes prediction requests:
    - part_type == "promoter": Routes to PromoterBiophysicsStrategy. If sequence
      length is insufficient or error occurs, safely falls back to
      KNNPredictionStrategy.
    - part_type == "cds": Routes to CDSStructuralStrategy. If translation or
      sequence errors occur, safely falls back to KNNPredictionStrategy.
    - other part_types (RBS, Terminator, etc.): Routes directly to
      KNNPredictionStrategy.
    """

    _promoter_biophysics_strategy = PromoterBiophysicsStrategy()
    _cds_structural_strategy = CDSStructuralStrategy()
    _knn_strategy = KNNPredictionStrategy()

    @classmethod
    def predict(
        cls,
        query_sequence: str,
        candidate_parts: List[Any],
        part_type: str = "promoter",
        k: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        """Predict kinetic parameters using strategy routing.

        Args:
            query_sequence: The novel DNA sequence string.
            candidate_parts: List of BiologicalPart objects from the repository.
            part_type: "promoter", "cds", etc.
            k: Number of nearest neighbors to average if k-NN fallback is used
                (default 3).

        Returns:
            Dictionary containing predicted parameter values and prediction metadata.
        """
        clean_type = (part_type or "promoter").lower().strip()

        if clean_type == "promoter":
            try:
                return cls._promoter_biophysics_strategy.predict(
                    query_sequence=query_sequence,
                    candidate_parts=candidate_parts,
                    **kwargs,
                )
            except Exception:
                # Safe fallback to legacy k-NN strategy
                return cls._knn_strategy.predict(
                    query_sequence=query_sequence,
                    candidate_parts=candidate_parts,
                    part_type=part_type,
                    k=k,
                )
        elif clean_type == "cds":
            try:
                return cls._cds_structural_strategy.predict(
                    query_sequence=query_sequence,
                    candidate_parts=candidate_parts,
                    **kwargs,
                )
            except Exception:
                # Safe fallback to legacy k-NN strategy for untranslatable or
                # frameshifted CDS
                return cls._knn_strategy.predict(
                    query_sequence=query_sequence,
                    candidate_parts=candidate_parts,
                    part_type=part_type,
                    k=k,
                )

        # Non-promoter/non-CDS parts route to k-NN strategy
        return cls._knn_strategy.predict(
            query_sequence=query_sequence,
            candidate_parts=candidate_parts,
            part_type=part_type,
            k=k,
        )

    @classmethod
    def identify_wildtype(
        cls,
        mutated_sequence: str,
        catalogue_db: Any,
        part_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Identify wild type baseline part with lowest Levenshtein distance > 0."""
        return identify_wildtype(mutated_sequence, catalogue_db, part_type=part_type)

    @classmethod
    def compare_kinetics(
        cls,
        mutated_sequence: str,
        catalogue_db: Any,
        part_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dual parameter extraction contrasting wild type baseline vs mutated
        sequence.
        """
        return compare_kinetics(mutated_sequence, catalogue_db, part_type=part_type)


def identify_wildtype(
    mutated_sequence: str,
    catalogue_db: Any,
    part_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Iterate through local parts database using Levenshtein distance logic.

    Finds and returns sequence and metadata for the part that has the lowest distance
    score strictly greater than 0 (distance > 0). This is our wild type baseline.

    Args:
        mutated_sequence: Query mutated DNA sequence.
        catalogue_db: Parts list, PartRepository, or PartsCatalogueService.
        part_type: Optional part_type filter ("promoter", "cds", etc.).

    Returns:
        Dictionary containing wild type sequence, id, name, part_type, distance,
        and part reference, or None if no candidate is found with distance > 0.
    """
    clean_mut = (mutated_sequence or "").upper().strip()
    if not clean_mut:
        return None

    if isinstance(catalogue_db, list):
        candidates = catalogue_db
    elif hasattr(catalogue_db, "get_all"):
        candidates = catalogue_db.get_all()
    elif hasattr(catalogue_db, "get_all_parts"):
        candidates = catalogue_db.get_all_parts()
    elif hasattr(catalogue_db, "_repository") and hasattr(
        catalogue_db._repository, "get_all"
    ):
        candidates = catalogue_db._repository.get_all()
    else:
        candidates = []

    target_type = part_type.lower().strip() if part_type else None

    best_part = None
    min_dist = float("inf")

    for part in candidates:
        p_seq = getattr(part, "sequence", "") or ""
        p_type = getattr(part, "part_type", "") or ""
        clean_p_seq = p_seq.upper().strip()

        if not clean_p_seq:
            continue

        if target_type and p_type.lower().strip() != target_type:
            continue

        dist = levenshtein_distance(clean_mut, clean_p_seq)

        # Filter candidates with lowest distance strictly > 0
        if dist > 0 and dist < min_dist:
            min_dist = dist
            best_part = part

    if best_part is None:
        return None

    return {
        "part": best_part,
        "id": best_part.id,
        "name": getattr(best_part, "name", best_part.id),
        "sequence": best_part.sequence,
        "part_type": getattr(best_part, "part_type", ""),
        "distance": min_dist,
        "parameters": {
            "K_d": getattr(best_part, "K_d", None),
            "y_max": getattr(best_part, "y_max", None),
            "y_min": getattr(best_part, "y_min", None),
            "n": getattr(best_part, "n", None),
            "translation_rate": getattr(best_part, "translation_rate", None),
            "degradation_rate": getattr(best_part, "degradation_rate", None),
        },
    }


def compare_kinetics(
    mutated_sequence: str,
    catalogue_db: Any,
    part_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Dual parameter extraction for wild type baseline vs mutated sequence.

    1. Identifies wild type baseline using identify_wildtype.
    2. Routes both wild type sequence and mutated sequence through the respective
       biophysics strategy (PromoterBiophysicsStrategy or CDSStructuralStrategy).
    3. Returns dictionary containing kinetic parameters for both sequences (e.g.
       wt_ymax, wt_kd, mut_ymax, mut_kd).

    Args:
        mutated_sequence: Query mutated DNA sequence.
        catalogue_db: Parts repository, service, or list of parts candidates.
        part_type: Optional explicit part_type string ("promoter" or "cds").

    Returns:
        Dictionary containing kinetic parameters for wild type and mutated sequences.
    """
    clean_mut = (mutated_sequence or "").upper().strip()
    if not clean_mut:
        raise ValueError("Mutated sequence cannot be empty.")

    wt_info = identify_wildtype(clean_mut, catalogue_db, part_type=part_type)
    if not wt_info:
        raise ValueError(
            "No wild type sequence candidate found in catalogue database with "
            "edit distance > 0."
        )

    wt_seq = wt_info["sequence"]
    effective_part_type = (
        (part_type or wt_info.get("part_type") or "promoter").lower().strip()
    )

    if isinstance(catalogue_db, list):
        candidates = catalogue_db
    elif hasattr(catalogue_db, "get_all"):
        candidates = catalogue_db.get_all()
    elif hasattr(catalogue_db, "get_all_parts"):
        candidates = catalogue_db.get_all_parts()
    elif hasattr(catalogue_db, "_repository") and hasattr(
        catalogue_db._repository, "get_all"
    ):
        candidates = catalogue_db._repository.get_all()
    else:
        candidates = []

    wt_pred = SequencePredictor.predict(
        query_sequence=wt_seq,
        candidate_parts=candidates,
        part_type=effective_part_type,
        ref_sequence=wt_seq,
    )
    mut_pred = SequencePredictor.predict(
        query_sequence=clean_mut,
        candidate_parts=candidates,
        part_type=effective_part_type,
        ref_sequence=wt_seq,
    )

    wt_params = wt_pred.get("parameters", {})
    mut_params = mut_pred.get("parameters", {})

    result = {
        "part_type": effective_part_type,
        "wildtype_info": wt_info,
        "wt_sequence": wt_seq,
        "mut_sequence": clean_mut,
        "wt_params": wt_params,
        "mut_params": mut_params,
    }

    if effective_part_type == "promoter":
        result.update(
            {
                "wt_ymax": wt_params.get("y_max", 250.0),
                "wt_kd": wt_params.get("K_d", 0.05),
                "wt_ymin": wt_params.get("y_min", 0.01),
                "wt_n": wt_params.get("n", 2.0),
                "mut_ymax": mut_params.get("y_max", 250.0),
                "mut_kd": mut_params.get("K_d", 0.05),
                "mut_ymin": mut_params.get("y_min", 0.01),
                "mut_n": mut_params.get("n", 2.0),
            }
        )
    elif effective_part_type == "cds":
        result.update(
            {
                "wt_translation_rate": wt_params.get("translation_rate", 0.1),
                "wt_degradation_rate": wt_params.get("degradation_rate", 0.01),
                "mut_translation_rate": mut_params.get("translation_rate", 0.1),
                "mut_degradation_rate": mut_params.get("degradation_rate", 0.01),
            }
        )

    return result
