"""A different world, genome schema, and policy using only public extension contracts.

Run:
  python examples/custom_world.py run --config examples/custom_world.json --steps 20 --output runs/custom
"""
from __future__ import annotations

import math

from kosmos.cli import main
from kosmos.genetics import Gene, GenomeSchema
from kosmos.interfaces import Decision, Outcome
from kosmos.registry import register_policy, register_world


SCHEMA = GenomeSchema("examples.battery.numeric.v1", (Gene("birth_threshold", 8.0, 16.0),))


class BatteryWorld:
    """A technical fixture with an external energy supply, not a scientific habitat."""
    world_id = "examples.battery.v1"

    def __init__(self, recharge=1.0):
        if isinstance(recharge, bool) or not math.isfinite(recharge) or recharge < 0:
            raise ValueError("Recharge must be finite and nonnegative")
        self.recharge = recharge
        self.ids = []

    def config_dict(self):
        return {"recharge": self.recharge}

    def reset(self, agent_ids, rng):
        self.ids = list(agent_ids)

    def observe(self, agent_id):
        return {"recharge": self.recharge}

    def step(self, decisions, rng):
        if set(decisions) != set(self.ids) or any(d.action != "rest" for d in decisions.values()):
            raise ValueError("Invalid battery-world action batch")
        return Outcome({key: self.recharge for key in self.ids})

    def can_mate(self, first, second):
        return first != second

    def on_birth(self, child, parents, rng):
        self.ids.append(child)

    def on_death(self, agent_id):
        self.ids.remove(agent_id)

    def snapshot(self):
        return {"ids": list(self.ids)}

    def restore(self, state, agent_ids):
        if set(state["ids"]) != set(agent_ids):
            raise ValueError("World population mismatch")
        self.ids = list(state["ids"])


class BatteryPolicy:
    policy_id = "examples.battery-policy.v1"

    def decide(self, observation, genome, rng):
        SCHEMA.validate(genome)
        return Decision("rest", reproduce=observation["energy"] >= genome.values[0])


register_world(BatteryWorld.world_id, BatteryWorld, SCHEMA)
register_policy(BatteryPolicy.policy_id, BatteryPolicy)

if __name__ == "__main__":
    main()
