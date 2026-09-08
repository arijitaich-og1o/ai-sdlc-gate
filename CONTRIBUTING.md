# Contributing

## Improving a skill (anyone in the organisation)

1. Branch from `main` in this repository (forks are not accepted by the arbiter).
2. Edit exactly one or more of `skills/<NN-phase>/SKILL.md`. Keep the front matter; bump `version`.
   Do not add files, directories or change anything outside `skills/`.
3. Open a pull request. The **Skill Challenge** workflow validates your version against the current one and
   posts the comparison. If yours is better (or parts of it are), it is written to your branch,
   you are added to `CREDITS.md`, and the PR auto-merges. If not, the PR is closed with the scores so you can
   iterate.

Tips: precision matters as much as coverage; a skill that floods reviewers loses. Say what not to flag.

## Improving the engine, policy, benchmark or workflows (code owners)

1. Branch, change, add tests under `gate/tests`.
2. `pip install -e "./gate[dev]" && pytest gate/tests` and run the hygiene scripts:
   `python scripts/check_pinned_actions.py .github/workflows` and
   `python scripts/check_ground_truth.py trials`.
3. Open a PR. `Validate Repository` and `Self Gate` must pass and a code owner must approve.

Extending the benchmark under `trials/` is very welcome: it raises the bar for every future skill. Keep every
value fake and describe the expected outcome in the phase's `GROUND_TRUTH.yaml` with robust keywords.

## Versioning and releases

Tag releases `vX.Y.Z`. Repositories may pin `gate-ref` to a tag to control when policy changes land; the default
is `main`.
