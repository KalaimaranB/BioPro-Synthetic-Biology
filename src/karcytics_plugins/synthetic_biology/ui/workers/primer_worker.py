"""Workers for primer candidate generation and in-silico amplification.

Both are genuinely slow. Candidate generation screens a grid of forward and
reverse lengths at every offset in the rubric's window and then screens the
surviving pairs; at the default offset of 12 that was measured at ~190 ms after
pre-filtering and several seconds before it. Amplification scans both strands
of the template for every window. Neither belongs on the GUI thread.

Follows the existing ``assembly_worker`` / ``crispr_worker`` pattern: subclass
``OneShotWorkerThread``, declare a result signal, forward ``finished_err`` to
``error_occurred``, and do the work in ``_execute``.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin import OneShotWorkerThread
from PySide6.QtCore import Signal

from ...analysis.assembly import amplification as amp
from ...analysis.assembly import gel as gel_engine
from ...analysis.assembly import restriction as rst
from ...analysis.assembly.primer_rubric import PrimerRubric
from ...analysis.assembly.vector_builder import VectorAssemblyEngine


class PrimerCandidateWorker(OneShotWorkerThread):
    """Ranks primer candidates for a target off the GUI thread."""

    candidates_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(  # noqa: PLR0913 - each argument is an independent search setting
        self,
        target_sequence: str,
        target_tm: float = 60.0,
        fwd_overhang: str = "",
        rev_overhang: str = "",
        rubric: PrimerRubric | None = None,
        require_full_target: bool = False,
        limit: int = 25,
        parent: Any = None,
    ) -> None:
        # Production callers always pass a parent (it anchors the thread's
        # lifetime); None is only for tests that call _execute() synchronously.
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.target_sequence = target_sequence
        self.target_tm = target_tm
        self.fwd_overhang = fwd_overhang
        self.rev_overhang = rev_overhang
        self.rubric = rubric
        self.require_full_target = require_full_target
        self.limit = limit

    def _execute(self) -> None:
        candidates = VectorAssemblyEngine.generate_primer_candidates(
            self.target_sequence,
            target_tm=self.target_tm,
            fwd_overhang=self.fwd_overhang,
            rev_overhang=self.rev_overhang,
            rubric=self.rubric,
            require_full_target=self.require_full_target,
            limit=self.limit,
        )
        self.candidates_ready.emit(list(candidates))


class AmplificationWorker(OneShotWorkerThread):
    """Runs in-silico PCR, and builds the digest and gel that follow from it.

    All three engines are driven here rather than in the view, so a view never
    has to orchestrate scientific steps or decide what to feed what.
    """

    # `object` so the dataclasses travel untouched; a typed signal would coerce.
    amplification_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(  # noqa: PLR0913 - each argument is an independent input to the reaction
        self,
        template: str,
        forward_primer: str,
        reverse_primer: str,
        forward_tail: str = "",
        reverse_tail: str = "",
        circular: bool = False,
        enzymes: Any = (),
        ladder: str = "1kb_plus",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.template = template
        self.forward_primer = forward_primer
        self.reverse_primer = reverse_primer
        self.forward_tail = forward_tail
        self.reverse_tail = reverse_tail
        self.circular = circular
        self.enzymes = tuple(enzymes or ())
        self.ladder = ladder

    def _execute(self) -> None:
        result = amp.amplify(
            self.template,
            self.forward_primer,
            self.reverse_primer,
            forward_tail=self.forward_tail,
            reverse_tail=self.reverse_tail,
            circular=self.circular,
            enzymes=self.enzymes,
        )

        digest = None
        lanes = []
        product = result.product
        if product is not None:
            lanes.append(gel_engine.product_lane(product.length, name="PCR product"))
            if self.enzymes:
                digest = rst.digest(product.sequence, self.enzymes, circular=False)
                lanes.append(gel_engine.digest_lane(digest, name=" + ".join(digest.enzymes)))
        else:
            # Several products still belong on a gel: that is what the student
            # would actually see, and it is the lesson.
            for index, amplicon in enumerate(result.amplicons, start=1):
                lanes.append(gel_engine.product_lane(amplicon.length, name=f"Product {index}"))

        built = gel_engine.build_gel(lanes, ladder=self.ladder) if lanes else None

        self.amplification_ready.emit(
            {
                "result": result,
                "digest": digest,
                "gel": built,
                "template_bp": len(self.template or ""),
            }
        )


class InternalSiteWorker(OneShotWorkerThread):
    """Checks whether a tail's enzyme also cuts inside the region to amplify.

    Fast for a short insert but unbounded in template length, and it is the
    check that decides whether a student's whole cloning strategy works, so it
    is kept off the GUI thread with the rest.
    """

    sites_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, sequence: str, enzymes: Any, parent: Any = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.sequence = sequence
        self.enzymes = tuple(enzymes or ())

    def _execute(self) -> None:
        if not self.enzymes or not self.sequence:
            self.sites_ready.emit({"enzymes": self.enzymes, "sites": ()})
            return
        sites = rst.find_sites(self.sequence, self.enzymes, circular=False)
        self.sites_ready.emit({"enzymes": self.enzymes, "sites": sites})


__all__ = ["AmplificationWorker", "InternalSiteWorker", "PrimerCandidateWorker"]
