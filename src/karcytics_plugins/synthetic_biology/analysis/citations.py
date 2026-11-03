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
    "primer_step",
    "resolve",
    "tellurium_step",
]
