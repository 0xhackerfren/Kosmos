# Kosmos

**Build worlds. Evolve populations. Investigate what emerges.**

Kosmos is an open-source research platform for populations of agents with
heritable configurations, reproduction, mutation, local communication, and
explicit environmental rules. Researchers can replace the world and controller
without modifying the lifecycle engine.

The first implementation is a small, dependency-free Python reference system.
Its agents use scripted policies. LLM backends, cultural inheritance, a graphical
observer, and Unity integration are planned extensions.

## Try a world

Requires Python 3.11 or newer. CI targets Python 3.11 and 3.12.

```bash
git clone https://github.com/0xhackerfren/Kosmos.git
cd Kosmos
python -m pip install -e .
python -m kosmos run --config examples/habitat.json --steps 200 --output runs/demo
python -m kosmos resume runs/demo/checkpoint.json --steps 200 --output runs/continued
```

Each output directory is new: an existing run is never overwritten. Runs contain
a provenance manifest, JSONL observations/actions/births/deaths/observer frames,
a summary, and an atomic JSON checkpoint. A continuation records its parent
checkpoint's checksum. No model server, external API, or paid service is used.

## What the foundation includes

- Versioned numeric genome schemas with bounded alleles and explicit decoding.
- Clonal reproduction or two-parent, per-locus recombination.
- Mutation records, parent identifiers, generation counters, and birth energy accounting.
- Energy and age mortality, maturity requirements, and a population capacity.
- A discrete resource habitat with simultaneous actions and partial observations.
- Local, byte-limited messages with an energy cost and a predefined signal vocabulary.
- Separate random streams for world dynamics, genetics, lifecycle, and individual policies.
- JSON checkpoint/resume with source/runtime checks and complete RNG state.
- Public world/policy interfaces and a second, independently registered example world.

The habitat's genes control exploration, signaling probability, and the energy
threshold for requesting reproduction. These are behavioral parameters, not
changes to model weights. The signal `food` is predefined: this example does
**not** demonstrate emergent language, specialization, or collective intelligence.

## Build your own world

Start with [the world authoring guide](docs/WORLDS.md) and
[the complete custom-world example](examples/custom_world.py):

```bash
python examples/custom_world.py run --config examples/custom_world.json --steps 20 --output runs/custom
python examples/custom_world.py resume runs/custom/checkpoint.json --steps 20 --output runs/custom-continued
```

A world defines observations, actions, resource effects, mating constraints,
birth/death placement, and serializable state. The engine manages identities,
genomes, survival, reproduction, and trajectories.

## Validate

```bash
python -m unittest discover -s tests -v
```

[GitHub Actions](https://github.com/0xhackerfren/Kosmos/actions) runs invariant,
trajectory continuation, and CLI checks. Check the workflow for actual validation
status; implementation alone is not an experimental result.

## Research and next steps

- [Current state and reentry instructions](STATE.md)
- [Architecture and scientific boundaries](docs/ARCHITECTURE.md)
- [Research charter](RESEARCH_CHARTER.md)
- [Development roadmap](ROADMAP.md)
- [Earlier checkpoint recovery](docs/CHECKPOINT_RECOVERY.md)
- [Contribution guidance](CONTRIBUTING.md)

This repository begins a new platform foundation. The earlier ECI archive has
not yet been imported or revalidated. No historical pilot data or findings are
represented as reproduced here.

MIT licensed. This is an early research implementation, not yet a validated
year-long unattended experiment service.
