# Earlier ECI checkpoint recovery

The previous research archive is named
`eci-research-checkpoint-2026-11-15.zip`. It remains the source for earlier
implementation and pilot artifacts. It has not been unpacked or audited in this
repository initialization session, which has connector access but no executor.

This repository's new source is independently authored platform infrastructure.
It is not a recovered copy of that archive. Previous conversation summaries are
not substitute evidence for experimental results.

When file execution is available:

1. Retrieve the original archive and record its SHA-256 before extraction.
2. Inspect the member list for absolute paths, parent traversal, symlinks,
   credentials, personal information, and unexpectedly large files.
3. Extract to a separate recovery directory. Do not overwrite Kosmos source.
4. Read the archive's STATE, manifests, dependency files, licenses, and tests.
5. Inventory implementation and results with their recorded code/model/task
   versions. Re-run the archive's original tests before refactoring anything.
6. Port useful components through a reviewed change; retain provenance and
   distinguish imported historical data from newly reproduced results.
7. Keep large outputs outside ordinary Git and publish suitable reproducibility
   metadata or release artifacts after inspecting their content.

Do not upload the opaque ZIP to Git merely to claim migration is complete.
