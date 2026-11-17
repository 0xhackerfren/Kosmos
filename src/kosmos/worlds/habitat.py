"""A discrete toroidal resource world with local observations and local messages."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Any

from kosmos.interfaces import Decision, Outcome


@dataclass(frozen=True)
class HabitatConfig:
    width: int = 12
    height: int = 12
    food_capacity: int = 4
    regrowth_probability: float = 0.12
    food_energy: float = 3.0
    movement_cost: float = 0.1
    message_cost: float = 0.05
    message_radius: int = 2
    max_message_bytes: int = 64

    def __post_init__(self) -> None:
        for name in ("width", "height", "food_capacity", "message_radius", "max_message_bytes"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if self.width < 3 or self.height < 3 or self.food_capacity < 1:
            raise ValueError("Habitat dimensions must be >= 3 and food capacity positive")
        if self.message_radius < 0 or self.max_message_bytes < 1:
            raise ValueError("Invalid communication limits")
        for name in ("regrowth_probability", "food_energy", "movement_cost", "message_cost"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.regrowth_probability > 1:
            raise ValueError("Regrowth probability must be in [0, 1]")


class Habitat:
    world_id = "kosmos.habitat.v1"

    def __init__(self, **config: Any):
        self.config = HabitatConfig(**config)
        self.food: list[list[int]] = []
        self.positions: dict[str, tuple[int, int]] = {}
        self.inboxes: dict[str, list[dict[str, Any]]] = {}

    def config_dict(self) -> dict[str, Any]:
        return asdict(self.config)

    def reset(self, agent_ids: list[str], rng: random.Random) -> None:
        c = self.config
        self.food = [[rng.randint(0, c.food_capacity) for _ in range(c.width)]
                     for _ in range(c.height)]
        self.positions = {key: (rng.randrange(c.width), rng.randrange(c.height))
                          for key in agent_ids}
        self.inboxes = {key: [] for key in agent_ids}

    def observe(self, agent_id: str) -> dict[str, Any]:
        x, y = self.positions[agent_id]
        return {
            "cells": [
                {"dx": dx, "dy": dy,
                 "food": self.food[(y + dy) % self.config.height][(x + dx) % self.config.width]}
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            ],
            "messages": [dict(message) for message in self.inboxes[agent_id]],
        }

    def _offset(self, source: str, target: str) -> tuple[int, int]:
        sx, sy = self.positions[source]
        tx, ty = self.positions[target]
        c = self.config
        return (
            (tx - sx + c.width // 2) % c.width - c.width // 2,
            (ty - sy + c.height // 2) % c.height - c.height // 2,
        )

    def step(self, decisions: dict[str, Decision], rng: random.Random) -> Outcome:
        if set(decisions) != set(self.positions):
            raise ValueError("Habitat actions must match the live population")
        # Validate the entire batch before changing the world.
        for decision in decisions.values():
            if decision.action not in ("move", "harvest", "wait"):
                raise ValueError(f"Unknown habitat action: {decision.action}")
            if decision.action == "move":
                if set(decision.parameters) != {"dx", "dy"}:
                    raise ValueError("Move requires dx and dy")
                dx, dy = decision.parameters["dx"], decision.parameters["dy"]
                if type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1:
                    raise ValueError("Move must be one cardinal cell")
            elif decision.parameters:
                raise ValueError("Harvest and wait do not accept parameters")
            if decision.message is not None:
                if len(decision.message.encode("utf-8")) > self.config.max_message_bytes:
                    raise ValueError("Message exceeds the world's byte budget")
        c = self.config
        energy = {key: 0.0 for key in decisions}
        events: list[dict[str, Any]] = []
        for key in sorted(decisions):
            decision = decisions[key]
            if decision.action == "move":
                x, y = self.positions[key]
                self.positions[key] = (
                    (x + decision.parameters["dx"]) % c.width,
                    (y + decision.parameters["dy"]) % c.height,
                )
                energy[key] -= c.movement_cost

        harvesters: dict[tuple[int, int], list[str]] = {}
        for key in sorted(decisions):
            if decisions[key].action == "harvest":
                harvesters.setdefault(self.positions[key], []).append(key)
        for (x, y), competitors in sorted(harvesters.items()):
            rng.shuffle(competitors)
            for key in competitors:
                if self.food[y][x] > 0:
                    self.food[y][x] -= 1
                    energy[key] += c.food_energy
                    events.append({"event": "harvest", "agent_id": key, "x": x, "y": y})

        self.inboxes = {key: [] for key in decisions}
        for sender in sorted(decisions):
            message = decisions[sender].message
            if message is None:
                continue
            energy[sender] -= c.message_cost
            recipients = []
            for recipient in sorted(decisions):
                if sender == recipient:
                    continue
                dx, dy = self._offset(recipient, sender)
                if max(abs(dx), abs(dy)) <= c.message_radius:
                    self.inboxes[recipient].append({
                        "sender": sender, "text": message, "dx": dx, "dy": dy,
                    })
                    recipients.append(recipient)
            events.append({
                "event": "message", "sender": sender, "text": message, "recipients": recipients,
                "bytes": len(message.encode("utf-8")),
            })
        for row in self.food:
            for x in range(c.width):
                if rng.random() < c.regrowth_probability and row[x] < c.food_capacity:
                    row[x] += 1
        return Outcome(energy, events)

    def can_mate(self, first: str, second: str) -> bool:
        return first != second and self.positions[first] == self.positions[second]

    def on_birth(self, child: str, parents: tuple[str, ...], rng: random.Random) -> None:
        if child in self.positions or not parents or any(p not in self.positions for p in parents):
            raise ValueError("Invalid birth placement")
        self.positions[child] = self.positions[parents[0]]
        self.inboxes[child] = []

    def on_death(self, agent_id: str) -> None:
        del self.positions[agent_id]
        del self.inboxes[agent_id]

    def snapshot(self) -> dict[str, Any]:
        return {
            "food": [list(row) for row in self.food],
            "positions": {key: list(position) for key, position in self.positions.items()},
            "inboxes": {key: [dict(message) for message in inbox]
                        for key, inbox in self.inboxes.items()},
        }

    def restore(self, state: dict[str, Any], agent_ids: list[str]) -> None:
        c = self.config
        food = state["food"]
        if len(food) != c.height or any(len(row) != c.width for row in food):
            raise ValueError("Checkpoint grid dimensions differ")
        if any(type(v) is not int or not 0 <= v <= c.food_capacity for row in food for v in row):
            raise ValueError("Invalid resource amount")
        if set(state["positions"]) != set(agent_ids) or set(state["inboxes"]) != set(agent_ids):
            raise ValueError("Checkpoint world population differs")
        for position in state["positions"].values():
            if len(position) != 2 or any(type(v) is not int for v in position):
                raise ValueError("Invalid position")
            if not (0 <= position[0] < c.width and 0 <= position[1] < c.height):
                raise ValueError("Position outside world")
        # Detach all state from caller-owned mutable objects.
        self.food = [list(row) for row in food]
        self.positions = {key: tuple(value) for key, value in state["positions"].items()}
        self.inboxes = {key: [dict(message) for message in value]
                        for key, value in state["inboxes"].items()}
