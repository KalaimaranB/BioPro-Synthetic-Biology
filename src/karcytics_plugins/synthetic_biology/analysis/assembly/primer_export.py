"""Turn a ranked primer candidate into something a student can submit.

For BIOL341 the exported primer set *is* the graded 5% deliverable, so this is
not a convenience: without it the tab produces numbers nobody can hand in or
order. Before this module there was no way to get a primer out of the
application at all.

What an export carries, and why each field is there:

* **Both sequences.** The full oligo is what you order; the annealing region is
  what the Tm and GC describe. A 5' restriction tail is in the first and not
  the second, and conflating them is the defect this workflow started with, so
  they are separate columns and the tail is named in its own.
* **Every rubric check**, with the value observed, the threshold it was judged
  against, and where that threshold came from. A marker can see not just that
  a primer passed but what it was asked to pass.
* **The methods paragraph with numbered references**, so the write-up and the
  primers that produced it travel together and cannot drift apart.

Building the rows lives here rather than in a view: the content is engine data
and scientific judgement, and a view that assembled it would be deciding what
a pass means. The view only chooses a filename and writes bytes.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

import csv
import io
from typing import Any

#: Columns in the CSV, in order. Stable so a marking script can rely on them.
CSV_COLUMNS: tuple[str, ...] = (
    "name",
    "direction",
    "full_oligo",
    "tail",
    "tail_enzyme",
    "annealing_region",
    "annealing_length_nt",
    "full_length_nt",
    "annealing_tm_c",
    "annealing_gc_percent",
    "three_prime_clamp",
    "product_bp",
    "verdict",
)


def _clamp_status(checks: Any) -> str:
    """Report the 3' clamp result as text, reading the engine's own check."""
    for check in checks or ():
        data = check if isinstance(check, dict) else check.to_dict()
        if data.get("name") == "three_prime_clamp":
            observed = data.get("observed_value")
            passed = data.get("passed")
            state = {True: "pass", False: "fail", None: "not run"}[passed]
            return f"{observed} G/C ({state})"
    return "not evaluated"


def _as_dict(check: Any) -> dict[str, Any]:
    return check if isinstance(check, dict) else check.to_dict()


def primer_rows(candidate: dict[str, Any], tail_enzymes: Any = ()) -> list[dict[str, Any]]:
    """One row per primer, with the annealing region kept distinct from the oligo."""
    checks = candidate.get("checks") or []
    summary = candidate.get("summary") or {}
    enzymes = list(tail_enzymes or [])
    rows: list[dict[str, Any]] = []

    for index, key in enumerate(("forward", "reverse")):
        primer = candidate.get(key)
        if primer is None:
            continue
        tail = getattr(primer, "overhang", "") or ""
        full = getattr(primer, "sequence", "") or ""
        anneal = full[len(tail) :] if tail and full.startswith(tail) else full
        rows.append(
            {
                "name": getattr(primer, "name", key),
                "direction": getattr(primer, "direction", key[:3].upper()),
                "full_oligo": full,
                "tail": tail,
                "tail_enzyme": enzymes[index] if index < len(enzymes) else "",
                "annealing_region": anneal,
                "annealing_length_nt": len(anneal),
                "full_length_nt": len(full),
                "annealing_tm_c": round(float(getattr(primer, "calculated_tm", 0.0)), 2),
                "annealing_gc_percent": round(float(getattr(primer, "gc_content", 0.0)), 1),
                "three_prime_clamp": _clamp_status(checks),
                "product_bp": candidate.get("product_bp", ""),
                "verdict": summary.get("verdict", ""),
            }
        )
    return rows


def check_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per rubric check: what was measured, against what, and on whose authority."""
    rows = []
    for check in candidate.get("checks") or []:
        data = _as_dict(check)
        rows.append(
            {
                "check": data.get("name", ""),
                "result": {True: "pass", False: "fail", None: "not run"}[data.get("passed")],
                "observed": data.get("observed_value"),
                "threshold": data.get("threshold", ""),
                "basis": data.get("provenance_label") or data.get("provenance", ""),
                "mechanism": ", ".join(data.get("mechanism") or ()),
                "note": data.get("message", ""),
                "what_to_do": data.get("remediation", ""),
            }
        )
    return rows


def to_csv(
    candidate: dict[str, Any],
    *,
    methods: str = "",
    tail_enzymes: Any = (),
    rubric_name: str = "",
) -> str:
    """The submission: primers, then every check, then the methods paragraph.

    One file rather than three, because a primer table that has drifted apart
    from the rubric it was judged against is worse than no export.
    """
    out = io.StringIO()
    writer = csv.writer(out)

    writer.writerow(["# Primer design export"])
    if rubric_name:
        writer.writerow([f"# Rubric: {rubric_name}"])
    writer.writerow([])

    writer.writerow(["PRIMERS"])
    writer.writerow(list(CSV_COLUMNS))
    for row in primer_rows(candidate, tail_enzymes):
        writer.writerow([row[column] for column in CSV_COLUMNS])

    checks = check_rows(candidate)
    if checks:
        writer.writerow([])
        writer.writerow(["RUBRIC CHECKS"])
        headers = [
            "check",
            "result",
            "observed",
            "threshold",
            "basis",
            "mechanism",
            "note",
            "what_to_do",
        ]
        writer.writerow(headers)
        for row in checks:
            writer.writerow([row[h] for h in headers])

    if methods:
        writer.writerow([])
        writer.writerow(["METHODS"])
        # One cell per line keeps the paragraph readable in a spreadsheet
        # instead of collapsing into a single unreadable row.
        for line in methods.splitlines():
            writer.writerow([line])

    return out.getvalue()


def to_fasta(candidate: dict[str, Any], *, annealing_only: bool = False) -> str:
    """FASTA of the oligos, for ordering or for feeding another tool.

    The description line carries Tm and GC so the numbers survive the format,
    and says which of the two sequences this is — ordering the annealing
    region when you meant the tailed oligo is an expensive mistake.
    """
    blocks = []
    for row in primer_rows(candidate):
        sequence = row["annealing_region"] if annealing_only else row["full_oligo"]
        kind = "annealing region only" if annealing_only else "full oligo, tail included"
        header = (
            f">{row['name']} {row['direction']} | {kind} | "
            f"{len(sequence)} nt | Tm {row['annealing_tm_c']} C "
            f"(annealing region) | GC {row['annealing_gc_percent']}%"
        )
        blocks.append(f"{header}\n{sequence}")
    return "\n".join(blocks) + ("\n" if blocks else "")


def clipboard_text(primer: Any) -> str:
    """One primer as a single line, for pasting into an order form."""
    tail = getattr(primer, "overhang", "") or ""
    full = getattr(primer, "sequence", "") or ""
    anneal = full[len(tail) :] if tail and full.startswith(tail) else full
    parts = [full]
    if tail:
        parts.append(f"(tail {tail} + annealing {anneal})")
    parts.append(f"Tm {float(getattr(primer, 'calculated_tm', 0.0)):.1f} C")
    parts.append(f"GC {float(getattr(primer, 'gc_content', 0.0)):.1f}%")
    return "  ".join(parts)


__all__ = [
    "CSV_COLUMNS",
    "check_rows",
    "clipboard_text",
    "primer_rows",
    "to_csv",
    "to_fasta",
]
