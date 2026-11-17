# Kosmos development instructions

Read README.md, STATE.md, RESEARCH_CHARTER.md, and docs/ARCHITECTURE.md before
making substantial changes.

- Continue from the actual repository state. Never invent experiments or results.
- The earlier ECI ZIP has not been recovered unless STATE.md records evidence.
- Keep world and policy extensions independent of the lifecycle engine.
- Separate genotype, lifetime state, cultural information, and observer-only data.
- Preserve source/config/runtime/seed provenance and auditable inheritance records.
- Run python -m unittest discover -s tests -v after behavioral changes.
- Report actual CI outcomes and distinguish unexecuted tests from passing checks.
- Treat source changes as requiring explicit checkpoint migration.
- Do not provision paid compute or start long-running jobs without a defined,
  authorized budget.
- Update STATE.md with completed work, evidence, blockers, and exact next actions.
