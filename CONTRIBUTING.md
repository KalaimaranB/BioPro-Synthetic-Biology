# Contributing to the Synthetic Biology module

This repo follows the Karcytics-wide contribution workflow. The authoritative
copy lives in the [Karcytics](../Karcytics/CONTRIBUTING.md) repo; this file is a
local copy so the rules are where you are working.

> **Repo-specific note.** CI enforces this policy through the
> `enforce-workflow` job in `.github/workflows/ci.yml`, and locally through the
> `conventional-commit-msg` hook in `.pre-commit-config.yaml`.

---

## 1. Branch Naming & Policy

Your branch name explicitly dictates what you are allowed to merge into. The `enforce-workflow` CI job automatically physically blocks any PR that does not follow this matrix.

| Prefix | Source Branch | Target Branch | Purpose |
| --- | --- | --- | --- |
| `feature/<slug>` | `develop` | `develop` | New functionality |
| `fix/<slug>` | `develop` | `develop` | Non-urgent bug fix |
| `chore/<slug>` | `develop` | `develop` | Tooling, CI, dependencies, cleanup |
| `docs/<slug>` | `develop` | `develop` | Documentation only |
| `hotfix/<slug>` | `main` | `main` | Urgent production fixes |

---

## 2. Standard Development (`develop`)

All standard work (`feature/*`, `fix/*`, `chore/*`, `docs/*`) MUST target `develop`.

1. **Branch off `develop`**

   ```bash
   git checkout develop && git pull
   git checkout -b feature/my-awesome-feature
   ```

2. **Commit** — [Conventional Commits](https://www.conventionalcommits.org/) are
   enforced. Commit messages and PR titles must start with `feat:`, `fix:`,
   `chore:`, `docs:`, etc.

   ```bash
   git commit -m "feat: added new UI dashboard"
   ```

3. **Push and PR**

   ```bash
   git push -u origin feature/my-awesome-feature
   gh pr create --base develop --head feature/my-awesome-feature --title "feat: added new UI dashboard"
   ```

4. **Merge (Squash Only)** — once CI passes, use **Squash and Merge**.

---

## 3. Promotions to Production (`develop` -> `main`)

1. Bump `version` in `pyproject.toml` if this release should produce a new
   executable. Commit it to `develop`.
2. Open the promotion PR:

   ```bash
   gh pr create --base main --head develop --title "chore: promote v1.6.0"
   ```

3. **Merge with "Create a merge commit" — NOT squash.**

   > [!WARNING]
   > Squashing a promotion makes Git forget that `main` and `develop` share
   > history, and the next promotion produces massive textual conflicts.

---

## 4. Versioning & Release Mechanics

`pyproject.toml`'s `version` field is the single source of truth (SemVer).

- A merge to `main` without a version bump still lands the code and runs full CI
  — it just produces no build or release.
- On every push to `main`, `release.yml` checks whether a GitHub Release for
  `v<version>` already exists. If not, the build/test/release pipeline runs.
- A failed promotion can be retried at the same version. You do NOT need to bump
  just to unstick the pipeline.
- Once a version has actually shipped, do not reuse its tag — re-running the
  release overwrites build assets in place and breaks the SLSA provenance
  attestation for that tag. Bump PATCH instead.

---

## 5. Hotfixes (The Fast-Track)

Urgent fixes bypass `develop` and go straight to `main`.

1. Branch off `main`, and bump the PATCH version in `pyproject.toml` so a build
   actually ships.
2. Push and open a PR against `main`.
3. **Squash and Merge.**

### The Automated Back-Merge

`back-merge.yml` fires after *any* push to `main`, opens
`chore/back-merge-main-<SHA>` against `develop`, and auto-merges it with a
standard merge. This keeps `develop` in sync after a hotfix or a promotion.

---

## 6. Visualizing the Graph

- `git tree` — topological graph of the current branch.
- `git tree-all` — every branch, ideal for seeing `develop` and `main` interact.

A **squash merge** reads as a single dot on a straight line. A **standard
merge** loops out and reconnects, proving the two branches share history.

---

## 7. GitHub UI & Code Reviews

### CodeRabbit AI

Scoped to PRs targeting `main` only (`auto_review.base_branches` in
`.coderabbit.yaml`). Day-to-day `feature/*` PRs into `develop` are not reviewed —
that is expected, not a failure.

This repo's `.coderabbit.yaml` additionally enforces the two module invariants:

- `analysis/` stays Qt-free, and every empirical value carries a citation (or is
  explicitly labelled a convention and cites nothing).
- `ui/` makes no scientific decisions and builds only from `karcytics_sdk.plugin.*`.

### Auto-Merge

Robot PRs auto-merge once CI passes. To intervene:

```bash
gh pr merge <PR_NUMBER> --disable-auto
```

---

## 8. Documentation Contributions

- Google-style docstrings for public modules, classes and functions.
- Keep them concise: one-line summary, optional description, Args, Returns,
  Raises, Examples.
- Prefer type hints in signatures; `mkdocstrings` renders types automatically.

```py
def compute(signal: np.ndarray, threshold: float) -> dict:
    """Compute metrics on `signal` above `threshold`.

    Args:
       signal: Input array of samples.
       threshold: Value to threshold the signal.

    Returns:
       A mapping of metric name to value.
    """
    ...
```

### Local preview

```bash
python -m pip install -r reqs.txt
python -m pip install -e .[dev]
mkdocs build
mkdocs serve
```

### PR checklist for docs changes

- Title starts with `docs:` and targets `develop`.
- `mkdocs build` runs clean, no warnings.
- Docstrings added or updated for public API changes.
- `markdownlint` passes (CI runs it).
- User-facing features get an example in `docs/user/`.

If a change touches both code and docs, open a single PR covering both.
