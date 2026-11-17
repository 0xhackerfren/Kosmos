"""Run and resume bounded local experiments without model services or API spend."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import time
from typing import Any

from kosmos.artifacts import canonical, provenance, read_checkpoint, write_checkpoint, write_json
from kosmos.engine import Engine, EngineConfig
from kosmos.policies import Forager
from kosmos.registry import make_policy, world_spec
from kosmos.worlds.habitat import Habitat


def _new_engine(config_path: Path | None, seed: int | None) -> Engine:
    data = json.loads(config_path.read_text(encoding="utf-8")) if config_path else {}
    if set(data) - {"engine", "world", "policy"}:
        raise ValueError("Unknown top-level experiment configuration key")
    config = EngineConfig(**data.get("engine", {}))
    if seed is not None:
        config = replace(config, seed=seed)
    world_data = data.get("world", {"id": Habitat.world_id, "config": {}})
    if set(world_data) - {"id", "config"}:
        raise ValueError("Unknown world configuration key")
    world_id = world_data["id"]
    spec = world_spec(world_id)
    world = spec.factory(**world_data.get("config", {}))
    policy = make_policy(data.get("policy", Forager.policy_id))
    return Engine(config, spec.schema, world, policy)


def _resume_engine(path: Path) -> tuple[Engine, str]:
    state, digest = read_checkpoint(path)
    spec = world_spec(state["world_id"])
    if spec.schema.to_dict() != state["schema"]:
        raise ValueError("Registered genome schema differs from the checkpoint")
    world = spec.factory(**state["world_config"])
    policy = make_policy(state["policy_id"])
    return Engine.restore(state, world, policy), digest


def _execute(
    engine: Engine, output: Path, steps: int, checkpoint_every: int, parent_digest: str | None,
) -> dict[str, Any]:
    if steps < 0 or checkpoint_every < 1:
        raise ValueError("Steps must be nonnegative and checkpoint interval positive")
    # Never overwrite an earlier run, even if it failed.
    output.mkdir(parents=True, exist_ok=False)
    started_tick = engine.tick
    started_at = time.monotonic()
    manifest = {
        "format_version": 1, "provenance": provenance(),
        "engine": asdict(engine.config), "schema": engine.schema.to_dict(),
        "world_id": engine.world.world_id, "world_config": engine.world.config_dict(),
        "policy_id": engine.policy.policy_id, "start_tick": started_tick,
        "requested_steps": steps, "checkpoint_every": checkpoint_every,
        "parent_checkpoint_sha256": parent_digest,
        "controller_type": "scripted", "model_calls": 0,
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "status.json", {"status": "running", "tick": engine.tick})
    write_checkpoint(output / "checkpoint.json", engine.snapshot())
    sequence = 0
    try:
        with (output / "events.jsonl").open("x", encoding="utf-8") as log:
            initial = {
                "type": "start", "tick": engine.tick, "metrics": engine.metrics(),
                "agents": [a.to_dict() for a in engine.agents.values()],
                "world": engine.world.snapshot(),
            }
            log.write(canonical(dict(initial, sequence=sequence)) + "\n")
            sequence += 1
            log.flush()
            for index in range(steps):
                if not engine.agents:
                    break
                for event in engine.step():
                    log.write(canonical(dict(event, sequence=sequence)) + "\n")
                    sequence += 1
                log.flush()
                if (index + 1) % checkpoint_every == 0:
                    write_checkpoint(output / "checkpoint.json", engine.snapshot())
        write_checkpoint(output / "checkpoint.json", engine.snapshot())
        summary = {
            "status": "complete", **engine.metrics(),
            "steps_completed": engine.tick - started_tick,
            "extinct": not bool(engine.agents), "elapsed_seconds": time.monotonic() - started_at,
        }
        write_json(output / "summary.json", summary)
        write_json(output / "status.json", {"status": "complete", "tick": engine.tick})
        return summary
    except Exception as error:
        # Keep the last complete checkpoint. A failed partially applied step is
        # never serialized as a valid continuation point.
        write_json(output / "status.json", {
            "status": "failed", "error_type": type(error).__name__, "message": str(error),
            "last_complete_checkpoint": "checkpoint.json",
        })
        raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kosmos evolutionary world runner")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Start a new experiment")
    run.add_argument("--config", type=Path)
    run.add_argument("--seed", type=int)
    resume = commands.add_parser("resume", help="Continue a verified checkpoint into a new run")
    resume.add_argument("checkpoint", type=Path)
    for command in (run, resume):
        command.add_argument("--steps", type=int, default=200)
        command.add_argument("--checkpoint-every", type=int, default=25)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.steps < 0 or args.checkpoint_every < 1:
        parser.error("Steps must be nonnegative and checkpoint interval positive")
    try:
        if args.command == "run":
            engine, parent = _new_engine(args.config, args.seed), None
        else:
            engine, parent = _resume_engine(args.checkpoint)
        summary = _execute(engine, args.output, args.steps, args.checkpoint_every, parent)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"kosmos: {error}\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
