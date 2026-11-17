# Contributing

Use Python 3.11 or 3.12 for the initial supported validation matrix.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Keep the reference core small and dependency-free. Add worlds or policies through
the extension contracts. Include invariant and checkpoint-continuation tests
for stateful behavior, and document any new source of randomness.

Use a new versioned identifier when changing world semantics, genome meaning,
or policy behavior. Source/runtime changes intentionally prevent silent resume;
a compatible migration must be explicit and tested.

Research contributions should include hypotheses, controls, seed-level raw
measurements, code/config/model provenance, and limitations. An interesting
animation is not evidence of collective intelligence.

Do not commit credentials, personal information, local environment files, or
large run logs. The existing MIT license covers contributions accepted here.
