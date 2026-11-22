"""What the off-target search actually covered, said in one place.

Why this module exists
----------------------
Audit finding C-2(a). ``find_grna_candidates`` scored off-targets by searching
the user's own pasted target sequence, while the parameter it passed that
sequence to was named ``reference_genome``. The view then reported "No
significant off-target mismatch sites detected" and a score of 100.0.

For a 1 kb insert that statement means only that the guide does not match a
second time within that 1 kb. The E. coli genome is ~4.6 Mb, so a 20-mer has
roughly 4,600 times more opportunity to find a near-match there than in the
pasted fragment. Every other defect in that audit produces a number that is
wrong; this one produced a **safety claim that was unsupported**, and a student
designing a guide for a strain they will actually transform could read it as
clearance to proceed.

The mathematics was never the problem -- the scorer's docstring is already
explicit that it is "CFD-style ... (not the CFD matrix)" and the module
deliberately cites nothing for its ranking heuristic. The *search space* was
the problem, and a search space is not something a view may describe in its own
words: the sentence has to come from the code that performed the search. So the
wording lives here, beside the threshold that decides whether a score counts as
clear, and the views render what they are given.

This module does not know about genomes on purpose. When C-2(b) adds genome
FASTA loading, the scorer's parameter already accepts any reference; what
changes is the ``space_label`` recorded on each candidate, and these sentences
stop needing the "submitted sequence only" qualifier. Nothing here claims the
search was narrow as a permanent fact -- only that it covered the span it is
told it covered.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

from typing import Any

from ..provenance import CONVENTION, Provenance

#: Score at or above which the heuristic found no appreciable near-match
#: *within the span that was searched*. A presentation convention for colouring
#: a cell, not a published safety threshold -- which is exactly why it lives in
#: ``analysis/`` with a label on it rather than as a bare ``>= 90.0`` in a view.
CLEAR_WITHIN_SEARCH_SCORE = 90.0

#: What a guide is called when the span searched was only the submitted
#: sequence. Short enough for a table column.
SUBMITTED_SEQUENCE_LABEL = "submitted sequence"

PROVENANCE: dict[str, Provenance] = {
    "search_space": Provenance(
        kind=CONVENTION,
        explanation=(
            "The off-target search covers only the sequence submitted for "
            "scanning. It is not a genome-wide search, and no genome is "
            "loaded. A guide with no second match in a short insert may still "
            "have many near-matches in the host chromosome, so this result "
            "cannot be read as evidence that a guide is specific in vivo."
        ),
    ),
    "clear_score": Provenance(
        kind=CONVENTION,
        explanation=(
            f"A score of {CLEAR_WITHIN_SEARCH_SCORE:g}% or above is treated as "
            "'no appreciable near-match within the searched span' for display "
            "purposes. The cut-off is this module's own, chosen to colour a "
            "table cell; it is not a published specificity criterion and "
            "carries no claim about in-vivo activity."
        ),
    ),
}


def is_clear_within_search(score: float) -> bool:
    """True when the score found no appreciable near-match in the searched span.

    Deliberately *not* named ``is_safe`` or ``is_specific``. It answers a
    question about one stretch of DNA, and the name has to keep saying so.
    """
    return float(score) >= CLEAR_WITHIN_SEARCH_SCORE


def searched_span(candidate: Any) -> int:
    """How many bases were searched for this candidate, 0 when unrecorded."""
    return int(getattr(candidate, "off_target_search_bp", 0) or 0)


def space_label(candidate: Any) -> str:
    """The span searched, named and measured: ``"submitted sequence, 1,002 bp"``."""
    label = getattr(candidate, "off_target_search_space", "") or SUBMITTED_SEQUENCE_LABEL
    span = searched_span(candidate)
    return f"{label}, {span:,} bp" if span else label


def column_heading() -> str:
    """Table column heading. Names the search space, because a bare
    "Off-target" column invites the genome-wide reading.
    """
    return f"Off-target in {SUBMITTED_SEQUENCE_LABEL} (heuristic)"


def cell_text(candidate: Any) -> str:
    """One table cell: the score and how many hits produced it.

    A bare ``100%`` reads as a clean bill of health. ``100% (0 hits)`` says
    what the number is made of, and the column heading says where it looked.
    """
    hits = len(getattr(candidate, "off_target_hits", ()) or ())
    return f"{float(getattr(candidate, 'off_target_score', 0.0)):g}% ({hits} hit(s))"


def headline(candidate: Any) -> str:
    """The sentence shown when the search found nothing more, or something.

    Replaces "No significant off-target mismatch sites detected.", which was
    absolute in a way the search could not support.
    """
    hits = len(getattr(candidate, "off_target_hits", ()) or ())
    span = searched_span(candidate)
    where = (
        f"within the submitted sequence ({span:,} bp)" if span else "within the submitted sequence"
    )
    if hits:
        return f"{hits} additional near-match(es) found {where}."
    return f"No additional matches {where}."


def caveat() -> str:
    """The limitation that must travel with any off-target number here.

    Shown next to the result rather than buried in a tooltip: it is the
    difference between a ranking aid and a specificity claim.
    """
    return (
        "This is not a genome-wide off-target search. Only the sequence you "
        "submitted was searched, so near-matches elsewhere in the host genome "
        "would not appear here. Do not treat this as evidence that a guide is "
        "specific in your strain -- screen candidates against the actual "
        "reference genome before ordering."
    )


def summary_lines(candidate: Any) -> tuple[str, ...]:
    """Headline, search space and caveat, in the order a reader needs them."""
    return (headline(candidate), f"Searched: {space_label(candidate)}", caveat())


__all__ = [
    "CLEAR_WITHIN_SEARCH_SCORE",
    "PROVENANCE",
    "SUBMITTED_SEQUENCE_LABEL",
    "caveat",
    "cell_text",
    "column_heading",
    "headline",
    "is_clear_within_search",
    "searched_span",
    "space_label",
    "summary_lines",
]
