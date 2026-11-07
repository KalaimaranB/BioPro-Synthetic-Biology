"""Nearest-neighbour free energies for primer secondary structure.

Computes ΔG°37 for the structures that compete with priming: a primer folding
back on itself (hairpin), a primer pairing with a copy of itself (self-dimer),
and two different primers pairing (heterodimer).

Why this is implemented here rather than wrapped
------------------------------------------------
``primer3-py`` solves exactly this problem and is the obvious thing to wrap. It
is published under **GPL-2.0-or-later** (PyPI ``license`` field and the Trove
classifier "GNU General Public License v2 or later"). This project is
distributed under the **PolyForm Noncommercial License 1.0.0** (see ``LICENSE``),
which permits only noncommercial use. GPL-2.0 §6 forbids imposing "any further
restrictions on the recipients' exercise of the rights granted herein", and a
noncommercial field-of-use restriction is such a restriction, so the two cannot
be combined in a distributed work. Since this plugin ships signed releases, the
dependency would have to be distributed. It is therefore implemented in-house.

Parameter provenance
--------------------
The stacking, initiation and terminal-AT parameters are the unified DNA
nearest-neighbour set of SantaLucia & Hicks (2004). They are read at import
from ``Bio.SeqUtils.MeltingTemp.DNA_NN4`` rather than copied into this file:
Biopython is already a dependency, its table is that paper's, and sourcing it
removes any chance of a transcription error in a 16-entry table of signed
floats. ``test_thermodynamics`` pins the values against the published numbers
so a Biopython change cannot silently move them.

What this module does and does not model
----------------------------------------
Duplex formation (both dimer kinds) is modelled completely: stacking over the
paired region, helix initiation, and the terminal-AT penalty at each end of
that region.

Hairpins are modelled by their **stem only**. A full hairpin ΔG needs loop
entropies — SantaLucia & Hicks (2004) Table 4 — that Biopython does not carry,
and inventing them would be worse than omitting them. What is returned is the
stem's stacking free energy, which is the term that decides whether the stem
holds; the loop term would make every value less stable (less negative), so the
stem-only figure is conservative: it can over-report a hairpin's stability,
never under-report it. Results are labelled ``stem-only`` in
:class:`StructureResult.model` and surfaced that way, and the rubric cutoff for
hairpins is a convention calibrated on this scale rather than a published
threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Bio.SeqUtils import MeltingTemp

#: Gas constant, kcal/(mol·K).
R_KCAL = 1.987e-3
#: Reference temperature for ΔG°37, in kelvin.
T37_K = 310.15

_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


def _load_nn_parameters() -> dict[str, tuple[float, float]]:
    """Read the SantaLucia & Hicks (2004) set from Biopython as ``(ΔH, ΔS)``."""
    return {key: (float(dh), float(ds)) for key, (dh, ds) in MeltingTemp.DNA_NN4.items()}


#: ``{"AA/TT": (ΔH kcal/mol, ΔS cal/(mol·K)), ...}`` plus the initiation terms.
NN_PARAMS: dict[str, tuple[float, float]] = _load_nn_parameters()


def complement(base: str) -> str:
    return _COMPLEMENT.get(base.upper(), "N")


def reverse_complement(seq: str) -> str:
    return "".join(complement(b) for b in reversed(seq.upper()))


def is_pair(a: str, b: str) -> bool:
    """True when ``a`` and ``b`` are Watson-Crick partners."""
    return _COMPLEMENT.get(a.upper()) == b.upper()


def _stack_key(top_pair: tuple[str, str], next_pair: tuple[str, str]) -> str | None:
    """The NN table key for two adjacent base pairs, or None if not tabulated.

    The table stores one orientation of each stack ("AA/TT" but not "TT/AA");
    the two are thermodynamically identical, so the reversed form is tried too.
    """
    a1, b1 = top_pair[0].upper(), top_pair[1].upper()
    a2, b2 = next_pair[0].upper(), next_pair[1].upper()
    forward = f"{a1}{a2}/{b1}{b2}"
    if forward in NN_PARAMS:
        return forward
    reverse = f"{b2}{b1}/{a2}{a1}"
    if reverse in NN_PARAMS:
        return reverse
    return None


def duplex_enthalpy_entropy(top: str, bottom: str) -> tuple[float, float]:
    """ΔH, ΔS for a fully complementary duplex, 5'->3' over 3'->5'.

    ``top`` and ``bottom`` are the two strands written so that ``top[i]`` pairs
    with ``bottom[i]``. Includes helix initiation and a terminal-AT penalty at
    each end, which is what the published model specifies.

    Raises:
        ValueError: the strands differ in length, or are shorter than 2 bases.
    """
    top, bottom = top.upper(), bottom.upper()
    if len(top) != len(bottom):
        raise ValueError("duplex strands must be the same length")
    if len(top) < 2:  # noqa: PLR2004 - a single pair has no stack to sum
        raise ValueError("a duplex needs at least two base pairs")

    dh, ds = NN_PARAMS["init"]

    for index in range(len(top) - 1):
        key = _stack_key((top[index], bottom[index]), (top[index + 1], bottom[index + 1]))
        if key is None:
            # A mismatch inside the run: the unified set has no stack for it.
            # Callers only build fully-paired runs, so this is defensive.
            continue
        stack_dh, stack_ds = NN_PARAMS[key]
        dh += stack_dh
        ds += stack_ds

    # Terminal AT penalty, applied once per helix end that is an A·T pair.
    penalty_dh, penalty_ds = NN_PARAMS["init_A/T"]
    for end_top in (top[0], top[-1]):
        if end_top in ("A", "T"):
            dh += penalty_dh
            ds += penalty_ds

    return dh, ds


def delta_g_37(delta_h: float, delta_s: float) -> float:
    """ΔG°37 in kcal/mol from ΔH (kcal/mol) and ΔS (cal/(mol·K))."""
    return delta_h - T37_K * (delta_s / 1000.0)


def duplex_delta_g(top: str, bottom: str) -> float:
    """ΔG°37 for a fully complementary duplex, in kcal/mol."""
    dh, ds = duplex_enthalpy_entropy(top, bottom)
    return delta_g_37(dh, ds)


@dataclass(frozen=True)
class StructureResult:
    """One predicted secondary structure.

    Attributes:
        delta_g: ΔG°37 in kcal/mol. 0.0 when no structure was found; more
            negative means more stable.
        kind: ``hairpin``, ``self_dimer`` or ``hetero_dimer``.
        model: What was actually computed, e.g. ``stem-only``. Surfaced so a
            reader is never shown an approximation as if it were complete.
        involves_three_prime: Whether the structure reaches a 3' end, within
            the window the caller passed. 3'-anchored structures are the ones
            that actually block extension.
        alignment: Human-readable rendering of the pairing, for the UI.
        base_pairs: Number of paired bases in the structure.
    """

    delta_g: float = 0.0
    kind: str = ""
    model: str = "nearest-neighbour"
    involves_three_prime: bool = False
    alignment: str = ""
    base_pairs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_g": round(self.delta_g, 2),
            "kind": self.kind,
            "model": self.model,
            "involves_three_prime": self.involves_three_prime,
            "alignment": self.alignment,
            "base_pairs": self.base_pairs,
        }


def _scan_duplex(
    seq_a: str,
    seq_b: str,
    kind: str,
    three_prime_window: int,
    min_pairs: int = 2,
) -> StructureResult:
    """Most stable duplex between ``seq_a`` and the reverse of ``seq_b``.

    Slides one strand past the other and, at each offset, scores every maximal
    run of consecutive complementary bases. The most negative ΔG found wins.

    ``seq_a`` and ``seq_b`` are given 5'->3'. ``seq_b`` is walked in reverse so
    that the two run antiparallel, which is how they would actually anneal.
    """
    a = seq_a.upper()
    b_rev = seq_b.upper()[::-1]
    best = StructureResult(kind=kind)

    for offset in range(-(len(b_rev) - 1), len(a)):
        run_start: int | None = None
        run_length = 0

        # +1 so a run ending at the last position is still closed and scored.
        for i in range(len(a) + 1):
            j = i - offset
            paired = i < len(a) and 0 <= j < len(b_rev) and is_pair(a[i], b_rev[j])
            if paired:
                if run_start is None:
                    run_start = i
                run_length += 1
                continue
            if run_start is not None and run_length >= min_pairs:
                top = a[run_start : run_start + run_length]
                bottom = b_rev[run_start - offset : run_start - offset + run_length]
                dh, ds = duplex_enthalpy_entropy(top, bottom)
                dg = delta_g_37(dh, ds)
                if dg < best.delta_g:
                    end_a = run_start + run_length
                    # seq_b's 3' end is index 0 of the reversed strand.
                    start_b = run_start - offset
                    touches_three_prime = (
                        end_a > len(a) - three_prime_window or start_b < three_prime_window
                    )
                    best = StructureResult(
                        delta_g=dg,
                        kind=kind,
                        involves_three_prime=touches_three_prime,
                        alignment=f"5'-{top}-3' / 3'-{bottom}-5'",
                        base_pairs=run_length,
                    )
            run_start = None
            run_length = 0

    return best


def self_dimer(seq: str, three_prime_window: int = 5) -> StructureResult:
    """Most stable duplex between a primer and a second copy of itself."""
    return _scan_duplex(seq, seq, "self_dimer", three_prime_window)


def hetero_dimer(seq_a: str, seq_b: str, three_prime_window: int = 5) -> StructureResult:
    """Most stable duplex between two different primers."""
    return _scan_duplex(seq_a, seq_b, "hetero_dimer", three_prime_window)


def hairpin(
    seq: str, min_stem: int = 3, min_loop: int = 3, three_prime_window: int = 5
) -> StructureResult:
    """Most stable hairpin stem in ``seq``.

    Returns the **stem** stacking free energy only; see the module docstring
    for why the loop term is absent and why that is conservative. ``min_loop``
    of 3 is the smallest sterically possible hairpin loop.
    """
    s = seq.upper()
    best = StructureResult(kind="hairpin", model="stem-only")

    for loop_start in range(len(s)):
        for loop_end in range(loop_start + min_loop, len(s)):
            # Grow the stem outward from the bases flanking the loop.
            stem = 0
            while (
                loop_start - stem - 1 >= 0
                and loop_end + stem + 1 < len(s)
                and is_pair(s[loop_start - stem - 1], s[loop_end + stem + 1])
            ):
                stem += 1
            if stem < min_stem:
                continue

            top = s[loop_start - stem : loop_start]
            bottom = s[loop_end + 1 : loop_end + 1 + stem][::-1]
            dh, ds = duplex_enthalpy_entropy(top, bottom)
            dg = delta_g_37(dh, ds)
            if dg < best.delta_g:
                best = StructureResult(
                    delta_g=dg,
                    kind="hairpin",
                    model="stem-only",
                    involves_three_prime=loop_end + 1 + stem > len(s) - three_prime_window,
                    alignment=f"stem 5'-{top}-3' / 3'-{bottom}-5', loop {loop_end - loop_start + 1} nt",
                    base_pairs=stem,
                )

    return best
