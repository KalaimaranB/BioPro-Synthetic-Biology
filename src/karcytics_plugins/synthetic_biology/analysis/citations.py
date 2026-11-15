"""Published work behind the module's models, registered with the SDK citation registry.

Every entry in ``CITATIONS`` was generated from the Crossref record for its DOI
(``https://api.crossref.org/works/<doi>``) on 2026-11-03 and is reproduced as
Crossref returned it — authors, title, venue, volume, issue, pages — not typed
from memory. The SDK's rule is that a wrong author list or DOI is worse than
none, so an entry that could not be verified is left out rather than guessed.
Two consequences worth knowing:

* Hill (1910), the origin of the Hill equation, is **not** registered. It
  appeared as a *J. Physiol.* proceedings abstract that has no DOI, and Crossref
  has no record of it. The Hill-repression kinetics the simulators use are
  credited through Elowitz & Leibler (2000), whose model is built on them.
* The primer Tm model is cited as **Allawi & SantaLucia (1997)**, not
  SantaLucia (1998). ``VectorAssemblyEngine.calculate_tm`` uses Biopython's
  ``DNA_NN3`` table, and Biopython's own source identifies that table as
  Allawi & SantaLucia (1997), *Biochemistry* 36: 10581–10594.

Features name their citation keys through ``FEATURE_CITATIONS``. Each analysis
that runs records a methods entry in ``SynBioState`` (via the step builders
below), and ``methods_text`` turns that record into a Materials & Methods
paragraph with numbered references — what a student needs for a lab write-up.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from karcytics_sdk.plugin.citations import Citation, MethodStep, get, register, resolve, to_bibtex

CITATIONS: tuple[Citation, ...] = (
    Citation(
        key="allawi1997",
        authors=(
            "Allawi, H. T.",
            "SantaLucia, J.",
        ),
        title="Thermodynamics and NMR of Internal G·T Mismatches in DNA",
        year=1997,
        venue="Biochemistry",
        volume="36(34)",
        pages="10581–10594",
        doi="10.1021/bi962590c",
    ),
    Citation(
        key="newton1989",
        authors=(
            "Newton, C. R.",
            "Graham, A.",
            "Heptinstall, L. E.",
            "Powell, S. J.",
            "Summers, C.",
            "Kalsheker, N.",
            "Smith, J. C.",
            "Markham, A. F.",
        ),
        title="Analysis of any point mutation in DNA. The amplification refractory mutation system (ARMS)",
        year=1989,
        venue="Nucleic Acids Research",
        volume="17(7)",
        pages="2503\u20132516",
        doi="10.1093/nar/17.7.2503",
    ),
    Citation(
        key="saiki1988",
        authors=(
            "Saiki, Randall K.",
            "Gelfand, David H.",
            "Stoffel, Susanne",
            "Scharf, Stephen J.",
            "Higuchi, Russell",
            "Horn, Glenn T.",
            "Mullis, Kary B.",
            "Erlich, Henry A.",
        ),
        title="Primer-Directed Enzymatic Amplification of DNA with a Thermostable DNA Polymerase",
        year=1988,
        venue="Science",
        volume="239(4839)",
        pages="487\u2013491",
        doi="10.1126/science.2448875",
    ),
    Citation(
        key="tindall1988",
        authors=(
            "Tindall, Kenneth R.",
            "Kunkel, Thomas A.",
        ),
        title="Fidelity of DNA synthesis by the Thermus aquaticus DNA polymerase",
        year=1988,
        venue="Biochemistry",
        volume="27(16)",
        pages="6008\u20136013",
        doi="10.1021/bi00416a027",
    ),
    Citation(
        key="roberts2022",
        authors=(
            "Roberts, Richard J",
            "Vincze, Tamas",
            "Posfai, Janos",
            "Macelis, Dana",
        ),
        title="REBASE: a database for DNA restriction and modification: enzymes, genes and genomes",
        year=2022,
        venue="Nucleic Acids Research",
        volume="51(D1)",
        pages="D629\u2013D630",
        doi="10.1093/nar/gkac975",
    ),
    Citation(
        key="southern1979",
        authors=("Southern, E.M.",),
        title="Measurement of DNA length by gel electrophoresis",
        year=1979,
        venue="Analytical Biochemistry",
        volume="100(2)",
        pages="319\u2013323",
        doi="10.1016/0003-2697(79)90235-5",
    ),
    Citation(
        key="elder1983",
        authors=(
            "Elder, J.K.",
            "Southern, E.M.",
        ),
        title=(
            "Measurement of DNA length by gel electrophoresis II: Comparison of methods "
            "for relating mobility to fragment length"
        ),
        year=1983,
        venue="Analytical Biochemistry",
        volume="128(1)",
        pages="227\u2013231",
        doi="10.1016/0003-2697(83)90369-x",
    ),
    Citation(
        key="choi2018",
        authors=(
            "Choi, K.",
            "Medley, J. K.",
            "König, M.",
            "Stocking, K.",
            "Smith, L.",
            "Gu, S.",
            "Sauro, H. M.",
        ),
        title="Tellurium: An extensible python-based modeling environment for systems and synthetic biology",
        year=2018,
        venue="Biosystems",
        volume="171",
        pages="74–79",
        doi="10.1016/j.biosystems.2018.07.006",
    ),
    Citation(
        key="cock2009",
        authors=(
            "Cock, P. J. A.",
            "Antao, T.",
            "Chang, J. T.",
            "Chapman, B. A.",
            "Cox, C. J.",
            "Dalke, A.",
            "Friedberg, I.",
            "Hamelryck, T.",
            "Kauff, F.",
            "Wilczynski, B.",
            "de Hoon, M. J. L.",
        ),
        title="Biopython: freely available Python tools for computational molecular biology and bioinformatics",
        year=2009,
        venue="Bioinformatics",
        volume="25(11)",
        pages="1422–1423",
        doi="10.1093/bioinformatics/btp163",
    ),
    Citation(
        key="dormand1980",
        authors=(
            "Dormand, J. R.",
            "Prince, P. J.",
        ),
        title="A family of embedded Runge-Kutta formulae",
        year=1980,
        venue="Journal of Computational and Applied Mathematics",
        volume="6(1)",
        pages="19–26",
        doi="10.1016/0771-050x(80)90013-3",
    ),
    Citation(
        key="elowitz2000",
        authors=(
            "Elowitz, M. B.",
            "Leibler, S.",
        ),
        title="A synthetic oscillatory network of transcriptional regulators",
        year=2000,
        venue="Nature",
        volume="403(6767)",
        pages="335–338",
        doi="10.1038/35002125",
    ),
    Citation(
        key="engler2008",
        authors=(
            "Engler, C.",
            "Kandzia, R.",
            "Marillonnet, S.",
        ),
        title="A One Pot, One Step, Precision Cloning Method with High Throughput Capability",
        year=2008,
        venue="PLoS ONE",
        volume="3(11)",
        pages="e3647",
        doi="10.1371/journal.pone.0003647",
    ),
    Citation(
        key="gibson2009",
        authors=(
            "Gibson, D. G.",
            "Young, L.",
            "Chuang, R.-Y.",
            "Venter, J. C.",
            "Hutchison, C. A.",
            "Smith, H. O.",
        ),
        title="Enzymatic assembly of DNA molecules up to several hundred kilobases",
        year=2009,
        venue="Nature Methods",
        volume="6(5)",
        pages="343–345",
        doi="10.1038/nmeth.1318",
    ),
    Citation(
        key="gillespie1977",
        authors=("Gillespie, D. T.",),
        title="Exact stochastic simulation of coupled chemical reactions",
        year=1977,
        venue="The Journal of Physical Chemistry",
        volume="81(25)",
        pages="2340–2361",
        doi="10.1021/j100540a008",
    ),
    Citation(
        key="hawley1983",
        authors=(
            "Hawley, D. K.",
            "McClure, W. R.",
        ),
        title="Compilation and analysis of Escherichia coli promoter DNA sequences",
        year=1983,
        venue="Nucleic Acids Research",
        volume="11(8)",
        pages="2237–2255",
        doi="10.1093/nar/11.8.2237",
    ),
    Citation(
        key="henikoff1992",
        authors=(
            "Henikoff, S.",
            "Henikoff, J. G.",
        ),
        title="Amino acid substitution matrices from protein blocks",
        year=1992,
        venue="Proceedings of the National Academy of Sciences",
        volume="89(22)",
        pages="10915–10919",
        doi="10.1073/pnas.89.22.10915",
    ),
    Citation(
        key="hindmarsh2005",
        authors=(
            "Hindmarsh, A. C.",
            "Brown, P. N.",
            "Grant, K. E.",
            "Lee, S. L.",
            "Serban, R.",
            "Shumaker, D. E.",
            "Woodward, C. S.",
        ),
        title="SUNDIALS: Suite of nonlinear and differential/algebraic equation solvers",
        year=2005,
        venue="ACM Transactions on Mathematical Software",
        volume="31(3)",
        pages="363–396",
        doi="10.1145/1089014.1089020",
    ),
    Citation(
        key="jinek2012",
        authors=(
            "Jinek, M.",
            "Chylinski, K.",
            "Fonfara, I.",
            "Hauer, M.",
            "Doudna, J. A.",
            "Charpentier, E.",
        ),
        title="A Programmable Dual-RNA–Guided DNA Endonuclease in Adaptive Bacterial Immunity",
        year=2012,
        venue="Science",
        volume="337(6096)",
        pages="816–821",
        doi="10.1126/science.1225829",
    ),
    Citation(
        key="owczarzy2008",
        authors=(
            "Owczarzy, R.",
            "Moreira, B. G.",
            "You, Y.",
            "Behlke, M. A.",
            "Walder, J. A.",
        ),
        title="Predicting Stability of DNA Duplexes in Solutions Containing Magnesium and Monovalent Cations",
        year=2008,
        venue="Biochemistry",
        volume="47(19)",
        pages="5336–5353",
        doi="10.1021/bi702363u",
    ),
    Citation(
        key="petzold1983",
        authors=("Petzold, L.",),
        title="Automatic Selection of Methods for Solving Stiff and Nonstiff Systems of Ordinary Differential Equations",
        year=1983,
        venue="SIAM Journal on Scientific and Statistical Computing",
        volume="4(1)",
        pages="136–148",
        doi="10.1137/0904010",
    ),
    Citation(
        key="santalucia2004",
        authors=(
            "SantaLucia, J.",
            "Hicks, D.",
        ),
        title="The Thermodynamics of DNA Structural Motifs",
        year=2004,
        venue="Annual Review of Biophysics and Biomolecular Structure",
        volume="33(1)",
        pages="415\u2013440",
        doi="10.1146/annurev.biophys.32.110601.141800",
    ),
    Citation(
        key="sharp1987",
        authors=(
            "Sharp, P. M.",
            "Li, W.-H.",
        ),
        title="The codon adaptation index-a measure of directional synonymous codon usage bias, and its potential applications",
        year=1987,
        venue="Nucleic Acids Research",
        volume="15(3)",
        pages="1281–1295",
        doi="10.1093/nar/15.3.1281",
    ),
    Citation(
        key="smith2009",
        authors=(
            "Smith, L. P.",
            "Bergmann, F. T.",
            "Chandran, D.",
            "Sauro, H. M.",
        ),
        title="Antimony: a modular model definition language",
        year=2009,
        venue="Bioinformatics",
        volume="25(18)",
        pages="2452–2454",
        doi="10.1093/bioinformatics/btp401",
    ),
    Citation(
        key="virtanen2020",
        authors=(
            "Virtanen, P.",
            "Gommers, R.",
            "Oliphant, T. E.",
            "Haberland, M.",
            "Reddy, T.",
            "Cournapeau, D.",
            "Burovski, E.",
            "Peterson, P.",
            "Weckesser, W.",
            "Bright, J.",
            "van der Walt, S. J.",
            "Brett, M.",
            "Wilson, J.",
            "Millman, K. J.",
            "Mayorov, N.",
            "Nelson, A. R. J.",
            "Jones, E.",
            "Kern, R.",
            "Larson, E.",
            "Carey, C. J.",
            "Polat, İ.",
            "Feng, Y.",
            "Moore, E. W.",
            "VanderPlas, J.",
            "Laxalde, D.",
            "Perktold, J.",
            "Cimrman, R.",
            "Henriksen, I.",
            "Quintero, E. A.",
            "Harris, C. R.",
            "Archibald, A. M.",
            "Ribeiro, A. H.",
            "Pedregosa, F.",
            "van Mulbregt, P.",
            "SciPy 1.0 Contributors",
            "Vijaykumar, A.",
            "Bardelli, A. P.",
            "Rothberg, A.",
            "Hilboll, A.",
            "Kloeckner, A.",
            "Scopatz, A.",
            "Lee, A.",
            "Rokem, A.",
            "Woods, C. N.",
            "Fulton, C.",
            "Masson, C.",
            "Häggström, C.",
            "Fitzgerald, C.",
            "Nicholson, D. A.",
            "Hagen, D. R.",
            "Pasechnik, D. V.",
            "Olivetti, E.",
            "Martin, E.",
            "Wieser, E.",
            "Silva, F.",
            "Lenders, F.",
            "Wilhelm, F.",
            "Young, G.",
            "Price, G. A.",
            "Ingold, G.-L.",
            "Allen, G. E.",
            "Lee, G. R.",
            "Audren, H.",
            "Probst, I.",
            "Dietrich, J. P.",
            "Silterra, J.",
            "Webber, J. T.",
            "Slavič, J.",
            "Nothman, J.",
            "Buchner, J.",
            "Kulick, J.",
            "Schönberger, J. L.",
            "de Miranda Cardoso, J. V.",
            "Reimer, J.",
            "Harrington, J.",
            "Rodríguez, J. L. C.",
            "Nunez-Iglesias, J.",
            "Kuczynski, J.",
            "Tritz, K.",
            "Thoma, M.",
            "Newville, M.",
            "Kümmerer, M.",
            "Bolingbroke, M.",
            "Tartre, M.",
            "Pak, M.",
            "Smith, N. J.",
            "Nowaczyk, N.",
            "Shebanov, N.",
            "Pavlyk, O.",
            "Brodtkorb, P. A.",
            "Lee, P.",
            "McGibbon, R. T.",
            "Feldbauer, R.",
            "Lewis, S.",
            "Tygier, S.",
            "Sievert, S.",
            "Vigna, S.",
            "Peterson, S.",
            "More, S.",
            "Pudlik, T.",
            "Oshima, T.",
            "Pingel, T. J.",
            "Robitaille, T. P.",
            "Spura, T.",
            "Jones, T. R.",
            "Cera, T.",
            "Leslie, T.",
            "Zito, T.",
            "Krauss, T.",
            "Upadhyay, U.",
            "Halchenko, Y. O.",
            "Vázquez-Baeza, Y.",
        ),
        title="SciPy 1.0: fundamental algorithms for scientific computing in Python",
        year=2020,
        venue="Nature Methods",
        volume="17(3)",
        pages="261–272",
        doi="10.1038/s41592-019-0686-2",
    ),
)

register(*CITATIONS)


# ── Which work each feature is built on ───────────────────────────────────

FEATURE_CITATIONS: dict[str, tuple[str, ...]] = {
    # Hill-repression ODE model, integrated with SciPy's solve_ivp.
    "circuit_simulation": ("elowitz2000", "virtanen2020"),
    "repressilator": ("elowitz2000",),
    # Simulate tab: an Antimony model run in Tellurium. libRoadRunner's default
    # integrator is CVODE from SUNDIALS — not LSODA, as the tab once claimed.
    "simulate_ode": ("choi2018", "smith2009", "hindmarsh2005"),
    "simulate_ssa": ("gillespie1977", "choi2018", "smith2009"),
    # Biopython Tm_NN with the DNA_NN3 table and saltcorr=7.
    "primer_design": ("allawi1997", "owczarzy2008", "cock2009"),
    # Secondary-structure screening. The nearest-neighbour parameters are the
    # SantaLucia & Hicks (2004) unified set, read from Biopython's DNA_NN4
    # table. The rubric *thresholds* applied on top of those energies are
    # conventions and cite nothing — see primer_rubric.THRESHOLD_PROVENANCE.
    "primer_screen": ("santalucia2004", "cock2009"),
    # Enzyme recognition sites, cut offsets and overhang polarity come from
    # REBASE as distributed with Biopython. Nothing in the digest engine is a
    # threshold, so there is no convention to disclaim.
    "restriction_digest": ("roberts2022", "cock2009"),
    # What is modelled is PCR with a thermostable polymerase, which is Saiki
    # et al. (1988) -- not Mullis & Faloona (1987), whose method used Klenow at
    # 37 C and is not what this engine simulates.
    #
    # The priming rule's *numbers* (5-base exact 3' window, 2 mismatches
    # upstream) remain conventions and cite nothing. Its *shape* does not:
    # Newton et al. (1989) demonstrated that an oligonucleotide with a
    # mismatched 3' residue will not function as a primer, and Tindall &
    # Kunkel (1988) showed, on a substrate carrying a 3'-OH terminal mismatch,
    # that Taq lacks detectable proofreading -- which is why such a mismatch is
    # not corrected. Each is attached to its own claim in
    # amplification.THRESHOLD_PROVENANCE; neither supports the chosen window.
    "amplification": ("saiki1988", "newton1989", "tindall1988", "allawi1997", "cock2009"),
    # Size-dependent mobility, calibrated against a ladder, is Southern (1979);
    # Elder & Southern (1983) compared the functional forms and found the
    # log-linear one wanting. The log-linear model this module uses is
    # therefore labelled a convention in gel.THRESHOLD_PROVENANCE: the
    # citations support the size dependence, not this particular equation.
    "gel_migration": ("southern1979", "elder1983"),
    # The scanner searches for the SpCas9 NGG PAM. Candidate *ranking* is the
    # module's own heuristic and deliberately cites nothing.
    "crispr_scan": ("jinek2012",),
    "golden_gate": ("engler2008",),
    "gibson_assembly": ("gibson2009",),
    "promoter_strength": ("hawley1983",),
    "codon_adaptation": ("sharp1987",),
    "protein_stability": ("henikoff1992",),
}

# solve_ivp methods with a defining paper. Radau and BDF are credited to SciPy
# alone rather than to a guessed source.
SOLVER_CITATIONS: dict[str, tuple[str, ...]] = {
    "RK45": ("dormand1980",),
    "LSODA": ("petzold1983",),
}


# ── Step builders: one per kind of analysis ───────────────────────────────
#
# Each returns a plain dict so it can live in SynBioState and be saved with the
# workflow. Wording is in the past tense, as a Methods section is written.

STEP_ORDER: tuple[str, ...] = (
    "design",
    "assembly",
    "primer_design",
    "primer_screen",
    "amplification",
    "restriction_digest",
    "gel_migration",
    "crispr_scan",
    "circuit_ode",
    "tellurium_ode",
    "tellurium_ssa",
)


def _entry(
    kind: str,
    description: str,
    citations: Iterable[str] = (),
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    keys = tuple(citations)
    for key in keys:
        get(key)  # fail at the call site, not when the paragraph is rendered
    return {
        "kind": kind,
        "description": description,
        "citations": list(keys),
        "parameters": dict(parameters or {}),
    }


def design_step(parts: Sequence[Any], n_genes: int) -> dict[str, Any]:
    """The construct and the network compiled from it."""
    n_units = sum(1 for p in parts if getattr(p, "part_type", "") == "promoter")
    return _entry(
        "design",
        f"A {len(parts)}-part construct of {n_units} transcription unit"
        f"{'s' if n_units != 1 else ''} was designed and compiled into a regulatory "
        f"network of {n_genes} gene{'s' if n_genes != 1 else ''}, each promoter "
        "governing the coding sequences downstream of it until the next promoter "
        "or terminator",
    )


def assembly_step(name: str, length_bp: int, n_features: int, circular: bool) -> dict[str, Any]:
    return _entry(
        "assembly",
        f"The construct was assembled in silico into {name}, a {length_bp:,} bp "
        f"{'circular' if circular else 'linear'} vector with {n_features} annotated features",
    )


def primer_step(target_tm: float, forward_tm: float, reverse_tm: float) -> dict[str, Any]:
    """Primer design. Salt and oligo concentrations are read off ``calculate_tm``
    itself, so this cannot report conditions the calculation did not use.
    """
    from .assembly.vector_builder import VectorAssemblyEngine

    defaults = inspect.signature(VectorAssemblyEngine.calculate_tm).parameters
    return _entry(
        "primer_design",
        "PCR primers were designed by selecting, at each end of the target, the "
        "binding length whose nearest-neighbour melting temperature was closest to "
        "the target, with magnesium-aware salt correction",
        FEATURE_CITATIONS["primer_design"],
        {
            "target Tm": f"{target_tm:g} °C",
            "forward Tm": f"{forward_tm:.2f} °C",
            "reverse Tm": f"{reverse_tm:.2f} °C",
            "[Na+]": f"{defaults['na_conc_mm'].default:g} mM",
            "[Mg2+]": f"{defaults['mg_conc_mm'].default:g} mM",
            "[primer]": f"{defaults['primer_conc_nm'].default:g} nM",
        },
    )


def primer_screen_step(
    rubric: Any,
    n_candidates: int,
    verdict: str,
    checks_applied: Sequence[str] = (),
) -> dict[str, Any]:
    """Primer screening. Reads its parameters off the rubric that was applied,
    so the write-up cannot claim thresholds the run did not use.

    Only the free-energy model is cited. The thresholds are conventions, and
    the description says so rather than letting a citation imply otherwise.
    """
    return _entry(
        "primer_screen",
        "Candidate primers were screened against a configurable rubric covering GC "
        "content, 3' clamp, single-base runs, pair melting-temperature match, product "
        "size and template uniqueness, with hairpin, self-dimer and heterodimer free "
        "energies computed from nearest-neighbour parameters; the rubric thresholds "
        "themselves are conventional primer-design practice rather than published "
        "values, and hairpins are scored on stem stacking only",
        FEATURE_CITATIONS["primer_screen"],
        {
            "rubric": getattr(rubric, "name", "unnamed"),
            "GC window": f"{rubric.gc_min_percent:g}\u2013{rubric.gc_max_percent:g}%",
            "3' clamp": (
                f"{rubric.clamp_min_gc}\u2013{rubric.clamp_max_gc} G/C "
                f"in last {rubric.clamp_window}"
            ),
            "max single-base run": rubric.max_poly_run,
            "pair Tm tolerance": f"{rubric.pair_tm_tolerance:g} \u00b0C",
            "product size": f"{rubric.product_min_bp}\u2013{rubric.product_max_bp} bp",
            "hairpin \u0394G cutoff": f"{rubric.hairpin_min_dg:g} kcal/mol",
            "dimer \u0394G cutoff": f"{rubric.self_dimer_min_dg:g} kcal/mol",
            "candidates ranked": n_candidates,
            "best verdict": verdict,
            **({"checks": ", ".join(checks_applied)} if checks_applied else {}),
        },
    )


def amplification_step(
    result: Any,
    *,
    template_bp: int | None = None,
    circular: bool | None = None,
) -> dict[str, Any]:
    """In-silico PCR. Parameters are read off the result's own diagnostics, so
    the write-up cannot report a rule the run did not apply.

    Only the Tm model and Biopython are cited. The mismatch-tolerance rule is
    this module's convention and the description says so rather than letting a
    citation imply it was measured.
    """
    diag = dict(getattr(result, "diagnostics", {}) or {})
    outcome = getattr(result, "outcome", "unknown")
    amplicons = tuple(getattr(result, "amplicons", ()) or ())

    parameters: dict[str, Any] = {
        "template": f"{diag.get('template_bp', template_bp)} bp "
        f"{'circular' if diag.get('circular', circular) else 'linear'}",
        "outcome": outcome,
        "products": len(amplicons),
        "3' bases required to match": diag.get("three_prime_exact"),
        "mismatches allowed elsewhere": diag.get("max_mismatches"),
        "max product searched": f"{diag.get('max_product_bp')} bp",
    }
    if amplicons:
        parameters["product sizes"] = ", ".join(f"{a.length} bp" for a in amplicons)
        parameters["product GC"] = ", ".join(f"{a.gc_percent:.1f}%" for a in amplicons)
    if getattr(result, "dimer_risk", False):
        parameters["heterodimer \u0394G"] = f"{result.dimer_delta_g:.2f} kcal/mol"

    return _entry(
        "amplification",
        "Amplification by the polymerase chain reaction with a thermostable "
        "polymerase was simulated in silico. Primer binding sites were located "
        "on both strands of the template, requiring an exact match over the "
        "3'-terminal bases -- an oligonucleotide mismatched at its 3' residue "
        "does not prime, and Taq lacks the proofreading activity that would "
        "excise such a mismatch -- and tolerating a bounded number of "
        "mismatches further upstream; amplicons were resolved from correctly "
        "oriented pairs within the maximum product length. Annealing "
        "temperatures were computed on the binding region alone, excluding any "
        "5' tail, while product lengths include it. The size of the 3' window "
        "and the number of mismatches tolerated are conventions of this module "
        "rather than published values, although the dependence on the 3' "
        "terminus itself is a published result",
        FEATURE_CITATIONS["amplification"],
        parameters,
    )


def digest_step(result: Any) -> dict[str, Any]:
    """A restriction digest. Enzyme geometry is REBASE's, via Biopython.

    There are no thresholds here, so nothing needs disclaiming as convention;
    what does need stating is what the model leaves out, which it does.
    """
    from .assembly.restriction import DIGEST_LIMITATIONS

    sites = tuple(getattr(result, "sites", ()) or ())
    fragments = tuple(getattr(result, "fragments", ()) or ())
    enzymes = tuple(getattr(result, "enzymes", ()) or ())

    return _entry(
        "restriction_digest",
        "Restriction sites were located using recognition sequences and "
        "strand-specific cut offsets from REBASE, and fragments were predicted "
        "with the overhang left at each end read from the template, so that "
        "enzymes cutting outside their recognition sequence yield "
        "sequence-dependent overhangs; the digest is modelled as complete and "
        "does not account for " + ", ".join(name for name, _ in DIGEST_LIMITATIONS),
        FEATURE_CITATIONS["restriction_digest"],
        {
            "enzymes": ", ".join(enzymes) or "none",
            "topology": "circular" if getattr(result, "circular", False) else "linear",
            "template": f"{getattr(result, 'template_length', 0)} bp",
            "sites found": len(sites),
            "fragments": len(fragments),
            **(
                {"fragment sizes": ", ".join(f"{f.length} bp" for f in fragments)}
                if fragments
                else {}
            ),
        },
    )


def gel_step(gel: Any) -> dict[str, Any]:
    """A predicted gel. The size dependence is cited; the equation is not.

    Southern (1979) established that mobility tracks fragment length against a
    ladder, and also that the relationship is *not* strictly linear in
    log(size). The log-linear form used here is a teaching approximation, and
    the description says so in place of implying the citation endorses it.
    """
    lanes = tuple(getattr(gel, "lanes", ()) or ())
    clamped = sum(1 for lane in lanes for b in getattr(lane, "bands", ()) if b.out_of_range)

    return _entry(
        "gel_migration",
        "Fragment positions were predicted from length by a log-linear "
        "mobility model calibrated to the gel's resolving window, with band "
        "intensity taken as proportional to the mass of DNA in the band and "
        "fragments of equal length merged into a single band; the log-linear "
        "form is a conventional approximation rather than a published "
        "relationship, and agarose percentage, voltage, run conditions and DNA "
        "conformation are not modelled",
        FEATURE_CITATIONS["gel_migration"],
        {
            "model": getattr(gel, "model", "log-linear"),
            "resolving window": f"{getattr(gel, 'min_bp', 0)}\u2013{getattr(gel, 'max_bp', 0)} bp",
            "lanes": len(lanes),
            "lane length": f"{getattr(gel, 'lane_length_mm', 0):g} mm",
            **({"bands outside the window": clamped} if clamped else {}),
        },
    )


def crispr_step(
    pam_type: str, spacer_length: int, target_length: int, n_candidates: int
) -> dict[str, Any]:
    is_spcas9 = "spcas9" in pam_type.lower()
    return _entry(
        "crispr_scan",
        f"Candidate protospacers were identified by scanning both strands of a "
        f"{target_length:,} bp target for {pam_type} protospacer-adjacent motifs and "
        "ranked with a rule-based heuristic (GC content, poly-T runs, PAM-proximal "
        "base) rather than a published on-target efficiency model",
        FEATURE_CITATIONS["crispr_scan"] if is_spcas9 else (),
        {"spacer length": f"{spacer_length} nt", "candidates": n_candidates},
    )


def circuit_ode_step(
    components: Sequence[Any],
    edges: Sequence[Any],
    solver: str,
    t_end: float,
    num_points: int,
) -> dict[str, Any]:
    """The SciPy simulation on the Circuit Simulation tab (and the demo)."""
    hill = sorted({float(c.n) for c in components if getattr(c, "n", None) is not None})
    has_repression = any(str(e.interaction_type).lower() == "repression" for e in edges)

    keys: list[str] = []
    if has_repression:
        keys.append("elowitz2000")
    keys.append("virtanen2020")
    keys.extend(SOLVER_CITATIONS.get(solver, ()))

    parameters: dict[str, Any] = {
        "solver": solver,
        "duration": f"{t_end:g} min",
        "time points": num_points,
    }
    if len(hill) == 1:
        parameters["Hill coefficient n"] = f"{hill[0]:g}"
    elif hill:
        parameters["Hill coefficient n"] = f"{hill[0]:g}–{hill[-1]:g}"

    return _entry(
        "circuit_ode",
        f"Protein dynamics of the {len(components)}-gene circuit were simulated as "
        "ordinary differential equations in which each gene's production is a Hill "
        "function of its repressors and activators and its protein decays at a "
        "first-order rate, integrated with SciPy's solve_ivp",
        keys,
        parameters,
    )


def tellurium_step(method: str, duration_min: float) -> dict[str, Any]:
    """The Simulate tab's Tellurium run, deterministic or stochastic."""
    if method == "gillespie":
        return _entry(
            "tellurium_ssa",
            "Stochastic trajectories of the same circuit were generated in Tellurium "
            "from an Antimony model, using Gillespie's stochastic simulation algorithm "
            "with molecule counts in place of concentrations",
            FEATURE_CITATIONS["simulate_ssa"],
            {"duration": f"{duration_min:g} min"},
        )
    return _entry(
        "tellurium_ode",
        "The deterministic simulation was reproduced in Tellurium from an Antimony "
        "model of the same circuit, integrated with CVODE",
        FEATURE_CITATIONS["simulate_ode"],
        {"duration": f"{duration_min:g} min"},
    )


# ── Methods paragraph and references ──────────────────────────────────────


def _module_version() -> str:
    try:
        from importlib.metadata import version

        return version("synthetic-biology-module")
    except Exception:
        return ""


def method_steps(log: Iterable[Mapping[str, Any]]) -> list[MethodStep]:
    """The methods log as SDK ``MethodStep``s, in the order a write-up reads."""
    rank = {kind: i for i, kind in enumerate(STEP_ORDER)}
    entries = sorted(log, key=lambda e: rank.get(str(e.get("kind")), len(rank)))
    return [
        MethodStep(
            description=str(e.get("description", "")),
            citations=tuple(e.get("citations", ())),
            parameters=dict(e.get("parameters", {})),
        )
        for e in entries
    ]


def cited_keys(log: Iterable[Mapping[str, Any]]) -> list[str]:
    """Every citation key the log uses, de-duplicated, first-mention order."""
    seen: dict[str, None] = {}
    for step in method_steps(log):
        for key in step.citations:
            seen.setdefault(key, None)
    return list(seen)


def methods_text(
    log: Iterable[Mapping[str, Any]],
    version: str | None = None,
    *,
    include_references: bool = True,
) -> str:
    """A Materials & Methods paragraph for the analyses recorded in ``log``.

    Numbering follows the SDK's ``citations.methods_text``: a reference takes
    the next number the first time it is cited. That function is not called
    directly because its opening sentence is fixed to "Images were analysed
    with ...", which describes an imaging plugin, not this one.

    The reference numbers match the order of ``cited_keys(log)``, so a list
    rendered from those keys (e.g. the SDK's ``CitationsPanel``) lines up with
    the bracketed numbers when ``include_references=False``.
    """
    steps = method_steps(log)
    order: list[str] = []

    def numbers(keys: Iterable[str]) -> str:
        nums = []
        for k in keys:
            get(k)
            if k not in order:
                order.append(k)
            nums.append(order.index(k) + 1)
        return f" [{', '.join(str(n) for n in nums)}]" if nums else ""

    def params(parameters: Mapping[str, Any]) -> str:
        if not parameters:
            return ""
        return " (" + ", ".join(f"{k} = {v}" for k, v in parameters.items()) + ")"

    ver = version if version is not None else _module_version()
    sentences = [
        "Genetic circuit design and simulation were performed with the Karcytics "
        f"Synthetic Biology module{' ' + ver if ver else ''}."
    ]
    if not steps:
        sentences.append("No analyses have been run in this workspace yet.")
    for step in steps:
        sentences.append(f"{step.description}{params(step.parameters)}{numbers(step.citations)}.")

    text = " ".join(sentences)
    if order and include_references:
        refs = "\n".join(f"{i}. {get(k).formatted()}" for i, k in enumerate(order, start=1))
        text += f"\n\nReferences\n{refs}"
    return text


def bibtex(log: Iterable[Mapping[str, Any]]) -> str:
    """BibTeX for every reference the methods paragraph cites."""
    keys = cited_keys(log)
    return to_bibtex(keys) if keys else ""


def all_keys() -> list[str]:
    return [c.key for c in CITATIONS]


__all__ = [
    "CITATIONS",
    "FEATURE_CITATIONS",
    "amplification_step",
    "digest_step",
    "gel_step",
    "SOLVER_CITATIONS",
    "STEP_ORDER",
    "all_keys",
    "assembly_step",
    "bibtex",
    "circuit_ode_step",
    "cited_keys",
    "crispr_step",
    "design_step",
    "method_steps",
    "methods_text",
    "primer_screen_step",
    "primer_step",
    "resolve",
    "tellurium_step",
]
