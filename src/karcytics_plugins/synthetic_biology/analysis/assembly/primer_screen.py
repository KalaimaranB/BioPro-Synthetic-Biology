"""Judge a primer, or a primer pair, against a rubric.

Pure functions over plain data: no Qt, no I/O, no global state. Every decision
a user sees about a primer is made here, so a view can only ever display a
:class:`RubricCheck` — it never re-derives a pass or a fail.

Three properties the checks hold to:

* **Nothing is silently skipped.** A check that cannot run returns
  ``passed=None`` with a reason, and still appears in the list. A missing
  template is a different answer from a clean pass, and the two never collapse.
* **The annealing region is what is judged.** A primer carrying a 5'
  restriction tail does not anneal along its full length on the first cycle, so
  GC content, Tm and the 3' clamp are computed on the annealing region. Tail
  composition is reported separately, never folded in.
* **Every check carries its numbers.** ``observed_value`` and ``threshold``
  travel with the result so a view can show "52.4% (40-60%)" without knowing
  what a GC window is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .primer_rubric import THRESHOLD_PROVENANCE, PrimerRubric
from .thermodynamics import StructureResult, hairpin, hetero_dimer, self_dimer

#: Check names, so callers and tests refer to them by constant rather than text.
GC_CONTENT = "gc_content"
THREE_PRIME_CLAMP = "three_prime_clamp"
POLY_RUN = "poly_run"
HAIRPIN = "hairpin"
SELF_DIMER = "self_dimer"
PAIR_TM_MATCH = "pair_tm_match"
HETERO_DIMER = "hetero_dimer"
PRODUCT_SIZE = "product_size"
TEMPLATE_UNIQUENESS = "template_uniqueness"

#: Checks that judge one primer on its own.
SINGLE_CHECKS: tuple[str, ...] = (GC_CONTENT, THREE_PRIME_CLAMP, POLY_RUN, HAIRPIN, SELF_DIMER)
#: Checks that need both primers, or the template.
PAIR_CHECKS: tuple[str, ...] = (PAIR_TM_MATCH, HETERO_DIMER, PRODUCT_SIZE, TEMPLATE_UNIQUENESS)


@dataclass(frozen=True)
class RubricCheck:
    """One rubric criterion applied to a primer or pair.

    Attributes:
        name: One of the module's check-name constants.
        passed: True, False, or None when the check could not be evaluated.
        observed_value: What was measured. None when not evaluated.
        threshold: The bound applied, as text, e.g. ``"40.0-60.0 %"``.
        message: A sentence for a human, including the reason when skipped.
        provenance: ``convention`` or ``sourced`` — whether the threshold is a
            community rule of thumb or follows from a published model. Carried
            so the UI can label it without deciding for itself.
        detail: Optional structure data, e.g. a dimer alignment.
    """

    name: str
    passed: bool | None
    message: str
    observed_value: float | str | None = None
    threshold: str = ""
    provenance: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def skipped(self) -> bool:
        return self.passed is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "provenance": self.provenance,
            "detail": dict(self.detail),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RubricCheck:
        return cls(
            name=data.get("name", ""),
            passed=data.get("passed"),
            message=data.get("message", ""),
            observed_value=data.get("observed_value"),
            threshold=data.get("threshold", ""),
            provenance=data.get("provenance", ""),
            detail=dict(data.get("detail") or {}),
        )


def _provenance_of(*fields: str) -> str:
    """The provenance shared by the rubric fields a check uses."""
    kinds = {THRESHOLD_PROVENANCE[f][0] for f in fields if f in THRESHOLD_PROVENANCE}
    return kinds.pop() if len(kinds) == 1 else "mixed"


def gc_percent(seq: str) -> float:
    """GC content of ``seq`` as a percentage; 0.0 for an empty string."""
    s = seq.upper()
    if not s:
        return 0.0
    return 100.0 * (s.count("G") + s.count("C")) / len(s)


def longest_homopolymer(seq: str) -> tuple[int, str]:
    """Length and base of the longest single-base run in ``seq``."""
    best_len, best_base = 0, ""
    for match in re.finditer(r"(.)\1*", seq.upper()):
        run = match.group(0)
        if len(run) > best_len:
            best_len, best_base = len(run), run[0]
    return best_len, best_base


def annealing_region(sequence: str, overhang: str) -> str:
    """The part of ``sequence`` that anneals: everything after the 5' tail.

    A tail is only a tail if the sequence actually starts with it; otherwise
    the full sequence is returned rather than blindly trimming a length.
    """
    if overhang and sequence.upper().startswith(overhang.upper()):
        return sequence[len(overhang) :]
    return sequence


# ── Single-primer checks ───────────────────────────────────────────────


def check_gc_content(anneal: str, rubric: PrimerRubric) -> RubricCheck:
    threshold = f"{rubric.gc_min_percent:g}-{rubric.gc_max_percent:g} %"
    prov = _provenance_of("gc_min_percent", "gc_max_percent")
    if not anneal:
        return RubricCheck(
            GC_CONTENT, None, "No annealing region to measure.", None, threshold, prov
        )
    value = gc_percent(anneal)
    passed = rubric.gc_min_percent <= value <= rubric.gc_max_percent
    return RubricCheck(
        GC_CONTENT,
        passed,
        f"GC content of the annealing region is {value:.1f}% ({threshold} required).",
        round(value, 1),
        threshold,
        prov,
    )


def check_three_prime_clamp(anneal: str, rubric: PrimerRubric) -> RubricCheck:
    threshold = f"{rubric.clamp_min_gc}-{rubric.clamp_max_gc} G/C in last {rubric.clamp_window}"
    prov = _provenance_of("clamp_min_gc", "clamp_max_gc", "clamp_window")
    if len(anneal) < rubric.clamp_window:
        return RubricCheck(
            THREE_PRIME_CLAMP,
            None,
            f"Annealing region is shorter than the {rubric.clamp_window} nt clamp window.",
            None,
            threshold,
            prov,
        )
    window = anneal[-rubric.clamp_window :].upper()
    count = window.count("G") + window.count("C")
    passed = rubric.clamp_min_gc <= count <= rubric.clamp_max_gc
    return RubricCheck(
        THREE_PRIME_CLAMP,
        passed,
        f"The last {rubric.clamp_window} bases ({window}) contain {count} G/C ({threshold}).",
        count,
        threshold,
        prov,
    )


def check_poly_run(anneal: str, rubric: PrimerRubric) -> RubricCheck:
    threshold = f"<= {rubric.max_poly_run}"
    prov = _provenance_of("max_poly_run")
    if not anneal:
        return RubricCheck(POLY_RUN, None, "No annealing region to measure.", None, threshold, prov)
    length, base = longest_homopolymer(anneal)
    passed = length <= rubric.max_poly_run
    return RubricCheck(
        POLY_RUN,
        passed,
        f"Longest single-base run is {length} ({base * length or '-'}); {threshold} allowed.",
        length,
        threshold,
        prov,
    )


def _structure_check(
    name: str, result: StructureResult, cutoff: float, strict_cutoff: float
) -> RubricCheck:
    """Shared body for hairpin and dimer checks.

    A structure that reaches a 3' end is judged against ``strict_cutoff``,
    because that is the end extension initiates from.
    """
    applied = strict_cutoff if result.involves_three_prime else cutoff
    threshold = f">= {applied:g} kcal/mol"
    passed = result.delta_g >= applied
    where = "at a 3' end" if result.involves_three_prime else "internal"
    if result.base_pairs == 0:
        message = "No structure found."
    else:
        message = (
            f"Most stable {name.replace('_', ' ')} is {result.delta_g:.2f} kcal/mol "
            f"over {result.base_pairs} bp ({where}); {threshold}."
        )
        if result.model != "nearest-neighbour":
            message += f" Model: {result.model}."
    return RubricCheck(
        name,
        passed,
        message,
        round(result.delta_g, 2),
        threshold,
        _provenance_of(f"{name}_min_dg"),
        result.to_dict(),
    )


def check_hairpin(anneal_or_full: str, rubric: PrimerRubric) -> RubricCheck:
    result = hairpin(anneal_or_full, three_prime_window=rubric.three_prime_window)
    return _structure_check(HAIRPIN, result, rubric.hairpin_min_dg, rubric.three_prime_dimer_min_dg)


def check_self_dimer(anneal_or_full: str, rubric: PrimerRubric) -> RubricCheck:
    result = self_dimer(anneal_or_full, three_prime_window=rubric.three_prime_window)
    return _structure_check(
        SELF_DIMER, result, rubric.self_dimer_min_dg, rubric.three_prime_dimer_min_dg
    )


def screen_primer(
    sequence: str, overhang: str = "", rubric: PrimerRubric | None = None
) -> list[RubricCheck]:
    """Every single-primer check, in a stable order.

    Composition checks use the annealing region; structure checks use the full
    oligo, because a 5' tail folds and dimerises even though it does not anneal
    in the first cycle.
    """
    rub = rubric or PrimerRubric()
    anneal = annealing_region(sequence, overhang)
    return [
        check_gc_content(anneal, rub),
        check_three_prime_clamp(anneal, rub),
        check_poly_run(anneal, rub),
        check_hairpin(sequence, rub),
        check_self_dimer(sequence, rub),
    ]


# ── Pair checks ────────────────────────────────────────────────────────


def check_pair_tm(
    forward_tm: float | None, reverse_tm: float | None, rubric: PrimerRubric
) -> RubricCheck:
    threshold = f"<= {rubric.pair_tm_tolerance:g} °C apart"
    prov = _provenance_of("pair_tm_tolerance")
    if forward_tm is None or reverse_tm is None:
        return RubricCheck(
            PAIR_TM_MATCH, None, "A melting temperature is missing.", None, threshold, prov
        )
    diff = abs(forward_tm - reverse_tm)
    return RubricCheck(
        PAIR_TM_MATCH,
        diff <= rubric.pair_tm_tolerance,
        f"Pair melting temperatures differ by {diff:.2f} °C ({threshold}).",
        round(diff, 2),
        threshold,
        prov,
    )


def check_hetero_dimer(fwd_seq: str, rev_seq: str, rubric: PrimerRubric) -> RubricCheck:
    result = hetero_dimer(fwd_seq, rev_seq, three_prime_window=rubric.three_prime_window)
    return _structure_check(
        HETERO_DIMER, result, rubric.hetero_dimer_min_dg, rubric.three_prime_dimer_min_dg
    )


def check_product_size(product_bp: int | None, rubric: PrimerRubric) -> RubricCheck:
    threshold = f"{rubric.product_min_bp}-{rubric.product_max_bp} bp"
    prov = _provenance_of("product_min_bp", "product_max_bp")
    if product_bp is None:
        return RubricCheck(
            PRODUCT_SIZE,
            None,
            "Product size is unknown without both binding positions on the template.",
            None,
            threshold,
            prov,
        )
    passed = rubric.product_min_bp <= product_bp <= rubric.product_max_bp
    return RubricCheck(
        PRODUCT_SIZE,
        passed,
        f"Product is {product_bp:,} bp ({threshold}).",
        product_bp,
        threshold,
        prov,
    )


def count_binding_sites(template: str, anneal: str) -> int:
    """Occurrences of ``anneal`` on either strand of ``template``.

    Overlapping matches are counted; a primer that matches twice in overlapping
    register still has two places to start.
    """
    from .thermodynamics import reverse_complement

    if not template or not anneal:
        return 0
    t, a = template.upper(), anneal.upper()
    rc = reverse_complement(a)

    def occurrences(needle: str) -> int:
        return sum(1 for i in range(len(t) - len(needle) + 1) if t[i : i + len(needle)] == needle)

    # A palindromic primer matches itself on both strands; count it once.
    return occurrences(a) + (occurrences(rc) if rc != a else 0)


def check_template_uniqueness(
    template: str | None, fwd_anneal: str, rev_anneal: str
) -> RubricCheck:
    """Each primer must have exactly one binding site on the template.

    ``rev_anneal`` is given as the primer is synthesised (5'->3'), so it is its
    own reverse complement that appears on the top strand; ``count_binding_sites``
    searches both strands and so handles either.
    """
    threshold = "exactly 1 site per primer"
    if not template:
        return RubricCheck(
            TEMPLATE_UNIQUENESS,
            None,
            "No template supplied, so binding sites could not be counted.",
            None,
            threshold,
            "",
        )
    fwd_hits = count_binding_sites(template, fwd_anneal)
    rev_hits = count_binding_sites(template, rev_anneal)
    passed = fwd_hits == 1 and rev_hits == 1
    return RubricCheck(
        TEMPLATE_UNIQUENESS,
        passed,
        f"Forward binds {fwd_hits}x and reverse binds {rev_hits}x on the template ({threshold}).",
        f"{fwd_hits}/{rev_hits}",
        threshold,
        "",
        {"forward_sites": fwd_hits, "reverse_sites": rev_hits},
    )


def screen_pair(  # noqa: PLR0913 - one argument per input the pair checks need; grouping them into a struct would only move the list
    fwd_sequence: str,
    rev_sequence: str,
    forward_tm: float | None,
    reverse_tm: float | None,
    *,
    fwd_overhang: str = "",
    rev_overhang: str = "",
    product_bp: int | None = None,
    template: str | None = None,
    rubric: PrimerRubric | None = None,
) -> list[RubricCheck]:
    """Every pair-level check, in a stable order."""
    rub = rubric or PrimerRubric()
    return [
        check_pair_tm(forward_tm, reverse_tm, rub),
        check_hetero_dimer(fwd_sequence, rev_sequence, rub),
        check_product_size(product_bp, rub),
        check_template_uniqueness(
            template,
            annealing_region(fwd_sequence, fwd_overhang),
            annealing_region(rev_sequence, rev_overhang),
        ),
    ]


# ── Summary ────────────────────────────────────────────────────────────


def summarise(checks: list[RubricCheck]) -> dict[str, Any]:
    """Counts plus a single verdict for a list of checks.

    ``verdict`` is ``pass`` only when nothing failed *and* nothing was skipped;
    an unevaluated check is reported as ``incomplete`` rather than being waved
    through, since a student would otherwise read a partial screen as a clean
    one.
    """
    failed = [c for c in checks if c.passed is False]
    skipped = [c for c in checks if c.passed is None]
    if failed:
        verdict = "fail"
    elif skipped:
        verdict = "incomplete"
    else:
        verdict = "pass"
    return {
        "verdict": verdict,
        "passed": sum(1 for c in checks if c.passed is True),
        "failed": len(failed),
        "skipped": len(skipped),
        "failed_names": [c.name for c in failed],
        "skipped_names": [c.name for c in skipped],
    }


def score(checks: list[RubricCheck]) -> float:
    """Rank a candidate: fraction of evaluated checks that passed, 0.0-1.0.

    Skipped checks are excluded from the denominator rather than counted as
    failures, so a candidate is not punished for a check the caller could not
    supply inputs for.
    """
    evaluated = [c for c in checks if c.passed is not None]
    if not evaluated:
        return 0.0
    return sum(1 for c in evaluated if c.passed) / len(evaluated)
