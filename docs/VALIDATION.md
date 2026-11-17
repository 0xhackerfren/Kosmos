# Foundation validation record

Implementation commit: `8f0fe62451a5b61001b11759d75f0fd0961c4582`.

Workflow: [tests, run 43993859477](https://github.com/0xhackerfren/Kosmos/actions/runs/43993859477).

| Check | Python 3.11 | Python 3.12 |
| --- | --- | --- |
| Editable package installation | Passed | Passed |
| 26 invariant/integration tests | Passed | Passed |
| Source/test compilation | Passed | Passed |
| Habitat: 30 ticks | Passed | Passed |
| Habitat: 10-tick continuation | Passed | Passed |
| Custom world: 20 ticks | Passed | Passed |
| Custom world: 5-tick continuation | Passed | Passed |

The test suite compares an uninterrupted reference trajectory with a serialized
and restored trajectory, including observations, actions, births/deaths, world
frames, and final RNG/state snapshots. A subprocess integration test independently
compares CLI run/resume with a straight run and verifies refusal to overwrite.

The habitat smoke run reported 60 births, 8 deaths, and 64 surviving agents at
tick 30; its continuation reached tick 40. These counts verify that lifecycle
events occur in an end-to-end example. They are not a replicated experiment,
an evolutionary advantage measurement, or evidence of emergent intelligence.

The custom example reached tick 20 with 13 agents, then tick 25 with 16 agents.
This verifies a second registered world/schema/policy through the same runner.

Small floating-point summary differences occur between Python 3.11 and 3.12.
No cross-version numerical identity is claimed; checkpoint resume explicitly
requires the same Python version.

No earlier ECI archive was unpacked and no historical pilot was reproduced.
No LLM inference, Unity build, year-long soak test, or paid service was executed.
