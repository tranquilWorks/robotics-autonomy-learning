# Future cross-repository handoffs

These are handoff records, not authorization to edit another repository.

## Controls and estimation

After RP01 is human-reviewed and an approved target revision is pinned, create a separate governed intake for `controls-gnc-learning`. That repository owns nonlinear dynamics, system identification, state estimation, and PID, pole-placement, LQR, energy-shaping, nonlinear, and MPC studies. It should consume the configuration, inventory, plant, experiment, result, and evidence identities plus the five golden fixtures at an exact producer revision. It must begin with deterministic simulation/replay and must not claim hardware identity, local authorization, or physical acceptance.

## Tranquility orchestration

After the target contract and controls model are separately approved, create a separate governed intake for `tranquility-te`. It should begin with a disabled-by-default, transport-free fake/replay adapter. It owns bounded job and artifact lifecycle behavior, including cancellation, timeout, restart, partial-artifact, and abort records. It must consume an exact schema and fixture revision and cannot bypass the local human authorization record, own the hard-real-time current loop, or act as the sole e-stop.

## Required compatibility record

Each handoff must name producer and consumer repositories, exact baselines and revisions, schema versions, exchanged fixture hashes, upgrade and rollback policies, retained validation level, and required human approvals. Adoption in one repository cannot be inferred from tests in another.

`TRANQUILITY NOT CONTACTED` and `CONTROLS-GNC NOT MODIFIED` remain true for RP01.
