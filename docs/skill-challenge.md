# Skill challenge

The seven skills are the organisation's shared review standard. Anyone may try to improve one; the repository
decides objectively and credits the contributor. The repository never contains more or fewer than seven skills.

## Procedure

1. A developer edits `skills/<NN-phase>/SKILL.md` on a branch of this repository and opens a PR.
2. `Skill Challenge` refuses forks and PRs touching anything but `skills/*/SKILL.md` (and `CREDITS.md`).
3. For each changed skill the engine:
   - loads the **current** skill from the base commit and the **candidate** from the PR head;
   - validates both (front matter, phase, semver, size, no forbidden instruction patterns);
   - runs both against `demo_codebase/<phase>/` and matches findings against `GROUND_TRUTH.yaml`:
     `recall` (planted defects found), `precision` (findings that are planted or judged legitimate),
     `clarity` (judge rating 0–1); `score = 0.6·recall + 0.25·precision + 0.15·clarity`;
   - asks the arbiter model (`llm.judge_model`) for `keep_current`, `replace` or `merge` with a rationale and,
     for merge, a merged body and the list of absorbed sections;
   - applies **guards**: `replace` needs `candidate ≥ current + min_improvement`; a merged skill must parse and
     validate; with `challenge.verify_merge` the merged skill is re-evaluated and must not score below the
     better input, otherwise the better input is used; unknown/failed arbiter output means `keep_current`.
4. The resolved skill is written to the branch (version bumped), `CREDITS.md` gains a row naming the contributor,
   decision, version and which parts were used, and a commit prefixed `skill-challenge:` is pushed.
5. The full comparison (scores, missed defects for each version, rationale, guards) is posted on the PR.
6. Accepted (`replace`/`merge`): label `challenge:accepted`, auto-merge (squash) enabled; the PR author remains
   the commit author. Rejected (`keep_current`): label `challenge:rejected`, PR closed with the comparison.
7. On the resolution commit the workflow re-runs, detects the `skill-challenge:` prefix, verifies the seven
   skills and does not arbitrate again (no loops, no double spend).

## Credit

- `replace`: your text becomes the skill; CREDITS.md says `entire skill`; you are the author of the squash
  commit.
- `merge`: the arbiter lists which sections of your candidate were absorbed; CREDITS.md records them.
- `keep_current`: no credit row, but the comparison shows exactly which planted defects you missed or found.

## Improving your odds

- Read the ground truth for your phase; the missed-defects list in a rejected challenge is your to-do list.
- Keep the taxonomy stable; new categories are fine if they are kebab-case and used consistently.
- Be precise: instruct what *not* to flag. Spurious findings lower precision and the arbiter penalises noise.
- Do not address the arbiter or the gate in the skill text; forbidden-instruction patterns fail validation.

## Extending the demo codebase

Planted defects are the benchmark. Adding realistic defects (with fake data only) through a code-owner PR makes
every future challenge more meaningful. Each defect needs a stable id, file, severity and robust keywords.
