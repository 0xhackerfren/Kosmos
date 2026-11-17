"""Behavioral invariants and independent resume/CLI integration checks."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from kosmos.artifacts import canonical, read_checkpoint, write_checkpoint
from kosmos.engine import Engine, EngineConfig
from kosmos.genetics import Gene, Genome, GenomeSchema, HABITAT_SCHEMA
from kosmos.interfaces import Decision, Outcome
from kosmos.policies import Forager
from kosmos.worlds.habitat import Habitat


class EmptyWorld:
    """A second world proves lifecycle code does not depend on Habitat."""
    world_id = "test.empty.v1"

    def config_dict(self):
        return {}

    def reset(self, agent_ids, rng):
        self.ids = list(agent_ids)
        self.observation = {"visible": True}

    def observe(self, agent_id):
        return self.observation

    def step(self, decisions, rng):
        if set(decisions) != set(self.ids):
            raise ValueError("Population mismatch")
        return Outcome({key: 0.0 for key in self.ids})

    def can_mate(self, first, second):
        return first != second

    def on_birth(self, child, parents, rng):
        self.ids.append(child)

    def on_death(self, agent_id):
        self.ids.remove(agent_id)

    def snapshot(self):
        return {"ids": list(self.ids), "observation": dict(self.observation)}

    def restore(self, state, agent_ids):
        if set(state["ids"]) != set(agent_ids):
            raise ValueError("Population mismatch")
        self.ids = list(state["ids"])
        self.observation = dict(state["observation"])


class Breeder:
    policy_id = "test.breeder.v1"

    def decide(self, observation, genome, rng):
        return Decision("wait", reproduce=True)


def empty_engine(**overrides):
    parameters = dict(
        population=2, max_population=32, initial_energy=10,
        metabolism=0, max_age=100, maturity_age=0,
        offspring_energy=4, birth_overhead=2, mutation_rate=0,
    )
    parameters.update(overrides)
    return Engine(EngineConfig(**parameters), HABITAT_SCHEMA, EmptyWorld(), Breeder())


class GeneticsTests(unittest.TestCase):
    def test_schema_rejects_invalid_alleles(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                GenomeSchema("test", (Gene("x", 0, 1),)).validate(Genome("test", (value,)))

    def test_schema_rejects_duplicate_loci_and_wrong_identity(self):
        with self.assertRaises(ValueError):
            GenomeSchema("test", (Gene("x", 0, 1), Gene("x", 0, 2)))
        with self.assertRaises(ValueError):
            HABITAT_SCHEMA.validate(Genome("wrong", (0, 0, 10)))

    def test_clone_without_mutation_is_exact(self):
        parent = HABITAT_SCHEMA.sample(random.Random(3))
        child, record = HABITAT_SCHEMA.reproduce((parent,), random.Random(5), 0, 0.1)
        self.assertEqual(child, parent)
        self.assertEqual(record["mutations"], [])

    def test_recombination_matches_recorded_parent_at_every_locus(self):
        schema = GenomeSchema("test", tuple(Gene(f"g{i}", 0, 1) for i in range(16)))
        parents = (Genome("test", (0.0,) * 16), Genome("test", (1.0,) * 16))
        child, record = schema.reproduce(parents, random.Random(7), 0, 0.1)
        self.assertEqual(set(record["locus_sources"]), {0, 1})
        for index, source in enumerate(record["locus_sources"]):
            self.assertEqual(child.values[index], parents[source].values[index])

    def test_extreme_mutations_stay_in_bounds_and_are_recorded(self):
        parent = HABITAT_SCHEMA.sample(random.Random(1))
        child, record = HABITAT_SCHEMA.reproduce((parent,), random.Random(9), 1, 100)
        HABITAT_SCHEMA.validate(child)
        self.assertEqual(len(record["mutations"]), len(HABITAT_SCHEMA.genes))
        self.assertNotEqual(child, parent)

    def test_invalid_mutation_settings_fail(self):
        parent = HABITAT_SCHEMA.sample(random.Random(0))
        for rate, scale in ((-1, 0.1), (2, 0.1), (0.1, -1), (float("nan"), 0.1)):
            with self.subTest(rate=rate, scale=scale), self.assertRaises(ValueError):
                HABITAT_SCHEMA.reproduce((parent,), random.Random(0), rate, scale)


class LifecycleTests(unittest.TestCase):
    def test_clonal_births_have_parents_and_pay_energy_cost(self):
        engine = empty_engine()
        events = engine.step()
        births = [e for e in events if e["type"] == "birth"]
        self.assertEqual(len(births), 2)
        self.assertAlmostEqual(sum(a.energy for a in engine.agents.values()), 16)
        for event in births:
            child = engine.agents[event["child"]["agent_id"]]
            self.assertEqual(len(child.parents), 1)
            self.assertEqual(child.genome, engine.agents[child.parents[0]].genome)
            self.assertEqual(child.generation, 1)

    def test_two_parent_birth_conserves_energy_minus_overhead(self):
        engine = empty_engine(reproduction="recombine")
        events = engine.step()
        births = [e for e in events if e["type"] == "birth"]
        self.assertEqual(len(births), 1)
        self.assertEqual(len(births[0]["child"]["parents"]), 2)
        self.assertAlmostEqual(engine.metrics()["total_energy"], 18)

    def test_unwilling_or_ineligible_partner_cannot_recombine(self):
        engine = empty_engine(population=1, reproduction="recombine")
        engine.step()
        self.assertEqual(engine.births, 0)

    def test_death_precedes_reproduction(self):
        engine = empty_engine(max_age=1)
        events = engine.step()
        self.assertFalse(engine.agents)
        self.assertEqual(engine.births, 0)
        self.assertEqual(len([e for e in events if e["type"] == "death"]), 2)

    def test_population_cap_and_newborn_action_timing(self):
        engine = empty_engine(population=1, max_population=2, initial_energy=100)
        first = engine.step()
        self.assertEqual(len(engine.agents), 2)
        self.assertEqual(len([e for e in first if e["type"] == "decision"]), 1)
        for _ in range(5):
            engine.step()
            self.assertEqual(len(engine.agents), 2)

    def test_disabled_reproduction_has_no_births(self):
        engine = empty_engine(reproduction="disabled")
        for _ in range(5):
            engine.step()
        self.assertEqual(engine.births, 0)

    def test_maturity_blocks_births(self):
        engine = empty_engine(maturity_age=5)
        for _ in range(4):
            engine.step()
        self.assertEqual(engine.births, 0)

    def test_policy_cannot_mutate_world_observation(self):
        class Mutator(Breeder):
            def decide(self, observation, genome, rng):
                observation["visible"] = False
                return Decision("wait")
        engine = empty_engine()
        engine.policy = Mutator()
        engine.step()
        self.assertEqual(engine.world.observation, {"visible": True})

    def test_policy_rng_is_independent_of_genetics_rng(self):
        class RandomPolicy(Breeder):
            def decide(self, observation, genome, rng):
                return Decision("wait", {"sample": rng.random()})
        first, second = empty_engine(), empty_engine()
        first.policy = second.policy = RandomPolicy()
        for _ in range(100):
            second.genetics_rng.random()
        a = [e for e in first.step() if e["type"] == "decision"]
        b = [e for e in second.step() if e["type"] == "decision"]
        self.assertEqual(a, b)

    def test_invalid_configurations_fail(self):
        for values in ({"population": 0}, {"max_population": 1}, {"metabolism": -1},
                       {"mutation_rate": 2}, {"max_age": 0}, {"seed": True}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(EngineConfig(), **values)


class HabitatTests(unittest.TestCase):
    def test_competing_harvesters_cannot_duplicate_food(self):
        world = Habitat(width=3, height=3, regrowth_probability=0)
        world.reset(["a", "b"], random.Random(0))
        world.food = [[0] * 3 for _ in range(3)]
        world.food[0][0] = 1
        world.positions = {"a": (0, 0), "b": (0, 0)}
        outcome = world.step({"a": Decision("harvest"), "b": Decision("harvest")}, random.Random(1))
        self.assertEqual(sum(outcome.energy_delta.values()), 3)
        self.assertEqual(world.food[0][0], 0)

    def test_messages_are_local_and_charged(self):
        world = Habitat(width=7, height=7, message_radius=1, regrowth_probability=0)
        world.reset(["a", "b", "c"], random.Random(0))
        world.positions = {"a": (0, 0), "b": (1, 0), "c": (3, 3)}
        outcome = world.step({
            "a": Decision("wait", message="food"), "b": Decision("wait"), "c": Decision("wait"),
        }, random.Random(1))
        self.assertEqual(len(world.observe("b")["messages"]), 1)
        self.assertEqual(world.observe("c")["messages"], [])
        self.assertAlmostEqual(outcome.energy_delta["a"], -world.config.message_cost)
        self.assertEqual(set(world.observe("b")), {"cells", "messages"})
        self.assertEqual(len(world.observe("b")["cells"]), 9)

    def test_invalid_batch_and_utf8_budget_leave_world_unchanged(self):
        world = Habitat(max_message_bytes=3)
        world.reset(["a"], random.Random(0))
        before = world.snapshot()
        for decision in (Decision("move", {"dx": 2, "dy": 0}),
                         Decision("wait", message="éé")):
            with self.assertRaises(ValueError):
                world.step({"a": decision}, random.Random(1))
            self.assertEqual(world.snapshot(), before)

    def test_seeded_reference_runs_match(self):
        config = EngineConfig(seed=18)
        first = Engine(config, HABITAT_SCHEMA, Habitat(), Forager())
        second = Engine(config, HABITAT_SCHEMA, Habitat(), Forager())
        for _ in range(20):
            self.assertEqual(first.step(), second.step())
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_gene_mapping_changes_reproduction_intent(self):
        policy = Forager()
        obs = {"energy": 10, "cells": [{"dx": 0, "dy": 0, "food": 1}], "messages": []}
        low = policy.decide(obs, Genome(HABITAT_SCHEMA.schema_id, (0.5, 0.5, 6)), random.Random(1))
        high = policy.decide(obs, Genome(HABITAT_SCHEMA.schema_id, (0.5, 0.5, 24)), random.Random(1))
        self.assertTrue(low.reproduce)
        self.assertFalse(high.reproduce)


class CheckpointTests(unittest.TestCase):
    def test_json_checkpoint_resume_matches_uninterrupted_trajectory(self):
        config = EngineConfig(seed=42, mutation_rate=0.3, reproduction="recombine")
        reference = Engine(config, HABITAT_SCHEMA, Habitat(), Forager())
        for _ in range(12):
            reference.step()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            write_checkpoint(path, reference.snapshot())
            state, _ = read_checkpoint(path)
            resumed = Engine.restore(state, Habitat(), Forager())
            for _ in range(23):
                self.assertEqual(reference.step(), resumed.step())
            self.assertEqual(canonical(reference.snapshot()), canonical(resumed.snapshot()))

    def test_checksum_detects_changed_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            write_checkpoint(path, empty_engine().snapshot())
            data = json.loads(path.read_text())
            data["payload"]["state"]["tick"] += 1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_checkpoint(path)

    def test_source_mismatch_requires_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            write_checkpoint(path, empty_engine().snapshot())
            data = json.loads(path.read_text())
            data["payload"]["source_digest"] = "other"
            data["sha256"] = hashlib.sha256(canonical(data["payload"]).encode()).hexdigest()
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "different Kosmos source"):
                read_checkpoint(path)

    def test_restore_rejects_missing_rng_and_plugin_mismatch(self):
        state = json.loads(canonical(empty_engine().snapshot()))
        state["rng"]["policies"].pop(next(iter(state["rng"]["policies"])))
        with self.assertRaises(ValueError):
            Engine.restore(state, EmptyWorld(), Breeder())
        with self.assertRaises(ValueError):
            Engine.restore(empty_engine().snapshot(), Habitat(), Breeder())

    def test_cli_run_resume_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prefix = [sys.executable, "-m", "kosmos"]
            run = base / "run"
            continued = base / "continued"
            straight = base / "straight"
            commands = [
                prefix + ["run", "--seed", "9", "--steps", "5", "--output", str(run)],
                prefix + ["resume", str(run / "checkpoint.json"), "--steps", "3",
                          "--output", str(continued)],
                prefix + ["run", "--seed", "9", "--steps", "8", "--output", str(straight)],
            ]
            for command in commands:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["status"], "complete")
            resumed, _ = read_checkpoint(continued / "checkpoint.json")
            reference, _ = read_checkpoint(straight / "checkpoint.json")
            self.assertEqual(canonical(resumed), canonical(reference))
            failed = subprocess.run(commands[0], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(failed.returncode, 0)
            events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
            self.assertEqual([e["sequence"] for e in events], list(range(len(events))))
            manifest = json.loads((continued / "manifest.json").read_text())
            self.assertTrue(manifest["parent_checkpoint_sha256"])


if __name__ == "__main__":
    unittest.main()
