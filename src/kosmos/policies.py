"""Deterministic-with-seed reference policies; these are not LLM agents."""

from __future__ import annotations

import random
from typing import Any

from kosmos.genetics import Genome, HABITAT_SCHEMA
from kosmos.interfaces import Decision


class Forager:
    policy_id = "kosmos.forager.v1"

    def decide(
        self, observation: dict[str, Any], genome: Genome, rng: random.Random,
    ) -> Decision:
        traits = HABITAT_SCHEMA.decode(genome)
        own_cell = next(c for c in observation["cells"] if c["dx"] == c["dy"] == 0)
        reproduce = observation["energy"] >= traits["reproduction_threshold"]
        if own_cell["food"] > 0:
            message = "food" if (
                own_cell["food"] > 1 and rng.random() < traits["signal_probability"]
            ) else None
            return Decision("harvest", reproduce=reproduce, message=message)
        directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        dx, dy = rng.choice(directions)
        if rng.random() >= traits["exploration"]:
            targets = [c for c in observation["cells"] if c["food"] > 0]
            if targets:
                # Randomize equal choices to avoid a fixed directional preference.
                rng.shuffle(targets)
                target = max(targets, key=lambda c: c["food"])
                dx, dy = self._toward(target["dx"], target["dy"], rng)
            else:
                messages = [m for m in observation["messages"] if m["text"] == "food"]
                if messages:
                    message = rng.choice(messages)
                    dx, dy = self._toward(message["dx"], message["dy"], rng)
        if dx == dy == 0:
            return Decision("wait", reproduce=reproduce)
        return Decision("move", {"dx": dx, "dy": dy}, reproduce=reproduce)

    @staticmethod
    def _toward(dx: int, dy: int, rng: random.Random) -> tuple[int, int]:
        directions = []
        if dx:
            directions.append((1 if dx > 0 else -1, 0))
        if dy:
            directions.append((0, 1 if dy > 0 else -1))
        return rng.choice(directions) if directions else (0, 0)
