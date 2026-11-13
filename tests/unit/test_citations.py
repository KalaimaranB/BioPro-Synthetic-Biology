"""The module's citations: registered, complete, and true to the code they credit.

The registry is the real SDK ``karcytics_sdk.plugin.citations`` (see conftest),
so these tests exercise genuine formatting and BibTeX output.
"""

from __future__ import annotations

import inspect
import re

import pytest

from karcytics_plugins.synthetic_biology.analysis import citations as cites
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState


class _Comp:
    def __init__(self, n: float = 2.5) -> None:
        self.n = n


class _Edge:
    def __init__(
        self,
        interaction_type: str = "repression",
        source_id: str = "",
        target_id: str = "",
    ) -> None:
        self.interaction_type = interaction_type
        self.source_id = source_id
        self.target_id = target_id


def _ring(n: float = 2.5, size: int = 3):
    """A cyclic repressor ring: the topology Elowitz & Leibler establish."""
    ids = [chr(ord("A") + i) for i in range(size)]
    comps = []
    for node in ids:
        comp = _Comp(n)
        comp.id = node
        comps.append(comp)
    edges = [_Edge("repression", ids[i], ids[(i + 1) % size]) for i in range(size)]
    return comps, edges


def _toggle():
    """Two genes repressing each other - a toggle switch, not a ring."""
    comps = []
    for node in ("A", "B"):
        comp = _Comp(2.0)
        comp.id = node
        comps.append(comp)
    return comps, [_Edge("repression", "A", "B"), _Edge("repression", "B", "A")]


# ── Registry integrity ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_every_citation_is_complete():
    keys = [c.key for c in cites.CITATIONS]
    assert len(keys) == len(set(keys)), "duplicate citation keys"
    for c in cites.CITATIONS:
        assert c.authors and all(a.strip() for a in c.authors), c.key
        assert c.title and not c.title.endswith("."), c.key
        assert 1900 < c.year < 2100, c.key
        assert c.venue, c.key
        assert re.fullmatch(r"10\.\d{4,9}/\S+", c.doi), f"{c.key}: {c.doi!r}"
        # Crossref sometimes drops the space around italics; generated titles
        # must not carry that artefact ("ofEscherichia").
        assert not re.search(r"[a-z][A-Z][a-z]+ [a-z]+[A-Z]", c.title), c.title


@pytest.mark.unit
def test_feature_and_solver_citations_resolve():
    from karcytics_sdk.plugin.citations import get

    for feature, keys in {**cites.FEATURE_CITATIONS, **cites.SOLVER_CITATIONS}.items():
        assert keys or feature in cites.SOLVER_CITATIONS, feature
        for key in keys:
            assert get(key).key == key


@pytest.mark.unit
def test_unverifiable_and_unused_works_are_not_registered():
    """Hill (1910) has no Crossref record; SantaLucia (1998) is not the Tm
    table the code uses. Neither should be cited.
    """
    keys = set(cites.all_keys())
    assert not any(k.startswith("hill19") for k in keys)
    assert "santalucia1998" not in keys


# ── Drift guards: each citation must match the code it credits ─────────────


@pytest.mark.unit
def test_primer_tm_citations_match_the_tm_code():
    """calculate_tm uses Biopython's DNA_NN3 (Allawi & SantaLucia 1997) and
    saltcorr=7 (Owczarzy et al. 2008). If either changes, so must the citation.
    """
    from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
        VectorAssemblyEngine,
    )

    src = inspect.getsource(VectorAssemblyEngine.calculate_tm)
    assert "DNA_NN3" in src
    assert "saltcorr=7" in src
    assert cites.FEATURE_CITATIONS["primer_design"][:2] == ("allawi1997", "owczarzy2008")

    from Bio.SeqUtils import MeltingTemp

    table_comment = inspect.getsource(MeltingTemp).split("DNA_NN3 =")[0].splitlines()[-1]
    assert "Allawi" in table_comment and "1997" in table_comment


@pytest.mark.unit
def test_simulate_tab_cites_the_integrator_tellurium_actually_uses():
    te = pytest.importorskip("tellurium")
    runner = te.loada("model m(); S1 = 1; J1: S1 => ; 0.1*S1; end")
    assert runner.integrator.getName() == "cvode"
    assert "hindmarsh2005" in cites.FEATURE_CITATIONS["simulate_ode"]
    runner.setIntegrator("gillespie")
    assert runner.integrator.getName() == "gillespie"
    assert "gillespie1977" in cites.FEATURE_CITATIONS["simulate_ssa"]


# ── Step builders ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_circuit_step_cites_the_solver_that_ran():
    # A real cyclic repressor ring, because elowitz2000 is now attached to that
    # topology rather than to any repressing edge.
    rk45 = cites.circuit_ode_step(*_ring(n=2.5), "RK45", 400, 1600)
    assert rk45["citations"] == ["elowitz2000", "virtanen2020", "dormand1980"]
    assert rk45["parameters"]["Hill coefficient n"] == "2.5"

    lsoda = cites.circuit_ode_step([_Comp()], [_Edge()], "LSODA", 100, 500)
    assert "petzold1983" in lsoda["citations"]

    # Radau has no registered source: credit SciPy only, never a guess.
    radau = cites.circuit_ode_step([_Comp()], [], "Radau", 100, 500)
    assert radau["citations"] == ["virtanen2020"]


@pytest.mark.unit
def test_crispr_step_cites_jinek_only_for_spcas9():
    assert cites.crispr_step("SpCas9 (NGG)", 20, 1083, 40)["citations"] == ["jinek2012"]
    assert cites.crispr_step("AsCas12a (TTTV)", 23, 1083, 12)["citations"] == []


@pytest.mark.unit
def test_primer_step_reports_the_conditions_calculate_tm_uses():
    from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
        VectorAssemblyEngine,
    )

    defaults = inspect.signature(VectorAssemblyEngine.calculate_tm).parameters
    step = cites.primer_step(60.0, 60.41, 59.55)
    assert step["parameters"]["[Na+]"] == f"{defaults['na_conc_mm'].default:g} mM"
    assert step["parameters"]["[Mg2+]"] == f"{defaults['mg_conc_mm'].default:g} mM"
    assert step["parameters"]["reverse Tm"] == "59.55 °C"


@pytest.mark.unit
def test_step_builder_rejects_an_unregistered_key():
    with pytest.raises(KeyError):
        cites._entry("x", "y", ("not_a_registered_key",))


# ── Methods paragraph ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_methods_text_orders_steps_like_a_write_up_and_numbers_consistently():
    log = [
        cites.circuit_ode_step([_Comp()] * 3, [_Edge()] * 3, "RK45", 400, 1600),  # run last...
        cites.primer_step(60.0, 60.41, 59.55),  # ...but written first
    ]
    text = cites.methods_text(log, version="1.2.3")

    assert text.startswith("Genetic circuit design and simulation were performed")
    assert "Images were analysed" not in text  # the SDK default's imaging wording
    assert text.index("PCR primers") < text.index("Protein dynamics")

    # Reference numbers follow cited_keys(), so a CitationsPanel lines up.
    refs = text.split("References\n", 1)[1].splitlines()
    from karcytics_sdk.plugin.citations import get

    for i, key in enumerate(cites.cited_keys(log), start=1):
        assert refs[i - 1].startswith(f"{i}. {get(key).formatted()[:30]}")


@pytest.mark.unit
def test_methods_text_without_references_and_when_empty():
    log = [cites.primer_step(60.0, 60.41, 59.55)]
    assert "References" not in cites.methods_text(log, include_references=False)
    assert "No analyses have been run" in cites.methods_text([])


@pytest.mark.unit
def test_bibtex_covers_every_cited_reference():
    log = [cites.primer_step(60.0, 60.41, 59.55), cites.crispr_step("SpCas9 (NGG)", 20, 900, 5)]
    bib = cites.bibtex(log)
    for key in cites.cited_keys(log):
        assert f"{{{key}," in bib
    assert cites.bibtex([]) == ""


# ── Methods log in the state ───────────────────────────────────────────────


@pytest.mark.unit
def test_record_method_keeps_the_latest_run_of_each_kind():
    state = SynBioState()
    state.record_method(cites.circuit_ode_step([_Comp(2.1)], [_Edge()], "RK45", 100, 500))
    state.record_method(cites.primer_step(60.0, 60.0, 60.0))
    state.record_method(cites.circuit_ode_step([_Comp(2.5)], [_Edge()], "RK45", 400, 1600))

    kinds = [e["kind"] for e in state.methods_log]
    assert kinds.count("circuit_ode") == 1
    ode = next(e for e in state.methods_log if e["kind"] == "circuit_ode")
    assert ode["parameters"]["Hill coefficient n"] == "2.5"


@pytest.mark.unit
def test_methods_log_is_saved_with_the_workspace():
    state = SynBioState()
    state.record_method(cites.primer_step(60.0, 60.41, 59.55))

    restored = SynBioState()
    restored.load_from_dict(state.to_dict())
    assert restored.methods_log == state.methods_log


# ── Primer screening ───────────────────────────────────────────────────


@pytest.mark.unit
def test_primer_screen_cites_the_free_energy_model_only():
    """The ΔG model is published; the thresholds on top of it are convention.

    Citing a paper for "40-60% GC" would misrepresent a rule of thumb as a
    finding, which is the same error the CRISPR scores made before.
    """
    keys = cites.FEATURE_CITATIONS["primer_screen"]
    assert "santalucia2004" in keys
    assert "cock2009" in keys


@pytest.mark.unit
def test_santalucia2004_matches_its_crossref_record():
    from karcytics_sdk.plugin.citations import get

    work = get("santalucia2004")
    assert work.authors == ("SantaLucia, J.", "Hicks, D.")
    assert work.year == 2004
    assert work.venue == "Annual Review of Biophysics and Biomolecular Structure"
    assert work.volume == "33(1)"
    assert work.pages == "415–440"
    assert work.doi == "10.1146/annurev.biophys.32.110601.141800"


@pytest.mark.unit
def test_the_nn_parameters_in_use_come_from_the_cited_work():
    """The citation must describe the table the code actually loads.

    Biopython labels DNA_NN4 as SantaLucia & Hicks (2004); the thermodynamics
    module reads that table, and primer_screen cites that paper. This pins the
    three together so they cannot drift apart silently.
    """
    import inspect

    from Bio.SeqUtils import MeltingTemp

    from karcytics_plugins.synthetic_biology.analysis.assembly import thermodynamics

    comment = inspect.getsource(MeltingTemp).split("DNA_NN4 =")[0].splitlines()[-1]
    assert "SantaLucia" in comment and "2004" in comment
    assert thermodynamics.NN_PARAMS["AA/TT"] == (
        MeltingTemp.DNA_NN4["AA/TT"][0],
        MeltingTemp.DNA_NN4["AA/TT"][1],
    )


@pytest.mark.unit
def test_primer_screen_step_reports_the_rubric_it_applied():
    from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import PrimerRubric

    rubric = PrimerRubric(name="BIOL341 Lab 3", gc_min_percent=45.0)
    entry = cites.primer_screen_step(rubric, n_candidates=12, verdict="pass")

    assert entry["kind"] == "primer_screen"
    assert entry["citations"] == list(cites.FEATURE_CITATIONS["primer_screen"])
    assert entry["parameters"]["rubric"] == "BIOL341 Lab 3"
    assert entry["parameters"]["GC window"].startswith("45")
    assert entry["parameters"]["candidates ranked"] == 12
    # The write-up must say the thresholds are conventions, not findings.
    assert "conventional primer-design practice" in entry["description"]
    assert "stem stacking only" in entry["description"]


@pytest.mark.unit
def test_primer_screen_is_written_up_after_the_design_it_judges():
    order = list(cites.STEP_ORDER)
    assert order.index("primer_screen") > order.index("primer_design")


@pytest.mark.unit
def test_a_screening_run_flows_into_methods_text_and_bibtex():
    from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import PrimerRubric
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState

    state = SynBioState()
    state.record_method(cites.primer_step(60.0, 60.1, 59.6))
    state.record_method(cites.primer_screen_step(PrimerRubric(), 8, "pass"))

    text = cites.methods_text(state.methods_log)
    assert "screened against a configurable rubric" in text
    assert "SantaLucia" in text
    assert "santalucia2004," in cites.bibtex(state.methods_log)


# ── Phase 2: digest, amplification and gel ────────────────────────────


@pytest.mark.unit
def test_phase2_citations_are_registered():
    for key in ("roberts2022", "southern1979", "elder1983"):
        entry = cites.get(key)
        assert entry.doi, key
        assert entry.authors, key


@pytest.mark.unit
def test_rebase_is_cited_for_enzyme_geometry():
    """Recognition sites and cut offsets are REBASE's, via Biopython."""
    keys = cites.FEATURE_CITATIONS["restriction_digest"]
    assert "roberts2022" in keys
    assert "cock2009" in keys


@pytest.mark.unit
def test_the_gel_cites_the_size_dependence_not_the_equation():
    """Southern (1979) established the relationship; the log-linear form is ours."""
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel

    assert cites.FEATURE_CITATIONS["gel_migration"] == ("southern1979", "elder1983")
    kind, _ = gel.THRESHOLD_PROVENANCE["mobility_model"]
    assert kind == "convention", "the equation must not claim to be a published result"


@pytest.mark.unit
def test_amplification_does_not_cite_its_mismatch_rule():
    """The priming rule is a convention and must carry no citation."""
    from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp

    keys = cites.FEATURE_CITATIONS["amplification"]
    # Phase 3 added the PCR method and the 3'-end mechanism. What must stay
    # true is that no citation is offered for the chosen *numbers*: both
    # parameters remain conventions, and only the rule's shape has a paper.
    for field_name in ("three_prime_exact", "max_mismatches"):
        assert amp.THRESHOLD_PROVENANCE[field_name].kind == "convention"
    assert amp.THRESHOLD_PROVENANCE["max_mismatches"].mechanism == ()
    assert "allawi1997" in keys and "cock2009" in keys
    mechanism = amp.THRESHOLD_PROVENANCE["three_prime_exact"].mechanism
    assert set(mechanism) <= set(keys), "a mechanism must be cited in the feature map"


@pytest.mark.unit
def test_phase2_steps_are_in_step_order():
    for kind in ("amplification", "restriction_digest", "gel_migration"):
        assert kind in cites.STEP_ORDER


@pytest.mark.unit
def test_phase2_steps_appear_in_workflow_order():
    """Methods read in the order the bench work happens."""
    order = list(cites.STEP_ORDER)
    assert order.index("primer_screen") < order.index("amplification")
    assert order.index("amplification") < order.index("restriction_digest")
    assert order.index("restriction_digest") < order.index("gel_migration")


def _phase2_log():
    from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel
    from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst

    from .sequence_fixtures import (
        ECORI_TAIL,
        HINDIII_TAIL,
        SYNTHETIC_ORF,
        SYNTHETIC_TEMPLATE,
        primers_for,
    )

    fwd, rev = primers_for(SYNTHETIC_ORF)
    result = amp.amplify(
        SYNTHETIC_TEMPLATE,
        ECORI_TAIL + fwd,
        HINDIII_TAIL + rev,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
        enzymes=["EcoRI", "HindIII"],
    )
    digest = rst.double_digest(result.product.sequence, "EcoRI", "HindIII")
    built = gel.build_gel([gel.product_lane(result.product.length), gel.digest_lane(digest)])
    return (
        [
            cites.amplification_step(result),
            cites.digest_step(digest),
            cites.gel_step(built),
        ],
        result,
        digest,
        built,
    )


@pytest.mark.unit
def test_each_phase2_step_records_the_parameters_it_ran_with():
    log, result, digest, built = _phase2_log()
    by_kind = {entry["kind"]: entry for entry in log}

    amp_params = by_kind["amplification"]["parameters"]
    assert amp_params["outcome"] == result.outcome
    assert amp_params["3' bases required to match"] == result.diagnostics["three_prime_exact"]

    dig_params = by_kind["restriction_digest"]["parameters"]
    assert dig_params["sites found"] == len(digest.sites)
    assert dig_params["enzymes"] == "EcoRI, HindIII"

    gel_params = by_kind["gel_migration"]["parameters"]
    assert gel_params["lanes"] == len(built.lanes)


@pytest.mark.unit
def test_phase2_steps_flow_into_methods_text_and_bibtex():
    log, _, _, _ = _phase2_log()
    text = cites.methods_text(log)

    assert "REBASE" in text
    assert "log-linear" in text
    # The disclaimers must survive into the paragraph a student submits.
    assert "convention" in text
    assert "does not account for" in text

    keys = cites.cited_keys(log)
    for key in ("roberts2022", "southern1979", "elder1983", "cock2009"):
        assert key in keys
    bib = cites.bibtex(log)
    for key in ("roberts2022", "southern1979", "elder1983"):
        assert f"{{{key}," in bib


@pytest.mark.unit
def test_the_digest_step_names_what_it_cannot_model():
    log, _, _, _ = _phase2_log()
    digest_entry = next(e for e in log if e["kind"] == "restriction_digest")
    for limitation in ("methylation sensitivity", "star activity", "isoschizomers"):
        assert limitation in digest_entry["description"]
