"""What format a piece of sequence text is actually in.

Why this exists
---------------
The importer decided format from the file name::

    fmt = "fasta" if file_path.endswith((".fa", ".fasta")) else "genbank"

so a FASTA file saved as ``.txt`` or ``.seq`` could not be chosen in the
dialog at all, and anything not ``.fa``/``.fasta`` was handed to the GenBank
parser whatever it contained. A student who renamed a file to get past the
filter was rewarded with a parser traceback.

The format of a sequence is a property of its content, not of its name. A
GenBank record begins with a ``LOCUS`` line, a FASTA record with ``>``; both
are true however the file is named. So the content decides, and the extension
is only consulted when the content is genuinely ambiguous — which, for these
two formats, it is not.

Keeping this in ``analysis/`` is deliberate: "what is this text" is a question
about data, and the standing rule is that no view holds such a judgement. The
file dialog's filter and the drop handler live in ``ui/`` and ask this module.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .sequence_input import AMBIGUITY_CODES, DNA_BASES

#: Biopython's name for each format we can hand to ``SeqIO.read``.
FASTA = "fasta"
GENBANK = "genbank"

#: Not a file format: bare residues, with no header of any kind. It has no
#: Biopython reader, so a caller wraps it before parsing.
RAW = "raw"

#: Nothing we can read. The caller must say so rather than guess.
UNKNOWN = "unknown"

#: Extensions the file dialog offers, mapped to what they *suggest*. A hint
#: only — :func:`sniff_format` never decides on this alone.
EXTENSION_HINTS: dict[str, str] = {
    ".fa": FASTA,
    ".fasta": FASTA,
    ".fna": FASTA,
    ".gb": GENBANK,
    ".gbk": GENBANK,
    ".genbank": GENBANK,
    ".txt": RAW,
    ".seq": RAW,
}

#: The dialog's filter. "All files" is last and deliberate: a file with no
#: extension at all must still be selectable, because the content is what
#: decides and the user may have no way to rename it.
FILE_DIALOG_FILTER = (
    "Sequence files (*.gb *.gbk *.genbank *.fa *.fasta *.fna *.txt *.seq);;"
    "GenBank (*.gb *.gbk *.genbank);;"
    "FASTA (*.fa *.fasta *.fna);;"
    "Plain sequence (*.txt *.seq);;"
    "All files (*)"
)

#: A GenBank record opens with LOCUS in column 1.
_LOCUS = re.compile(r"^\s*LOCUS\s+\S", re.IGNORECASE)

#: A FASTA record opens with '>' (or ';' in the original Pearson format).
_FASTA_START = re.compile(r"^\s*[>;]")

#: Characters that may appear in bare residue text without disqualifying it.
#: Ambiguity codes are included here on purpose: whether to *accept* N is
#: ``clean_sequence``'s decision, not this module's. Sniffing says what the
#: text is; validation says whether it may be used.
_RESIDUE_CHARS = DNA_BASES | set(AMBIGUITY_CODES) | {"U"}

#: How much of an unrecognised first line to quote back in a refusal.
_QUOTED_CHARS = 60

#: Share of residue characters above which bare text is read as sequence.
#: A convention, not a measurement: it is high enough that prose and binary
#: never reach it, and loose enough to tolerate the odd stray character in a
#: copy-paste. Cites nothing.
RESIDUE_THRESHOLD = 0.9


@dataclass(frozen=True)
class FormatVerdict:
    """What the text is, and what it looked like if the answer is "nothing".

    Attributes:
        fmt: :data:`FASTA`, :data:`GENBANK`, :data:`RAW` or :data:`UNKNOWN`.
        reason: How the decision was reached, in a sentence a student can act
            on. Always populated, including on success, so a caller can show
            why a file named one thing was read as another.
        hint: What the file name suggested, or ``""`` when no name was given.
        disagrees_with_name: True when the content contradicts the extension.
            The content still wins; this only lets a view mention it.
    """

    fmt: str
    reason: str
    hint: str = ""
    disagrees_with_name: bool = False

    @property
    def ok(self) -> bool:
        """True when the text is in a format we can load."""
        return self.fmt != UNKNOWN

    @property
    def needs_wrapping(self) -> bool:
        """True when the text has no header and must be wrapped before parsing."""
        return self.fmt == RAW


def extension_hint(filename: str) -> str:
    """What ``filename``'s extension suggests, or ``""`` for no suggestion."""
    name = str(filename or "").lower()
    for ext, fmt in EXTENSION_HINTS.items():
        if name.endswith(ext):
            return fmt
    return ""


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _looks_like_residues(text: str) -> tuple[bool, float]:
    """Is this bare sequence? Returns the verdict and the residue share."""
    compact = "".join(str(text).split()).upper()
    if not compact:
        return False, 0.0
    residues = sum(1 for c in compact if c in _RESIDUE_CHARS)
    share = residues / len(compact)
    return share >= RESIDUE_THRESHOLD, share


def _describe(text: str) -> str:
    """Name what was actually found, for a refusal a student can act on."""
    if not text.strip():
        return "the file is empty"

    if "\x00" in text[:4096]:
        return "it contains binary data, so it is not a text sequence file"

    first = _first_meaningful_line(text)
    if first.startswith("%PDF"):
        return "it is a PDF, not a sequence file"
    if first.startswith("PK\x03\x04"):
        return "it is a zip-based document (.docx, .xlsx or similar), not a sequence file"

    shown = first[:_QUOTED_CHARS] + ("..." if len(first) > _QUOTED_CHARS else "")
    return f"it begins {shown!r}, which is neither a FASTA '>' header nor a GenBank LOCUS line"


def sniff_format(text: str | None, *, filename: str = "") -> FormatVerdict:
    """Decide what ``text`` is from its content, using ``filename`` only as a hint.

    The content always wins. A GenBank record named ``.fasta`` is read as
    GenBank; a FASTA record named ``.txt`` is read as FASTA. ``filename`` is
    recorded so a caller can tell the user the two disagreed, which is usually
    worth knowing — it is how a file ends up misnamed in a lab's shared drive.

    Args:
        text: The file's contents, or what the user pasted.
        filename: The file's name, when there is one. Never required.

    Returns:
        A :class:`FormatVerdict`. Check ``.ok`` before using ``.fmt``.
    """
    raw = "" if text is None else str(text)
    hint = extension_hint(filename)

    def verdict(fmt: str, reason: str) -> FormatVerdict:
        # RAW and a .txt/.seq hint agree; so do the two real formats with
        # their own extensions. Anything else is a genuine contradiction.
        disagrees = bool(hint) and hint != fmt
        return FormatVerdict(fmt, reason, hint, disagrees)

    if not raw.strip():
        return FormatVerdict(UNKNOWN, "There is nothing to read — the input is empty.", hint)

    first = _first_meaningful_line(raw)

    if _LOCUS.match(first):
        return verdict(GENBANK, "Read as GenBank: the record opens with a LOCUS line.")

    if _FASTA_START.match(first):
        return verdict(FASTA, "Read as FASTA: the record opens with a '>' description line.")

    looks_raw, share = _looks_like_residues(raw)
    if looks_raw:
        return verdict(
            RAW,
            f"Read as bare sequence: {share:.0%} of the characters are residues "
            "and there is no FASTA or GenBank header.",
        )

    return FormatVerdict(
        UNKNOWN,
        f"This does not look like a sequence — {_describe(raw)}. "
        "Supported formats are GenBank, FASTA, and plain sequence text.",
        hint,
    )


__all__ = [
    "EXTENSION_HINTS",
    "FASTA",
    "FILE_DIALOG_FILTER",
    "GENBANK",
    "RAW",
    "RESIDUE_THRESHOLD",
    "UNKNOWN",
    "FormatVerdict",
    "extension_hint",
    "sniff_format",
]
