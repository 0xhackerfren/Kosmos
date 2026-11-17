"""Version-one extension contracts. Worlds and policies are explicitly registered."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import inspect
from pathlib import Path
import random
from typing import Any, Protocol

from kosmos.genetics import Genome


@dataclass(frozen=True)
class Decision:
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    reproduce: bool = False
    message: str | None = None


@dataclass(frozen=True)
class Outcome:
    energy_delta: dict[str, float]
    events: list[dict[str, Any]] = field(default_factory=list)


class Policy(Protocol):
    """Stateless controller: sees one agent's observation and inherited genome.

    Stateful policies must wait for an explicit lifetime-state/checkpoint contract.
    A shared mutable policy would create an unrecorded cultural memory channel.
    """
    policy_id: str

    def decide(
        self, observation: dict[str, Any], genome: Genome, rng: random.Random,
    ) -> Decision: ...


class World(Protocol):
    world_id: str

    def config_dict(self) -> dict[str, Any]: ...
    def reset(self, agent_ids: list[str], rng: random.Random) -> None: ...
    def observe(self, agent_id: str) -> dict[str, Any]: ...
    def step(self, decisions: dict[str, Decision], rng: random.Random) -> Outcome: ...
    def can_mate(self, first: str, second: str) -> bool: ...
    def on_birth(self, child: str, parents: tuple[str, ...], rng: random.Random) -> None: ...
    def on_death(self, agent_id: str) -> None: ...
    def snapshot(self) -> dict[str, Any]: ...
    def restore(self, state: dict[str, Any], agent_ids: list[str]) -> None: ...

def plugin_source_digest(plugin: object) -> str:
    """Fingerprint the defining module, including file-backed third-party plugins."""
    path = inspect.getsourcefile(type(plugin))
    if path is None:
        raise ValueError("Checkpointable plugins require file-backed Python source")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
