"""Lifecycle orchestration independent of the example habitat."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Any

from kosmos.genetics import Genome, GenomeSchema
from kosmos.interfaces import Decision, Policy, World, plugin_source_digest


def stream(seed: int, namespace: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{namespace}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _tuples(value: Any) -> Any:
    return tuple(_tuples(v) for v in value) if isinstance(value, list) else value


@dataclass(frozen=True)
class EngineConfig:
    seed: int = 1
    population: int = 12
    max_population: int = 64
    initial_energy: float = 12.0
    metabolism: float = 0.4
    max_age: int = 100
    maturity_age: int = 3
    offspring_energy: float = 4.0
    birth_overhead: float = 2.0
    reproduction: str = "clonal"
    mutation_rate: float = 0.1
    mutation_scale: float = 0.1

    def __post_init__(self) -> None:
        for name in ("seed", "population", "max_population", "max_age", "maturity_age"):
            value = getattr(self, name)
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.population <= self.max_population:
            raise ValueError("Require 1 <= population <= max_population")
        if self.max_age < 1 or not 0 <= self.maturity_age < self.max_age:
            raise ValueError("Maturity must precede maximum age")
        for name in ("initial_energy", "offspring_energy", "metabolism", "birth_overhead",
                     "mutation_rate", "mutation_scale"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.initial_energy <= 0 or self.offspring_energy <= 0:
            raise ValueError("Starting energy must be positive")
        if self.mutation_rate > 1:
            raise ValueError("mutation_rate must be in [0, 1]")
        if self.reproduction not in ("clonal", "recombine", "disabled"):
            raise ValueError("Unknown reproduction mode")


@dataclass
class Agent:
    agent_id: str
    genome: Genome
    energy: float
    born_tick: int
    generation: int = 0
    parents: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["genome"] = self.genome.to_dict()
        result["parents"] = list(self.parents)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Agent:
        genome = data["genome"]
        return cls(
            agent_id=data["agent_id"],
            genome=Genome(genome["schema_id"], tuple(genome["values"])),
            energy=data["energy"], born_tick=data["born_tick"],
            generation=data["generation"], parents=tuple(data["parents"]),
        )


class Engine:
    FORMAT_VERSION = 1

    def __init__(self, config: EngineConfig, schema: GenomeSchema, world: World, policy: Policy):
        self.config, self.schema, self.world, self.policy = config, schema, world, policy
        self.tick = 0
        self.next_id = 0
        self.births = 0
        self.deaths = 0
        self.world_rng = stream(config.seed, "world")
        self.genetics_rng = stream(config.seed, "genetics")
        self.lifecycle_rng = stream(config.seed, "lifecycle")
        self.agents: dict[str, Agent] = {}
        self.policy_rngs: dict[str, random.Random] = {}
        founder_rng = stream(config.seed, "founders")
        for _ in range(config.population):
            agent_id = self._allocate_id()
            self.agents[agent_id] = Agent(
                agent_id, schema.sample(founder_rng), config.initial_energy, 0,
            )
            self.policy_rngs[agent_id] = stream(config.seed, f"policy:{agent_id}")
        world.reset(sorted(self.agents), self.world_rng)

    def _allocate_id(self) -> str:
        agent_id = f"a{self.next_id:08d}"
        self.next_id += 1
        return agent_id

    def metrics(self) -> dict[str, Any]:
        return {
            "tick": self.tick, "population": len(self.agents),
            "births": self.births, "deaths": self.deaths,
            "total_energy": sum(a.energy for a in self.agents.values()),
            "max_generation": max((a.generation for a in self.agents.values()), default=0),
        }

    def step(self) -> list[dict[str, Any]]:
        """Observe together, act together, resolve survival, then reproduce.

        Newborns first act on the following tick. A parent participates in at
        most one birth per tick. Capacity is a slot constraint, not fitness.
        """
        decisions: dict[str, Decision] = {}
        observations: dict[str, dict[str, Any]] = {}
        for agent_id in sorted(self.agents):
            agent = self.agents[agent_id]
            # Copy across the plugin boundary to prevent observation mutation.
            observation = json.loads(json.dumps(self.world.observe(agent_id), allow_nan=False))
            observation.update(energy=agent.energy, age=self.tick - agent.born_tick)
            observations[agent_id] = observation
            decision = self.policy.decide(observation, agent.genome, self.policy_rngs[agent_id])
            if not isinstance(decision, Decision) or not isinstance(decision.action, str):
                raise ValueError("Policies must return Decision objects")
            if type(decision.reproduce) is not bool:
                raise ValueError("Reproduction intent must be boolean")
            if not isinstance(decision.parameters, dict):
                raise ValueError("Action parameters must be a dictionary")
            if decision.message is not None and not isinstance(decision.message, str):
                raise ValueError("Messages must be text or None")
            # Freeze caller-owned dictionaries before another policy invocation.
            decisions[agent_id] = Decision(**json.loads(json.dumps(asdict(decision), allow_nan=False)))

        outcome = self.world.step(decisions, self.world_rng)
        if set(outcome.energy_delta) != set(self.agents):
            raise ValueError("World must return one energy delta for every acting agent")
        for value in outcome.energy_delta.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("World returned a non-finite or nonnumeric energy delta")
        self.tick += 1
        events: list[dict[str, Any]] = [{
            "type": "decision", "tick": self.tick, "agent_id": agent_id,
            "observation": observations[agent_id], "decision": asdict(decisions[agent_id]),
        } for agent_id in sorted(decisions)]
        events.extend({"type": "world", "tick": self.tick, "detail": e} for e in outcome.events)
        for agent_id in sorted(list(self.agents)):
            agent = self.agents[agent_id]
            agent.energy += outcome.energy_delta[agent_id] - self.config.metabolism
            if not math.isfinite(agent.energy):
                raise ValueError("Agent energy became non-finite")
            reason = None
            if agent.energy <= 0:
                reason = "energy"
            elif self.tick - agent.born_tick >= self.config.max_age:
                reason = "age"
            if reason:
                self.world.on_death(agent_id)
                del self.agents[agent_id]
                del self.policy_rngs[agent_id]
                self.deaths += 1
                events.append({
                    "type": "death", "tick": self.tick, "agent_id": agent_id, "reason": reason,
                })
        events.extend(self._reproduce(decisions))
        # Observer frames are privileged; these are never policy observations.
        events.append({
            "type": "frame", "tick": self.tick, "metrics": self.metrics(),
            "agents": [a.to_dict() for a in self.agents.values()], "world": self.world.snapshot(),
        })
        return events

    def _reproduce(self, decisions: dict[str, Decision]) -> list[dict[str, Any]]:
        if self.config.reproduction == "disabled":
            return []
        nparents = 2 if self.config.reproduction == "recombine" else 1
        contribution = (self.config.offspring_energy + self.config.birth_overhead) / nparents
        candidates = [
            agent_id for agent_id in sorted(self.agents)
            if decisions[agent_id].reproduce
            and self.tick - self.agents[agent_id].born_tick >= self.config.maturity_age
            and self.agents[agent_id].energy > contribution
        ]
        self.lifecycle_rng.shuffle(candidates)
        used: set[str] = set()
        events = []
        for first in candidates:
            if len(self.agents) >= self.config.max_population:
                break
            if first in used:
                continue
            parents = (first,)
            if nparents == 2:
                second = next((
                    candidate for candidate in candidates
                    if candidate != first and candidate not in used
                    and self.world.can_mate(first, candidate)
                ), None)
                if second is None:
                    continue
                parents = (first, second)
            genome, inheritance = self.schema.reproduce(
                tuple(self.agents[p].genome for p in parents), self.genetics_rng,
                self.config.mutation_rate, self.config.mutation_scale,
            )
            child_id = self._allocate_id()
            child = Agent(
                child_id, genome, self.config.offspring_energy, self.tick,
                max(self.agents[p].generation for p in parents) + 1, parents,
            )
            self.world.on_birth(child_id, parents, self.world_rng)
            for parent in parents:
                self.agents[parent].energy -= contribution
            self.agents[child_id] = child
            self.policy_rngs[child_id] = stream(self.config.seed, f"policy:{child_id}")
            self.births += 1
            used.update(parents)
            events.append({
                "type": "birth", "tick": self.tick, "child": child.to_dict(),
                "contribution_per_parent": contribution, "inheritance": inheritance,
            })
        return events

    def snapshot(self) -> dict[str, Any]:
        return {
            "format_version": self.FORMAT_VERSION, "config": asdict(self.config),
            "schema": self.schema.to_dict(), "tick": self.tick, "next_id": self.next_id,
            "births": self.births, "deaths": self.deaths,
            "world_id": self.world.world_id, "world_config": self.world.config_dict(),
            "policy_id": self.policy.policy_id, "world": self.world.snapshot(),
            "plugin_sources": {
                "world": plugin_source_digest(self.world), "policy": plugin_source_digest(self.policy),
            },
            "agents": [a.to_dict() for a in self.agents.values()],
            "rng": {
                "world": self.world_rng.getstate(), "genetics": self.genetics_rng.getstate(),
                "lifecycle": self.lifecycle_rng.getstate(),
                "policies": {key: value.getstate() for key, value in self.policy_rngs.items()},
            },
        }

    @classmethod
    def restore(cls, state: dict[str, Any], world: World, policy: Policy) -> Engine:
        if state["format_version"] != cls.FORMAT_VERSION:
            raise ValueError("Unsupported checkpoint format")
        if world.world_id != state["world_id"] or policy.policy_id != state["policy_id"]:
            raise ValueError("Checkpoint plugin identity mismatch")
        if state["plugin_sources"] != {
            "world": plugin_source_digest(world), "policy": plugin_source_digest(policy),
        }:
            raise ValueError("Checkpoint plugin source changed; migration is required")
        if world.config_dict() != state["world_config"]:
            raise ValueError("Checkpoint world configuration mismatch")
        obj = cls.__new__(cls)
        obj.config = EngineConfig(**state["config"])
        obj.schema = GenomeSchema.from_dict(state["schema"])
        obj.world, obj.policy = world, policy
        obj.tick, obj.next_id = state["tick"], state["next_id"]
        obj.births, obj.deaths = state["births"], state["deaths"]
        for name in ("tick", "next_id", "births", "deaths"):
            if type(getattr(obj, name)) is not int or getattr(obj, name) < 0:
                raise ValueError("Invalid lifecycle counters")
        obj.agents = {}
        for data in state["agents"]:
            agent = Agent.from_dict(data)
            obj.schema.validate(agent.genome)
            if agent.agent_id in obj.agents or not math.isfinite(agent.energy) or agent.energy <= 0:
                raise ValueError("Invalid checkpoint agent")
            if type(agent.born_tick) is not int or not 0 <= agent.born_tick <= obj.tick:
                raise ValueError("Invalid birth tick")
            if type(agent.generation) is not int or agent.generation < 0:
                raise ValueError("Invalid generation")
            if agent.agent_id != f"a{int(agent.agent_id[1:]):08d}":
                raise ValueError("Invalid agent identifier")
            if not 0 <= int(agent.agent_id[1:]) < obj.next_id:
                raise ValueError("Identifier counter would reuse an existing agent ID")
            obj.agents[agent.agent_id] = agent
        if len(obj.agents) > obj.config.max_population:
            raise ValueError("Checkpoint exceeds population capacity")
        if obj.next_id != obj.config.population + obj.births:
            raise ValueError("Inconsistent birth counter")
        if len(obj.agents) != obj.next_id - obj.deaths:
            raise ValueError("Inconsistent death counter")
        obj.world_rng = random.Random()
        obj.genetics_rng = random.Random()
        obj.lifecycle_rng = random.Random()
        obj.world_rng.setstate(_tuples(state["rng"]["world"]))
        obj.genetics_rng.setstate(_tuples(state["rng"]["genetics"]))
        obj.lifecycle_rng.setstate(_tuples(state["rng"]["lifecycle"]))
        if set(state["rng"]["policies"]) != set(obj.agents):
            raise ValueError("Missing or extra per-agent RNG states")
        obj.policy_rngs = {}
        for agent_id, rng_state in state["rng"]["policies"].items():
            obj.policy_rngs[agent_id] = random.Random()
            obj.policy_rngs[agent_id].setstate(_tuples(rng_state))
        world.restore(state["world"], sorted(obj.agents))
        return obj
