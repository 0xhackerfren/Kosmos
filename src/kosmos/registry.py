"""Explicit plugin registry; checkpoint strings never trigger arbitrary imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from kosmos.genetics import GenomeSchema, HABITAT_SCHEMA
from kosmos.interfaces import Policy, World
from kosmos.policies import Forager
from kosmos.worlds.habitat import Habitat


@dataclass(frozen=True)
class WorldSpec:
    factory: Callable[..., World]
    schema: GenomeSchema


_WORLDS: dict[str, WorldSpec] = {}
_POLICIES: dict[str, Callable[[], Policy]] = {}


def register_world(world_id: str, factory: Callable[..., World], schema: GenomeSchema) -> None:
    if not world_id or world_id in _WORLDS:
        raise ValueError("World identifier must be unique and nonempty")
    _WORLDS[world_id] = WorldSpec(factory, schema)


def register_policy(policy_id: str, factory: Callable[[], Policy]) -> None:
    if not policy_id or policy_id in _POLICIES:
        raise ValueError("Policy identifier must be unique and nonempty")
    _POLICIES[policy_id] = factory


def world_spec(world_id: str) -> WorldSpec:
    try:
        return _WORLDS[world_id]
    except KeyError:
        raise ValueError(f"World is not registered: {world_id}") from None


def make_policy(policy_id: str) -> Policy:
    try:
        factory = _POLICIES[policy_id]
    except KeyError:
        raise ValueError(f"Policy is not registered: {policy_id}") from None
    return factory()


register_world(Habitat.world_id, Habitat, HABITAT_SCHEMA)
register_policy(Forager.policy_id, Forager)
