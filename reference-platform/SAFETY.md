# Safety and authorization boundary

RP01 validates data only. Its code reads bounded regular JSON files and writes fixtures only when the operator explicitly runs the deterministic generator with an output directory. Each generated file is replaced atomically, and pre-existing symbolic-link output roots, parents, and file targets are rejected before writing so those paths cannot redirect a write outside the selected tree. It has no CAN, serial or USB-device, GPIO, camera, vacuum, motor, credential, or network-service integration.

Every complete fixture contains a `run_authorization` record so omission cannot silently bypass a gate. RP01 fixtures set:

- `authorization_status` to `withheld`;
- `physical_run_authorized` and `local_presence_confirmed` to `false`;
- guard state to `not_evaluated`;
- e-stop result to `not_run`;
- maximum energy class to `none`.

The validator rejects an absent authorization record, a conflicting configuration identity, an execution request outside `contract_only`, a current/duration/state limit beyond the configuration envelope, and any static fixture that claims a physical lifecycle or evidence level.

## Future physical authority

A later, separately approved hardware program must provide an independent power-removing e-stop, local watchdog, current and temperature limits, configuration-specific travel/state limits, guarding and hard stops, exact as-built inventory and calibration, and a locally present human authorization for every physical run. The local supervisor—not Tranquility or this learning repository—must own immediate abort and hard-real-time safety behavior.

No RP01 test validates those physical mechanisms. The contract fields record their future evidence; they are not substitutes for it.
