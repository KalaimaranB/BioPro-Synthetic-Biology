"""Plasmid Assembly: From Sequence to Gel — the module's first Academy course.

Written for a second- or third-year undergraduate who has met PCR in lecture
and has never opened this app. It runs inside the Plasmid Assembly tab and
takes the learner the whole way: load a sequence, design a primer pair, read
the ranked table, add a restriction tail, inspect the predicted product, run a
predicted gel, and finish by reading the Methods paragraph the app wrote from
their own actions.

The teaching contract
---------------------
Three things are taught at once, and the steps below are deliberately ordered
so they interleave rather than stack:

1. **Platform** — where a control is and what pressing it does.
2. **Theory** — the biology or thermodynamics the control stands for.
3. **The division of labour** — what the app computed, and what is still the
   learner's call. This is the one undergraduates reliably get wrong with a
   tool like this, so it recurs as an explicit refrain: *the app gives you X,
   you decide Y*. A student who leaves believing the Score column is a verdict
   on their experiment has learned the software and missed the science.

Why so much of it is about provenance
-------------------------------------
This module already separates values that follow from published work
(:data:`~analysis.provenance.SOURCED`) from values that are its own practice
(:data:`~analysis.provenance.CONVENTION`), with a third category for a rule
whose *shape* is published while its *parameters* are ours
(:data:`~analysis.provenance.MECHANISM`). ``provenance.py`` says that split is
"worthless if it only exists in the source". Teaching it is how it stops being
worthless: the gel lesson and the Methods lesson exist mainly to make a
student notice that a number on screen can be a computation, a convention, or
a prediction, and that telling them apart is their job when they write it up.

Scope
-----
Nothing here teaches a feature that does not exist. In particular the course
never mentions orthogonality checking, which the manifest advertises but which
has no implementation — an Academy course validates what the learner did, so a
lesson on a missing feature would hang rather than merely mislead.

See ``context.py`` for what the validators are allowed to inspect and
``validators.py`` for the checks themselves. No Qt imports: a course is
declarative data.
"""

from __future__ import annotations

from karcytics_sdk.plugin.tutorial_models import QUESTION_PREDICT as _PREDICT
from karcytics_sdk.plugin.tutorial_models import (
    ActionStep,
    AnswerChoice,
    BranchingStep,
    Course,
    InfoStep,
    InteractionStep,
    QuestionStep,
    VerificationStep,
)

from .validators import (
    CandidateSelected,
    CandidatesRanked,
    MethodRecorded,
    PlasmidLoaded,
    PrimerDialogOpen,
    TailAdded,
    ViewingDialogTab,
)

# ── Widget object names ───────────────────────────────────────────────────────
#
# Spotlighting resolves a widget by `objectName`, so every name below must be
# set in `ui/views/plasmid_assembly_view.py`. They are collected here, rather
# than written inline, because `tests/unit/test_plasmid_assembly_course.py`
# asserts the view actually defines each one — a renamed widget then fails a
# test instead of silently producing a lesson that highlights nothing.

PARTS_PALETTE = "parts_palette"
BTN_IMPORT = "btn_import_sequence"
BTN_PASTE = "btn_paste_sequence"
BTN_PRIMER = "btn_design_primers"
IMPORT_NOTICE = "plasmid_import_notice"
SEQUENCE_VIEWER = "plasmid_sequence_viewer"

FEATURE_COMBO = "primer_feature_combo"
COORDS_ROW = "primer_coords_row"
TM_SPIN = "primer_tm_spin"
FWD_TAIL = "primer_fwd_tail_edit"
COVERAGE_TOGGLE = "primer_coverage_toggle"
BTN_RUN_DESIGN = "primer_btn_design"
PRIMER_TABBAR = "primer_result_tabbar"
CANDIDATE_TABLE = "primer_candidate_table"
RUBRIC_PANEL = "primer_rubric_panel"
AMPLIFICATION_TRACK = "primer_amplification_track"
GEL_LADDER = "gel_ladder_combo"
GEL_AGAROSE = "gel_agarose_combo"
GEL_VIEW = "gel_view"
BTN_METHODS = "primer_btn_methods"


def _open_plasmid_tab(panel: object) -> None:
    """Put the workspace on Plasmid Assembly before the course points at it.

    The driver drops any spotlight target whose ``isVisible()`` is False, and a
    widget on a tab that is not current is not visible. Without this the course
    ran correctly and highlighted nothing: the workspace opens on tab 0
    (Design), every target here belongs to tab 2, and a course that dims the
    screen while pointing at invisible widgets looks exactly like a broken
    overlay.

    Duck-typed and silent on failure, because a step whose only job is
    navigation must never be the thing that ends a lesson.
    """
    opener = getattr(panel, "show_plasmid_tab", None)
    if callable(opener):
        opener()


_steps = [
    # ── PHASE 1: Orientation ──────────────────────────────────────────────────
    InfoStep(
        id="welcome",
        text=(
            "Hey, I'm **Cyto** 👋. Over the next 25 minutes we'll take one DNA sequence and "
            "turn it into a primer pair, a predicted PCR product, and a predicted gel.\n\n"
            "Everything you see will be **computed, not measured**. Knowing the difference is "
            "most of what this course is for."
        ),
        cyto_emotion="cheering",
        cyto_animation="cheering",
        next_step_id="go_to_plasmid_tab",
    ),
    ActionStep(
        id="go_to_plasmid_tab",
        text="Taking you to the Plasmid Assembly tab…",
        cyto_emotion="talking",
        action=_open_plasmid_tab,
        next_step_id="the_layout",
    ),
    InfoStep(
        id="the_layout",
        text=(
            "This is the **Plasmid Assembly** tab. Three regions:\n\n"
            "• **Left** — a palette of biological parts you can drag.\n"
            "• **Middle** — your construct, and the toolbar that acts on it.\n"
            "• **Right** — the sequence itself, as text."
        ),
        cyto_emotion="talking",
        target_widget_names=[PARTS_PALETTE, BTN_PRIMER, SEQUENCE_VIEWER],
        next_step_id="what_is_active",
    ),
    InfoStep(
        id="what_is_active",
        text=(
            "One idea to hold onto: this tab always has exactly one **active sequence**, and "
            "every tool downstream — primers, product, gel — runs against *that*.\n\n"
            "If a result looks wrong later, your first question is usually *which sequence is "
            "actually loaded?*"
        ),
        cyto_emotion="idle",
        target_widget_names=[SEQUENCE_VIEWER],
        next_step_id="three_routes",
    ),
    # ── PHASE 2: Getting a sequence in ────────────────────────────────────────
    InfoStep(
        id="three_routes",
        text=(
            "Three ways in, and they all end up in the same place:\n\n"
            "• **📋 Paste Sequence** — raw bases, FASTA, or a whole GenBank record.\n"
            "• **📁 Import File** — the same formats from disk.\n"
            "• **Drag a file** onto the tab.\n\n"
            "Use whichever you like — your own sequence is fine."
        ),
        cyto_emotion="pointing",
        target_widget_names=[BTN_PASTE, BTN_IMPORT],
        next_step_id="load_one",
    ),
    VerificationStep(
        id="load_one",
        text=(
            "👉 Load a sequence now. If you don't have one handy, paste a few hundred bases of "
            "anything — I'll wait."
        ),
        cyto_emotion="pointing",
        target_widget_names=[BTN_PASTE, BTN_IMPORT],
        validator=PlasmidLoaded(),
        allow_interaction=True,
        hide_next_button=True,
        stuck_hint_text="Both buttons are in the toolbar, just above the construct area.",
        stuck_hint_after_ms=30000,
        next_step_id="read_the_notice",
    ),
    InfoStep(
        id="read_the_notice",
        text=(
            "Loaded. 🎉 Now look at the line under the toolbar.\n\n"
            "That notice lists **every change the app made to your text** — uppercasing, "
            "stripped whitespace and digits, `U` swapped for `T`. It is not decoration. If you "
            "pasted RNA and didn't notice, your primers are for a different molecule than you "
            "think."
        ),
        cyto_emotion="talking",
        # The viewer is listed as well because the notice hides itself when a
        # paste needed no cleaning at all — a legitimate outcome that would
        # otherwise leave this step pointing at nothing.
        target_widget_names=[IMPORT_NOTICE, SEQUENCE_VIEWER],
        next_step_id="format_question",
    ),
    QuestionStep(
        id="format_question",
        text="Your record carries a gene called *gfp*. Which format preserves that name?",
        cyto_emotion="talking",
        choices=[
            AnswerChoice(
                text="FASTA",
                feedback=(
                    "FASTA holds bases and one header line — no feature table. The *gfp* "
                    "annotation is simply absent from the file."
                ),
            ),
            AnswerChoice(text="GenBank", correct=True),
            AnswerChoice(
                text="Both, equally",
                feedback=(
                    "Not equally. Both carry the bases; only GenBank carries the annotations "
                    "that say which stretch is a gene."
                ),
            ),
        ],
        explanation=(
            "This matters in a minute: the **Amplify** dropdown can only offer you named "
            "regions that the record brought with it. FASTA in, coordinates only."
        ),
        next_step_id="what_is_a_primer",
    ),
    # ── PHASE 3: Theory before the dialog ─────────────────────────────────────
    InfoStep(
        id="what_is_a_primer",
        text=(
            "Before we open anything — what a primer actually is.\n\n"
            "A short single strand, ~18–25 bases, that base-pairs to one strand of your "
            "template. Polymerase cannot start a chain from nothing; it can only **extend an "
            "existing 3′ end**. The primer supplies that end. That's the whole job."
        ),
        cyto_emotion="talking",
        next_step_id="predict_tm",
    ),
    QuestionStep(
        id="predict_tm",
        text=(
            "Before I tell you — what do you think mainly sets a primer's melting "
            "temperature?\n\nNo wrong answer here; I'll come back to it."
        ),
        cyto_emotion="idle",
        kind=_PREDICT,
        question_id="tm_guess",
        choices=[
            AnswerChoice(text="Its %GC"),
            AnswerChoice(text="Its length"),
            AnswerChoice(text="Which bases sit next to which"),
            AnswerChoice(text="Not sure"),
        ],
        next_step_id="tm_truth",
    ),
    InfoStep(
        id="tm_truth",
        text=(
            "You said: **{answer:tm_guess}**.\n\n"
            "The honest answer is the third one. Stacking energy between *neighbouring* base "
            "pairs is what this app computes — a nearest-neighbour thermodynamic model, "
            "corrected for salt. %GC and length correlate with Tm, which is why the "
            "rule-of-thumb formulas work roughly, but they are shortcuts to the real quantity, "
            "not the quantity itself."
        ),
        cyto_emotion="happy",
        next_step_id="three_prime_question",
    ),
    QuestionStep(
        id="three_prime_question",
        text=(
            "A primer is perfectly matched everywhere except **one mismatched base at its 3′ "
            "end**. What happens?"
        ),
        cyto_emotion="talking",
        choices=[
            AnswerChoice(
                text="It primes normally — one base out of twenty barely matters",
                feedback=(
                    "Position matters more than count here. A mismatch in the middle is often "
                    "tolerated; this one is not."
                ),
            ),
            AnswerChoice(text="It essentially fails to prime", correct=True),
            AnswerChoice(
                text="The polymerase proofreads and fixes it",
                feedback=(
                    "Taq has no detectable 3′→5′ proofreading, so there is nothing to correct "
                    "the mismatch."
                ),
            ),
        ],
        explanation=(
            "The 3′ end is the business end — it's the one the polymerase extends. This is why "
            "the app judges structures anchored at the 3′ end far more harshly than internal "
            "ones, and it's a **published experimental result**, not a convention. Hold that "
            "distinction; it comes back."
        ),
        next_step_id="open_dialog",
    ),
    # ── PHASE 4: Designing ────────────────────────────────────────────────────
    InteractionStep(
        id="open_dialog",
        text="👉 Open **🧬 Design Primers** in the toolbar.",
        cyto_emotion="pointing",
        target_widget_names=[BTN_PRIMER],
        target_widget_name=BTN_PRIMER,
        event_trigger="clicked",
        allow_interaction=True,
        next_step_id="dialog_is_open",
    ),
    VerificationStep(
        id="dialog_is_open",
        text="Give it a moment to come up.",
        cyto_emotion="idle",
        validator=PrimerDialogOpen(),
        hide_next_button=True,
        # Normally satisfied without a click, when the dialog appears. Panel
        # interaction stays on so a learner whose dialog did not open can press
        # the toolbar button again instead of being stuck behind a hidden Next.
        allow_interaction=True,
        target_widget_names=[BTN_PRIMER],
        resume_step_id="open_dialog",
        next_step_id="choose_region",
    ),
    InfoStep(
        id="choose_region",
        text=(
            "**Amplify** is the first decision, and it's yours.\n\n"
            "If your record had features, they're listed here by name. Otherwise you get "
            "*Whole target sequence* and the coordinate boxes below.\n\n"
            "The app will happily design primers for whatever you pick. It has no idea which "
            "region you *meant*."
        ),
        cyto_emotion="talking",
        target_widget_names=[FEATURE_COMBO, COORDS_ROW],
        allow_interaction=True,
        next_step_id="coordinates_note",
    ),
    InfoStep(
        id="coordinates_note",
        text=(
            "A warning worth having: an **inverted or empty** range used to fall through to the "
            "whole template, so a typo silently amplified everything. It now refuses and tells "
            "you.\n\n"
            "Read the red line if the button pushes back."
        ),
        cyto_emotion="idle",
        target_widget_names=[COORDS_ROW],
        allow_interaction=True,
        next_step_id="target_tm",
    ),
    InfoStep(
        id="target_tm",
        text=(
            "**Target Tm** defaults to 60 °C. The app ranks candidates by how close they land "
            "to this number.\n\n"
            "60 is a reasonable default, not a law. You set it from the annealing temperature "
            "your polymerase and protocol actually use — *the app gives you the Tm of each "
            "candidate; you decide what Tm you want.*"
        ),
        cyto_emotion="talking",
        target_widget_names=[TM_SPIN],
        allow_interaction=True,
        next_step_id="coverage_toggle",
    ),
    InfoStep(
        id="coverage_toggle",
        text=(
            "**Coverage** is off by default. Left off, the app may trim your region slightly to "
            "find a better-scoring pair.\n\n"
            "Switch it on when the full region must be in the product — an entire ORF, say. "
            "Trimming three bases off a coding sequence is the kind of thing you find out about "
            "at the sequencing stage."
        ),
        cyto_emotion="idle",
        target_widget_names=[COVERAGE_TOGGLE],
        allow_interaction=True,
        next_step_id="run_design",
    ),
    VerificationStep(
        id="run_design",
        text="👉 Press **Design Primers**.",
        cyto_emotion="pointing",
        target_widget_names=[BTN_RUN_DESIGN],
        validator=CandidatesRanked(),
        allow_interaction=True,
        hide_next_button=True,
        stuck_hint_text="If it refuses, the red caption under the form says why.",
        stuck_hint_after_ms=20000,
        resume_step_id="open_dialog",
        next_step_id="table_tour",
    ),
    # ── PHASE 5: Reading the output ───────────────────────────────────────────
    InfoStep(
        id="table_tour",
        text=(
            "Ranked candidates. Each row is a **pair**:\n\n"
            "• **Forward / Reverse** — the sequences to order.\n"
            "• **Tm**, **GC%** — per primer.\n"
            "• **Product** — base pairs between them.\n"
            "• **Score**, **Verdict** — the app's summary judgement."
        ),
        cyto_emotion="talking",
        target_widget_names=[CANDIDATE_TABLE],
        allow_interaction=True,
        next_step_id="score_warning",
    ),
    InfoStep(
        id="score_warning",
        text=(
            "Now the important part. **Score is not truth.**\n\n"
            "It's how well the pair satisfies a **rubric** — a list of thresholds that lives in "
            "a file, is overridable, and can be swapped for your department's own. Your "
            "instructor can ship a different one and every Score in this table changes, with no "
            "new biology involved."
        ),
        cyto_emotion="talking",
        target_widget_names=[CANDIDATE_TABLE],
        allow_interaction=True,
        next_step_id="provenance_question",
    ),
    QuestionStep(
        id="provenance_question",
        text=(
            "Two numbers in front of you. Which of these is a **convention** — community "
            "practice rather than a measured result?\n\nSelect all that apply."
        ),
        cyto_emotion="talking",
        multi_select=True,
        choices=[
            AnswerChoice(text="The 40–60% GC window a primer must fall in", correct=True),
            AnswerChoice(
                text="The Tm value computed for each primer",
                feedback=(
                    "That one is sourced. It comes out of a published nearest-neighbour model "
                    "with a published salt correction."
                ),
            ),
            AnswerChoice(
                text="Requiring a G or C in the last 5 bases (the 3′ clamp)", correct=True
            ),
            AnswerChoice(
                text="That a 3′ mismatch stops a primer working",
                feedback=(
                    "That's a published experimental finding — the one you answered a question "
                    "about a few steps ago."
                ),
            ),
        ],
        explanation=(
            "Both GC-window and clamp rules are widely taught, widely used, and **not** "
            "empirical findings — no honest citation supports them as such, so this app cites "
            "nothing for them and labels them conventions wherever it shows them.\n\n"
            "The free-energy cutoffs are the interesting middle case: the ΔG is computed from a "
            "published model, but *where you draw the line* on that scale is still a convention."
        ),
        reveal_after_attempts=2,
        next_step_id="rubric_panel",
    ),
    InfoStep(
        id="rubric_panel",
        text=(
            "The panel below the table breaks one pair down check by check — GC, clamp, "
            "poly-base runs, hairpins, self- and hetero-dimers, Tm match.\n\n"
            "Each carries its own provenance label. That's the app telling you which of its own "
            "opinions you're allowed to cite."
        ),
        cyto_emotion="talking",
        target_widget_names=[RUBRIC_PANEL],
        allow_interaction=True,
        allow_scroll=True,
        next_step_id="select_row",
    ),
    VerificationStep(
        id="select_row",
        text="👉 Click a row to select that pair. The Amplification and Gel tabs stay empty until you do.",
        cyto_emotion="pointing",
        target_widget_names=[CANDIDATE_TABLE],
        validator=CandidateSelected(),
        allow_interaction=True,
        hide_next_button=True,
        next_step_id="tail_theory",
    ),
    # ── PHASE 6: Tails ────────────────────────────────────────────────────────
    InfoStep(
        id="tail_theory",
        text=(
            "Those **5′ tail** boxes are how cloning happens.\n\n"
            "A tail is extra bases bolted onto the 5′ end that **do not match the template**. "
            "Cycle one, they just hang off. But they get copied into the product — so every "
            "molecule you make afterwards carries them. Add `GAATTC` and your product now has "
            "an EcoRI site it never had."
        ),
        cyto_emotion="talking",
        target_widget_names=[FWD_TAIL],
        allow_interaction=True,
        next_step_id="add_tail",
    ),
    VerificationStep(
        id="add_tail",
        text=(
            "👉 Type a tail into **Forward 5′ tail** — try `GAATTC`. Watch the caption beside "
            "it name the enzyme."
        ),
        cyto_emotion="pointing",
        target_widget_names=[FWD_TAIL],
        validator=TailAdded(),
        allow_interaction=True,
        hide_next_button=True,
        stuck_hint_text="Any DNA works, but GAATTC is recognised and will be named for you.",
        stuck_hint_after_ms=25000,
        next_step_id="tail_tm_trap",
    ),
    InfoStep(
        id="tail_tm_trap",
        text=(
            "⚠️ A trap that catches people every term.\n\n"
            "**Tm and GC% in that table are for the annealing region only** — the tail is "
            "excluded, because it doesn't anneal on the first cycle. The oligo you order is "
            "longer than the thermodynamics shown.\n\n"
            "The caption under the table says exactly this. It's there because it's a real "
            "misreading, not because someone liked the sentence."
        ),
        cyto_emotion="surprised",
        target_widget_names=[CANDIDATE_TABLE],
        allow_interaction=True,
        next_step_id="go_amplification",
    ),
    # ── PHASE 7: The product ──────────────────────────────────────────────────
    VerificationStep(
        id="go_amplification",
        text="👉 Open the **Amplification** tab.",
        cyto_emotion="pointing",
        target_widget_names=[PRIMER_TABBAR],
        validator=ViewingDialogTab("amplification"),
        allow_interaction=True,
        hide_next_button=True,
        next_step_id="read_product",
    ),
    InfoStep(
        id="read_product",
        text=(
            "Your predicted product, drawn on the template.\n\n"
            "The two ends are the **primer footprints** — where each primer anneals. Between "
            "them is the **interior**, which neither primer covers and the polymerase copies. "
            "Product length is footprint-to-footprint, tails included."
        ),
        cyto_emotion="talking",
        target_widget_names=[AMPLIFICATION_TRACK],
        allow_interaction=True,
        next_step_id="circular_note",
    ),
    InfoStep(
        id="circular_note",
        text=(
            "If your template is **circular**, position 0 is a bookkeeping choice, not a real "
            "end of the molecule. A product can run straight through it, and the track will say "
            "so — *spans the origin*.\n\n"
            "A plasmid has no beginning. Your coordinate system does."
        ),
        cyto_emotion="idle",
        target_widget_names=[AMPLIFICATION_TRACK],
        allow_interaction=True,
        next_step_id="go_gel",
    ),
    # ── PHASE 8: The gel ──────────────────────────────────────────────────────
    VerificationStep(
        id="go_gel",
        text="👉 Open the **Gel** tab.",
        cyto_emotion="pointing",
        target_widget_names=[PRIMER_TABBAR],
        validator=ViewingDialogTab("gel"),
        allow_interaction=True,
        hide_next_button=True,
        next_step_id="predict_band",
    ),
    QuestionStep(
        id="predict_band",
        text=(
            "Before you study it — your product against this ladder. Where do you expect the band?"
        ),
        cyto_emotion="talking",
        kind=_PREDICT,
        question_id="band_guess",
        choices=[
            AnswerChoice(text="Near the top — it barely moved"),
            AnswerChoice(text="Somewhere in the middle"),
            AnswerChoice(text="Near the bottom — it ran a long way"),
        ],
        next_step_id="gel_controls",
    ),
    InfoStep(
        id="gel_controls",
        text=(
            "You guessed **{answer:band_guess}** — check it against the lane.\n\n"
            "Small fragments travel further. **Ladder** gives you known sizes to compare "
            "against; **Agarose %** sets which size range this gel can separate at all. Change "
            "either and the prediction re-runs."
        ),
        cyto_emotion="happy",
        target_widget_names=[GEL_LADDER, GEL_AGAROSE],
        allow_interaction=True,
        next_step_id="resolving_window",
    ),
    InfoStep(
        id="resolving_window",
        text=(
            "Try a different **Agarose %** and watch bands crowd together or spread out.\n\n"
            "Each percentage has a *resolving window* — the size range it separates usefully. "
            "Two fragments both outside it become one smear. Picking the percentage to match "
            "your expected product is a real experimental decision, and it's yours."
        ),
        cyto_emotion="pointing",
        target_widget_names=[GEL_AGAROSE],
        allow_interaction=True,
        next_step_id="gel_honesty",
    ),
    InfoStep(
        id="gel_honesty",
        text=(
            "Now the most important sentence in this course.\n\n"
            "**This gel is a prediction, not data.** Migration here is modelled as a straight "
            "line against log₁₀(size) — a teaching approximation. That DNA mobility depends on "
            "size is an established result. That it is *log-linear* is not: the original work "
            "proposed a different relationship, and a follow-up study compared the forms and "
            "found this one wanting.\n\n"
            "So the app labels this a **convention** and cites the papers for the size "
            "dependence only."
        ),
        cyto_emotion="talking",
        target_widget_names=[GEL_VIEW],
        allow_interaction=True,
        next_step_id="gel_missing",
    ),
    InfoStep(
        id="gel_missing",
        text=(
            "And look at what this model never asked you for: **voltage, buffer, run time**.\n\n"
            "All three change where a band lands on a real gel. A model that doesn't take them "
            "cannot be predicting your gel in particular. It's for *is my product roughly the "
            "size I expected, and would I be able to see it* — and that's genuinely useful. "
            "It's just not a result."
        ),
        cyto_emotion="idle",
        next_step_id="gel_question",
    ),
    QuestionStep(
        id="gel_question",
        text=(
            "Your actual gel comes back and the band sits noticeably higher than this "
            "prediction. What's the *first* thing you should suspect?"
        ),
        cyto_emotion="talking",
        choices=[
            AnswerChoice(
                text="The app computed the product size wrong",
                feedback=(
                    "Unlikely — product size is just arithmetic on coordinates. It's the "
                    "mobility model, not the length, that's approximate."
                ),
            ),
            AnswerChoice(
                text="Nothing — predictions and gels disagree, that's normal",
                feedback=(
                    "Too comfortable. A clear mismatch is information, and shrugging at it is "
                    "how a mispriming event becomes a published figure."
                ),
            ),
            AnswerChoice(
                text="Either the run conditions differ from the model's assumptions, or you "
                "amplified something other than what you designed for",
                correct=True,
            ),
        ],
        explanation=(
            "Both are worth checking, and they call for different fixes. The model ignores run "
            "conditions, so a shift is expected. But a *large* shift, or an extra band, points "
            "at mispriming — and the Amplification tab is where you'd go to see whether your "
            "primers had another plausible site."
        ),
        next_step_id="methods_intro",
    ),
    # ── PHASE 9: The Methods capstone ─────────────────────────────────────────
    InfoStep(
        id="methods_intro",
        text=(
            "Last thing, and it's the one that saves you time later.\n\n"
            "Everything you just did was logged. The app can write it up as a **Methods "
            "paragraph with references** — in the past tense, the way you'd submit it."
        ),
        cyto_emotion="happy",
        target_widget_names=[BTN_METHODS],
        allow_interaction=True,
        next_step_id="open_methods",
    ),
    VerificationStep(
        id="open_methods",
        text="👉 Open **Methods & References**.",
        cyto_emotion="pointing",
        target_widget_names=[BTN_METHODS],
        validator=MethodRecorded(
            "primer_design",
            action=(
                "I can't find a recorded primer design. Go back to **Candidates** and press "
                "**Design Primers** once more."
            ),
        ),
        allow_interaction=True,
        hide_next_button=False,
        next_step_id="methods_read",
    ),
    InfoStep(
        id="methods_read",
        text=(
            "Read it properly — it describes **your** run, with your numbers.\n\n"
            "Then find the citations. Each one is attached to a specific claim, and some claims "
            "deliberately have none. A missing citation there is not an oversight; it's the app "
            "declining to dress a convention up as a finding."
        ),
        cyto_emotion="talking",
        allow_interaction=True,
        next_step_id="citation_question",
    ),
    QuestionStep(
        id="citation_question",
        text=(
            "You're writing this up. Which sentence is honest about where the numbers came from?"
        ),
        cyto_emotion="talking",
        choices=[
            AnswerChoice(
                text="Primers were validated against established design criteria (Allawi et al., 1997).",
                feedback=(
                    "This attaches the GC and clamp *criteria* to a paper about nearest-neighbour "
                    "thermodynamics. That paper supports the Tm calculation — not the thresholds "
                    "you judged against."
                ),
            ),
            AnswerChoice(
                text="Melting temperatures were computed with a nearest-neighbour model "
                "(Allawi et al., 1997) and screened against conventional GC and 3′-clamp "
                "criteria.",
                correct=True,
            ),
            AnswerChoice(
                text="Product sizes were confirmed by agarose gel electrophoresis.",
                feedback=(
                    "You didn't run a gel — you predicted one. 'Confirmed' claims an experiment "
                    "that doesn't exist yet, which is the most serious of the three errors here."
                ),
            ),
        ],
        explanation=(
            "The pattern to carry out of here: **cite the model, label the convention, and "
            "never call a prediction a measurement.** The app has been doing all three for you "
            "on screen the entire time — now you know what it was telling you."
        ),
        next_step_id="graduation",
    ),
    # ── PHASE 10: Graduation ──────────────────────────────────────────────────
    InfoStep(
        id="graduation",
        text=(
            "🏆 Done. You loaded a sequence, designed and screened a primer pair, added a "
            "restriction tail, read a predicted product and a predicted gel, and wrote up the "
            "lot with honest references.\n\n"
            "The split worth remembering: **the app computes, you decide.** Region, target Tm, "
            "coverage, which candidate, which agarose, whether the verdict suits your "
            "experiment — every one of those was yours."
        ),
        cyto_emotion="cheering",
        cyto_animation="cheering",
        next_step_id="finish",
    ),
    BranchingStep(
        id="finish",
        text=(
            "You've earned the **🧬 Plasmid Cartographer** badge.\n\nNow go design primers for "
            "something you actually care about."
        ),
        cyto_emotion="happy",
        options={
            "Let's build something 🔬": "__complete__",
        },
    ),
]


# ── Course object ─────────────────────────────────────────────────────────────

plasmid_assembly_course = Course(
    id="synbio_plasmid_assembly_v1",
    title="Plasmid Assembly: From Sequence to Gel",
    description=(
        "Load a sequence, design and screen a PCR primer pair, add a restriction tail, and "
        "read the predicted product and gel — learning what the app computes for you, what it "
        "only conventionally assumes, and what is still your call."
    ),
    estimated_minutes=25,
    badge_reward="Plasmid Cartographer",
    badge_icon="🧬",
    prerequisite_course_ids=[],
    steps=_steps,
)


#: Every ``objectName`` the steps above spotlight, derived from them rather
#: than listed by hand — a hand-kept copy drifted from the steps within an hour
#: of being written. ``test_plasmid_assembly_course.py`` asserts the view
#: actually defines each one, so a renamed widget fails a test instead of
#: quietly producing a lesson that highlights nothing.
TARGETED_WIDGETS: tuple[str, ...] = tuple(
    dict.fromkeys(name for step in _steps for name in (step.target_widget_names or []))
)
