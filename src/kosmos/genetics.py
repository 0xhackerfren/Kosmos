"""Bounded numeric genomes and auditable inheritance; no model-weight mutation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Any


@dataclass(frozen=True)
class Gene:
    name: str
    low: float
    high: float

    def __post_init__(self) -> None:
        if not self.name or not math.isfinite(self.low) or not math.isfinite(self.high):
            raise ValueError("Gene names and finite bounds are required")
        if self.low >= self.high:
            raise ValueError("Gene lower bound must be below its upper bound")


@dataclass(frozen=True)
class Genome:
    schema_id: str
    values: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "values": list(self.values)}


@dataclass(frozen=True)
class GenomeSchema:
    schema_id: str
    genes: tuple[Gene, ...]

    def __post_init__(self) -> None:
        if not self.schema_id or not self.genes:
            raise ValueError("A schema identifier and at least one gene are required")
        if len({gene.name for gene in self.genes}) != len(self.genes):
            raise ValueError("Duplicate gene names")

    def validate(self, genome: Genome) -> None:
        if genome.schema_id != self.schema_id or len(genome.values) != len(self.genes):
            raise ValueError("Genome schema mismatch")
        for gene, value in zip(self.genes, genome.values):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Non-numeric allele: {gene.name}")
            if not math.isfinite(value) or not gene.low <= value <= gene.high:
                raise ValueError(f"Allele out of bounds: {gene.name}")

    def decode(self, genome: Genome) -> dict[str, float]:
        self.validate(genome)
        return {gene.name: value for gene, value in zip(self.genes, genome.values)}

    def sample(self, rng: random.Random) -> Genome:
        return Genome(self.schema_id, tuple(rng.uniform(g.low, g.high) for g in self.genes))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "genes": [asdict(g) for g in self.genes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomeSchema:
        return cls(data["schema_id"], tuple(Gene(**g) for g in data["genes"]))

    def reproduce(
        self,
        parents: tuple[Genome, ...],
        rng: random.Random,
        mutation_rate: float,
        mutation_scale: float,
    ) -> tuple[Genome, dict[str, Any]]:
        """One-parent cloning or per-locus two-parent recombination, then mutation.

        Scale is a fraction of each locus's allowed range. Every inheritance
        choice and attempted mutation is recorded, including clamped/no-op ones.
        """
        if len(parents) not in (1, 2):
            raise ValueError("Reproduction requires one or two parents")
        if not math.isfinite(mutation_rate) or not 0 <= mutation_rate <= 1:
            raise ValueError("Mutation rate must be in [0, 1]")
        if not math.isfinite(mutation_scale) or mutation_scale < 0:
            raise ValueError("Mutation scale must be finite and nonnegative")
        for parent in parents:
            self.validate(parent)
        values, sources, mutations = [], [], []
        for index, gene in enumerate(self.genes):
            source = rng.randrange(len(parents)) if len(parents) == 2 else 0
            before = parents[source].values[index]
            after = before
            if rng.random() < mutation_rate:
                delta = rng.gauss(0, mutation_scale * (gene.high - gene.low))
                after = min(gene.high, max(gene.low, before + delta))
                mutations.append({
                    "gene": gene.name, "before": before, "proposed_delta": delta,
                    "after": after,
                })
            values.append(after)
            sources.append(source)
        child = Genome(self.schema_id, tuple(values))
        self.validate(child)
        return child, {"locus_sources": sources, "mutations": mutations}


HABITAT_SCHEMA = GenomeSchema(
    "kosmos.habitat.numeric.v1",
    (
        Gene("exploration", 0.0, 1.0),
        Gene("signal_probability", 0.0, 1.0),
        Gene("reproduction_threshold", 6.0, 24.0),
    ),
)
