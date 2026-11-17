# Author a world

See [the runnable example](../examples/custom_world.py). Its recharge environment
has a different observation/action space and a different genome schema from the
habitat. It deliberately uses an external energy source and is a technical fixture.

## Contracts

Implement the World and Policy protocols in `kosmos.interfaces`.

| Method | Requirement |
| --- | --- |
| config_dict | JSON configuration sufficient to construct this world |
| reset | Initialize environmental state for the supplied founder IDs |
| observe | Return only information available to this agent |
| step | Resolve all actors together; return one finite energy delta per actor |
| can_mate | Define pair compatibility; the engine checks maturity and energy |
| on_birth | Place the child without copying undeclared parental state |
| on_death | Remove environmental state belonging to the dead agent |
| snapshot | Return all environmental state needed for exact continuation |
| restore | Validate and restore that state, checking live population identity |

A Policy has a stable `policy_id` and a stateless `decide(observation, genome, rng)`.
It returns a Decision with a world-specific action, JSON parameters, an optional
message, and a reproduction request. Messages are a world responsibility; a
world can omit communication entirely.

The engine supplies age and energy as reserved observation fields. World code
must not use those keys for a different meaning. World effects return energy
deltas; they do not directly edit the agent population.

## Register without changing the engine

```python
register_world(MyWorld.world_id, MyWorld, MY_SCHEMA)
register_policy(MyPolicy.policy_id, MyPolicy)

# Registration is process-local. This launcher must register the same plugins
# for both run and resume before delegating to the CLI.
main()
```

Use stable, versioned identifiers. JSON configuration selects only registered
identifiers; a checkpoint cannot specify a module to import or arbitrary code
to execute. Installing or running a plugin is still executing its Python code;
the interfaces are organizational boundaries, not a security sandbox.

For checkpoints, define plugins in real source files. The defining modules are
fingerprinted. Record versions/digests of any additional assets and dependencies
your plugin uses; Kosmos does not automatically discover those.

## Verification checklist

- Test simultaneous-action ordering and contention without duplicating resources.
- Test that observations exclude hidden global state.
- Verify resource creation and consumption with independent accounting.
- Reject malformed actions before mutating the environment.
- Snapshot every environmental RNG or transient message state you introduce.
- Compare uninterrupted and resumed trajectories, including births and deaths.
- Use initially comparable agents when studying specialization.
- Separate genetic inheritance, social information, and lifetime learning.

External simulator, PettingZoo, model-server, and Unity adapters are future
integrations. They are not implemented by the current registry.
