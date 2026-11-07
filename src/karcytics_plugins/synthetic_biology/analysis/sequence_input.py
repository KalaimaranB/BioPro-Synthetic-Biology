"""Validate and normalise a DNA sequence before any engine touches it.

Why this exists
---------------
The nearest-neighbour tables that produce Tm have parameters for A, C, G and T
and nothing else. Before this module, a sequence containing ``U`` or ``N`` —
or a pasted GenBank ORIGIN block, digits and all — still produced a confident
melting temperature and GC percentage. Those numbers were fabricated: the model
cannot represent those residues, and nothing said so. On a graded deliverable
that is the most dangerous kind of defect, because it is confidently wrong
rather than obviously broken.

The contract
------------
Three outcomes, never a silent fourth:

* **Accepted** — plain ACGT, in any case, with any whitespace or line breaks.
* **Transformed, and reported** — a FASTA header, a multi-line body, a GenBank
  ORIGIN block, or RNA. Each transformation is named in
  :attr:`CleanSequence.transformations` so a caller can say "I converted RNA to
  DNA" rather than doing it behind the user's back.
* **Refused, with a reason** — ambiguity codes (N and friends), stray digits,
  any other residual character, or nothing at all. Refusals name the offending
  characters and where they are.

Nothing is ever silently dropped. There is a bad precedent in this codebase —
``sequence_predictor`` used to do ``"".join(c for c in q.upper() if c in
"ACGTN")``, which discards whatever it does not recognise and quietly admits
N — and this module exists partly so that pattern has a replacement.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: The only residues the thermodynamic model can represent.
DNA_BASES = frozenset("ACGT")

#: IUPAC ambiguity codes. Refused rather than expanded: a primer that might be
#: any of four sequences has no single Tm, and guessing one would be the same
#: fabrication this module exists to stop.
AMBIGUITY_CODES: dict[str, str] = {
    "N": "any base",
    "R": "A or G",
    "Y": "C or T",
    "S": "G or C",
    "W": "A or T",
    "K": "G or T",
    "M": "A or C",
    "B": "C, G or T",
    "D": "A, G or T",
    "H": "A, C or T",
    "V": "A, C or G",
}

#: A GenBank ORIGIN line: leading coordinate, then space-separated 10-mers.
_ORIGIN_LINE = re.compile(r"^\s*\d+\s+(?P<body>[A-Za-z\s]+)$")

#: A FASTA description line.
_FASTA_HEADER = re.compile(r"^\s*[>;]")


@dataclass(frozen=True)
class SequenceIssue:
    """One reason a sequence was refused."""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class CleanSequence:
    """The result of validating a sequence: what it became and what it cost.

    Attributes:
        sequence: The cleaned ACGT sequence. Empty when the input was refused.
        transformations: Human-readable notes, one per change applied. Shown to
            the user so a conversion is never invisible.
        refusals: Why the sequence cannot be used. Empty means it is usable.
        original_length: Length of the raw input, for reporting.
    """

    sequence: str
    transformations: tuple[str, ...] = ()
    refusals: tuple[SequenceIssue, ...] = ()
    original_length: int = 0

    @property
    def ok(self) -> bool:
        """True when the sequence can be handed to an engine."""
        return not self.refusals and bool(self.sequence)

    @property
    def was_transformed(self) -> bool:
        return bool(self.transformations)

    def summary(self) -> str:
        """One line a view can show without composing anything itself."""
        if self.refusals:
            return " ".join(issue.message for issue in self.refusals)
        if self.transformations:
            return f"{len(self.sequence)} bp. " + " ".join(self.transformations)
        return f"{len(self.sequence)} bp."

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "ok": self.ok,
            "transformations": list(self.transformations),
            "refusals": [issue.to_dict() for issue in self.refusals],
            "original_length": self.original_length,
            "summary": self.summary(),
        }


class SequenceRejectedError(ValueError):
    """Raised by :func:`require_sequence` when a sequence cannot be used."""

    def __init__(self, result: CleanSequence) -> None:
        super().__init__(result.summary())
        self.result = result
        self.issues = result.refusals


# ── Cleaning steps ─────────────────────────────────────────────────────


def _strip_markup(raw: str) -> tuple[str, list[str]]:
    """Remove FASTA headers and GenBank ORIGIN coordinates, reporting each."""
    notes: list[str] = []
    kept: list[str] = []
    headers = 0
    origin_lines = 0

    for line in raw.splitlines() or [raw]:
        if _FASTA_HEADER.match(line):
            headers += 1
            continue
        match = _ORIGIN_LINE.match(line)
        if match and re.search(r"[A-Za-z]", line):
            # A leading number followed only by bases and spaces is a GenBank
            # ORIGIN row; the number is a coordinate, not sequence.
            origin_lines += 1
            kept.append(match.group("body"))
            continue
        kept.append(line)

    if headers:
        notes.append(f"Ignored {headers} FASTA header line{'s' if headers > 1 else ''}.")
    if origin_lines:
        notes.append(
            f"Read {origin_lines} GenBank ORIGIN line"
            f"{'s' if origin_lines > 1 else ''} and dropped their position numbers."
        )
    return "\n".join(kept), notes


def _describe_offenders(text: str) -> list[SequenceIssue]:
    """Name every character that cannot be part of a DNA sequence."""
    issues: list[SequenceIssue] = []

    ambiguous = sorted({c for c in text if c in AMBIGUITY_CODES})
    if ambiguous:
        described = ", ".join(f"{c} ({AMBIGUITY_CODES[c]})" for c in ambiguous)
        count = sum(text.count(c) for c in ambiguous)
        issues.append(
            SequenceIssue(
                "ambiguity",
                f"Sequence contains {count} ambiguity code"
                f"{'s' if count > 1 else ''}: {described}. "
                "A position that could be more than one base has no single "
                "melting temperature, so no primer can be designed across it. "
                "Replace the ambiguous positions with the actual bases, or "
                "choose a region that does not span them.",
            )
        )

    digits = sorted({c for c in text if c.isdigit()})
    if digits:
        issues.append(
            SequenceIssue(
                "digits",
                f"Sequence contains digits ({', '.join(digits)}) that are not "
                "part of a recognised GenBank ORIGIN layout. If you pasted "
                "numbered sequence, include the whole ORIGIN block so the "
                "position numbers can be identified and removed.",
            )
        )

    others = sorted(
        {c for c in text if c not in DNA_BASES and c not in AMBIGUITY_CODES and not c.isdigit()}
    )
    if others:
        shown = ", ".join(repr(c) for c in others[:8])
        issues.append(
            SequenceIssue(
                "unrecognised",
                f"Sequence contains characters that are not DNA bases: {shown}. "
                "Expected only A, C, G and T.",
            )
        )
    return issues


def clean_sequence(raw: str | None, *, label: str = "Sequence") -> CleanSequence:
    """Validate and normalise ``raw``, reporting every change and every refusal.

    Args:
        raw: The sequence as the user supplied it.
        label: What to call it in messages, e.g. ``"Forward primer"``.

    Returns:
        A :class:`CleanSequence`. Check ``.ok`` before using ``.sequence``;
        a refused input yields an empty sequence rather than a partial one,
        because a partially cleaned sequence is exactly the silent corruption
        this function exists to prevent.
    """
    text = "" if raw is None else str(raw)
    original_length = len(text)

    if not text.strip():
        return CleanSequence(
            "",
            refusals=(
                SequenceIssue("empty", f"{label} is empty. Paste or select a DNA sequence."),
            ),
            original_length=original_length,
        )

    stripped, notes = _strip_markup(text)

    had_whitespace = bool(re.search(r"\s", stripped.strip()))
    compact = "".join(stripped.split())
    if had_whitespace:
        notes.append("Removed whitespace and line breaks.")

    if compact != compact.upper():
        notes.append("Converted to upper case.")
    compact = compact.upper()

    uracil = compact.count("U")
    if uracil and "T" not in compact:
        # RNA: convert, and say so. Mixed U and T is not RNA, it is a mistake,
        # so it falls through to the refusal path below.
        compact = compact.replace("U", "T")
        notes.append(f"Converted RNA to DNA ({uracil} U -> T).")
    elif uracil:
        return CleanSequence(
            "",
            transformations=tuple(notes),
            refusals=(
                SequenceIssue(
                    "mixed_u_t",
                    f"{label} contains both U and T, so it is neither DNA nor RNA. "
                    "Check the sequence you pasted.",
                ),
            ),
            original_length=original_length,
        )

    offenders = _describe_offenders(compact)
    if offenders:
        prefixed = tuple(
            SequenceIssue(issue.code, f"{label}: {issue.message}") for issue in offenders
        )
        return CleanSequence(
            "", transformations=tuple(notes), refusals=prefixed, original_length=original_length
        )

    if not compact:
        return CleanSequence(
            "",
            transformations=tuple(notes),
            refusals=(
                SequenceIssue("empty", f"{label} has no bases left once markup is removed."),
            ),
            original_length=original_length,
        )

    return CleanSequence(compact, tuple(notes), (), original_length)


def require_sequence(raw: str | None, *, label: str = "Sequence") -> str:
    """Return the cleaned sequence, raising :class:`SequenceRejectedError` if unusable.

    For engine entry points that cannot return a structured result. The
    exception carries the full :class:`CleanSequence`, so a caller that wants
    the transformations can still reach them.
    """
    result = clean_sequence(raw, label=label)
    if not result.ok:
        raise SequenceRejectedError(result)
    return result.sequence


# ── Region validation ──────────────────────────────────────────────────


@dataclass(frozen=True)
class RegionSelection:
    """A validated coordinate range over a template."""

    start: int
    end: int
    refusals: tuple[SequenceIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.refusals

    @property
    def length(self) -> int:
        return max(self.end - self.start, 0)

    def summary(self) -> str:
        if self.refusals:
            return " ".join(issue.message for issue in self.refusals)
        return f"{self.start}-{self.end} ({self.length} bp)"


def validate_region(start: int, end: int, template_length: int) -> RegionSelection:
    """Check a coordinate range, refusing inverted and empty selections.

    Previously an inverted range (600 to 400) or an empty one (500 to 500) fell
    back to the whole template, so a student who mistyped a coordinate silently
    amplified everything. Both are now refused by name.
    """
    issues: list[SequenceIssue] = []

    if template_length <= 0:
        issues.append(SequenceIssue("no_template", "There is no template to select a region from."))
        return RegionSelection(0, 0, tuple(issues))

    if start < 0 or end < 0:
        issues.append(SequenceIssue("negative", "Coordinates cannot be negative."))
    if start > template_length or end > template_length:
        issues.append(
            SequenceIssue(
                "out_of_range",
                f"Coordinates must lie within the template, which is "
                f"{template_length} bp; got {start}-{end}.",
            )
        )
    if start == end:
        issues.append(
            SequenceIssue(
                "empty_region",
                f"Start and end are both {start}, so the selected region is empty. "
                "Widen the range, or choose the whole target.",
            )
        )
    elif start > end:
        issues.append(
            SequenceIssue(
                "inverted",
                f"Start ({start}) is after end ({end}). Swap them, or correct "
                "whichever coordinate is wrong — this is not read as the whole "
                "template.",
            )
        )

    return RegionSelection(start, end, tuple(issues))


__all__ = [
    "AMBIGUITY_CODES",
    "DNA_BASES",
    "CleanSequence",
    "RegionSelection",
    "SequenceIssue",
    "SequenceRejectedError",
    "clean_sequence",
    "require_sequence",
    "validate_region",
]
