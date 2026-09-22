# Skill challenge

The eight skills are the organisation's shared review standard. Anyone may try to improve one; the repository
decides objectively and credits the contributor. The repository never contains more or fewer than eight skills.

## How to challenge

1. Branch from `main` in this repository (forks are not accepted).
2. Edit `skills/<NN-phase>/SKILL.md`. Keep the front matter (`name`, `phase`, `description`) and bump `version`.
   Change nothing else: no new files, no other directories.
3. Open a pull request. The **Skill Challenge** workflow runs automatically.

## What happens

1. Your candidate is checked structurally: valid front matter, matching phase, semantic version, sensible size,
   and no text that tries to instruct the gate or the arbiter (that fails validation immediately).
2. The current skill and your candidate are both validated against the organisation's review benchmark and
   scored on **coverage** (how much of what should be found is found), **precision** (how much of what is found
   is real), and **clarity** (how specific and actionable the findings are). The weighted score is
   `0.6·coverage + 0.25·precision + 0.15·clarity`.
3. The arbiter model reads both skills and both score sheets and proposes one of:
   - **keep current** — the candidate is not better, or is noisier;
   - **replace** — the candidate is clearly better as a whole (it must beat the current score by a margin);
   - **merge** — specific sections of the candidate improve the current skill; a merged skill is produced,
     validated and re-scored before it is accepted.
4. The resolved skill (version bumped) and a row in `CREDITS.md` naming you, the decision and the parts of
   your work that were used are committed to your branch. The full comparison is posted on the pull request.
5. Accepted challenges (`replace`, `merge`) get the label `challenge:accepted` and merge automatically once
   checks pass; you remain the author of the merged commit. Rejected challenges get `challenge:rejected` and are
   closed with the comparison so you can iterate.

## Credit

- **replace**: your text becomes the skill; `CREDITS.md` records `entire skill`.
- **merge**: `CREDITS.md` lists the sections of your candidate that were absorbed.
- **keep current**: no credit row, but you get both score sheets.

## Improving your odds

- Precision matters as much as coverage. A skill that floods reviewers with speculative findings loses even if
  it finds more.
- Say what *not* to flag, not just what to flag.
- Keep the category taxonomy stable; add categories only in kebab-case and use them consistently.
- Give the model concrete severity rules and ask for file/line and a concrete fix in every finding.
- Do not address the arbiter or the gate in the skill text.

## Rules

- One challenge per pull request per skill is fine; several skills in one PR are scored independently.
- The arbiter is the only way skills change. Code owners cannot merge a skill change that bypasses it.
- Every decision, score sheet and guard is recorded in the workflow run for audit.
