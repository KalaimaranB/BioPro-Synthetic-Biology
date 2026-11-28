"""Karcytics Academy courses for the Synthetic Biology module.

Courses are declarative data: step lists, answer choices and validators, with
no PySide6 anywhere in the package. The panel supplies the one thing a
validator cannot compute for itself — a read-only snapshot of what the user is
looking at (:mod:`.context`) — and ``ui.main_panel`` registers what is here
with ``karcytics_sdk.plugin.runtime_services.tutorial_manager`` under this
plugin's id.

Adding a course: define it in its own module, export it here, and add it to
:data:`ALL_COURSES`. Registration picks it up with no further wiring.
"""

from karcytics_sdk.plugin.tutorial_models import Course

from .context import PrimerDialogSnapshot, SynBioAcademyContext
from .plasmid_assembly import plasmid_assembly_course

#: Every course this module offers, in the order the catalogue should show them.
ALL_COURSES: tuple[Course, ...] = (plasmid_assembly_course,)

__all__ = [
    "ALL_COURSES",
    "PrimerDialogSnapshot",
    "SynBioAcademyContext",
    "plasmid_assembly_course",
]
