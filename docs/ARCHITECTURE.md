# Architecture

## Ownership

| Component | Owns |
| --- | --- |
| GenomeSchema | Allele bounds, decoding, recombination, mutation records |
| Engine | Identity, age, energy, survival, reproduction, RNG streams |
| World | Environmental state, observations, actions, resources, communication |
| Policy | Stateless decisions from one observation and one genome |
| Runner | Files, provenance, checkpoints, continuation ancestry |
| Observer | Privileged recorded frames, separate from policy observations |

## One tick

1. All live agents observe the same pre-action world state. The engine adds the
   agent's own energy and age, then copies each observation before calling its policy.
2. Policies choose actions and optional reproduction/message intents using
   independent, persistent per-agent random streams.
3. The world validates and resolves the action batch. In the habitat, movement
   precedes harvest contention; messages are delivered for next-tick observation,
   and resource regrowth follows harvest.
4. The engine applies resource effects and metabolism, then removes agents
   whose energy is nonpositive or whose maximum age is reached.
5. Surviving, mature, willing parents compete for birth slots in a seeded,
   shuffled order. A parent can contribute to only one birth per tick.
6. Each birth transfers offspring energy from the parent(s), plus a specified
   overhead that leaves the system. Parents must retain positive energy.
   Two-parent reproduction requires world-defined mating compatibility.
7. Children receive inherited/mutated genomes and fresh policy RNG streams;
   they first act next tick. An observer frame is emitted.

Ecological resource constraints and differential survival/reproduction can
change population composition. The engine has no imposed score-based selection
optimizer or claim of open-ended evolution.

## Heredity

The current genome is numeric and versioned. Mutations are Gaussian perturbations
scaled by each locus's allowed range and clamped at the bounds. The record
distinguishes proposed changes from realized values.

A numeric trait's meaning is the executable mapping in its policy. The habitat
schema encodes exploration probability, signaling probability, and a reproduction
request threshold. Roles and language conventions are not encoded or inferred.

There is no inherited lifetime memory, inherited conversation, or cultural
archive in this version. Such channels require separate explicit contracts and
ablation controls. Stateful policy instances are currently unsupported because
they would hide information outside checkpoints.

## Reproducibility and records

Checkpoints include live agents, world state, schema, lifecycle counters, and
all RNG states (including Gaussian caches). The envelope includes a checksum,
the installed core-source digest, and the Python version. World/policy defining
modules have additional source digests, including file-backed external plugins.

The runner refuses resume after a core/plugin source or Python-version change.
Dependencies, external assets, and model stochasticity will need stronger
provenance before adding inference backends. A checksum detects corruption;
it is not a signature or proof that a downloaded file is trustworthy.

Event logs record observations, decisions, messages, births with parental
contributions and mutation records, deaths, and full observer frames. Genome
ancestry for dead agents is reconstructed from these records rather than kept
in unbounded engine memory. Initial founders appear in the start record.

An exception marks the run failed and preserves the last complete checkpoint.
A continuation writes to a new directory and identifies that checkpoint. There
is no claim of an atomic transaction spanning the event log and checkpoint;
a crash can leave trailing log events beyond the checkpoint. Treat the checkpoint
tick as the continuation boundary and do not count overlapping events twice.

Checkpoint replacement is atomic on the local filesystem and the file is flushed.
Directory metadata is not explicitly fsynced; this is not a power-loss durability
guarantee. Logs are flushed per tick but are not fsynced per event.

Exact continuation is checked for supported local reference configurations.
Universal reproducibility across operating systems, dependencies, models, or
future Unity physics is not claimed.

## Unity boundary

First add an observer that reads recorded frames and renders agents, resources,
messages, ancestry, and trait distributions. Observation/playback must not advance
or alter the scientific simulation.

A later UnityWorld adapter may implement the same World contract when physics
or embodiment is an experimental variable. The Python engine continues to own
genomes and lifecycle rules. One controller owns simulation time; do not run
two competing clocks. Unity agent IDs need explicit mapping to permanent Kosmos
IDs. Births, deaths, resets, and interruptions need protocol events.

Recorded playback and a fresh rerun are distinct modes. Pin builds and runtime
versions and test reproducibility before using Unity results scientifically.

## Scientific limits

The scripted habitat is a machinery validation task. Its fixed signal vocabulary,
handwritten decisions, resource density, and reproduction rules shape its behavior.
It cannot establish emergent language, spontaneous specialization, or an LLM thesis.

Reproduction disabled and mutation disabled are useful mechanism checks, but they
are not automatically population- or compute-matched research controls. Before
confirmatory studies, design independent seeds, held-out worlds, selection controls,
communication interventions, competitive optimization baselines, and compute accounting.
