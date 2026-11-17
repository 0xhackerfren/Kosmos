# Current state

## Repository initialization

Kosmos is the public platform repository. A runnable Python foundation has been
authored through the GitHub connector. The original ECI archive is preserved
separately and has not been imported or revalidated.

Implemented source includes:

- A world-independent lifecycle engine, explicit world/policy contracts, and registry.
- Bounded numeric genomes, mutation, clonal and two-parent inheritance.
- Parent-funded offspring energy, maturity, age/energy death, capacity constraints.
- A resource habitat with local observations and costly, bounded local messages.
- A scripted reference policy and an independently registered custom-world example.
- JSONL records, provenance, atomic JSON checkpoints, and checked continuation.
- 26 automated tests plus command-line smoke checks and a Python 3.11/3.12 CI matrix.
- MIT license and contributor/world-authoring documentation.

## Validation status

Tests have been authored but not executed locally: the initialization session
has no executor. GitHub Actions validation is the next gate. Consult the tests
workflow on the exact implementation commit for its actual outcome.

No pilot results or thesis findings were generated in this initialization.

## Reentry

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m kosmos run --config examples/habitat.json --steps 200 --output runs/demo
python -m kosmos resume runs/demo/checkpoint.json --steps 200 --output runs/continued
```

Use new output directories. Resuming requires the same Python version and
unchanged core/world/policy source; checkpoint migrations are not yet implemented.

## Next actions

1. Run CI and fix failures before treating the foundation as validated.
2. Follow docs/CHECKPOINT_RECOVERY.md when the earlier archive can be unpacked.
3. Reconcile existing code and research artifacts without overwriting provenance.
4. Establish a replicated, controlled first experiment.
5. Add a read-only observer before attempting a Unity environment adapter.

The current policies are scripted. LLM backends, cultural inheritance, graphical
observation, Unity, and long-duration operating controls are not implemented.
