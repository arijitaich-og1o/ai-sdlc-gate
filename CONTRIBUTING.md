# Contributing

## Improving a skill (anyone in the organisation)

1. Branch from `main` in this repository (forks are not accepted by the arbiter).
2. Edit exactly one or more of `skills/<NN-phase>/SKILL.md`. Keep the front matter; bump `version`.
   Do not add files, directories or change anything outside `skills/`.
3. Open a pull request. The **Skill Challenge** workflow evaluates your version against the current one on the
   demo codebase and posts the comparison. If yours is better (or parts of it are), it is written to your branch,
   you are added to `CREDITS.md`, and the PR auto-merges. If not, the PR is closed with the scores so you can
   iterate.

Tips: read `demo_codebase/<phase>/GROUND_TRUTH.yaml` to see which defects the current skill misses. Precision
matters as much as recall; a skill that floods reviewers loses.

## Improving the engine, policy, demo codebase or workflows (code owners)

1. Branch, change, add tests under `gate/tests`.
2. `pip install -e "./gate[dev]" && pytest gate/tests` and run the hygiene scripts:
   `python scripts/check_pinned_actions.py .github/workflows templates` and
   `python scripts/check_ground_truth.py demo_codebase`.
3. Open a PR. `Validate Repository` and `Self Gate` must pass and a code owner must approve.

Adding planted defects to `demo_codebase/` is very welcome: it raises the bar for every future skill. Keep every
value fake and add the defect to `GROUND_TRUTH.yaml` with robust keywords.

## Versioning and releases

Tag releases `vX.Y.Z`. Repositories may pin `gate-ref` to a tag to control when policy changes land; the default
is `main`.
