# Reconfigurable reference-platform contracts

Status: **proposal — software contract only**. RP01 establishes deterministic, target-owned data contracts. It does not authorize procurement, fabrication, device access, energization, motion, or a physical run, and it does not demonstrate a robot or safe state.

`robotics-autonomy-learning` owns configuration identity, geometry-facing contract fields, canonical fixture serialization, and the local validation implementation. Portfolio Control owns product intent and batch scope. Future dynamics and controller work belongs in `controls-gnc-learning`; future bounded orchestration belongs in `tranquility-te`. Those consumers require separate governed changes and a pinned approved contract revision.

## Contract baseline

The v1 family defines eight strict JSON contracts:

1. configuration;
2. hardware inventory;
3. plant model;
4. experiment request;
5. run authorization;
6. telemetry/event record;
7. result;
8. evidence.

The schemas and version index are in [`../contracts/reference-platform/`](../contracts/reference-platform/README.md). Each complete fixture binds all eight documents with the same configuration identity and canonical hash.

| Fixture | Contract identity | Boundary |
| --- | --- | --- |
| `drawbot_2r` | two active joints, horizontal, pen | proposal only |
| `rotary_pendulum_1` | one active and one passive joint, vertical | proposal only |
| `pendubot_2link` | one active and one passive joint, vertical | proposal only |
| `passive_multilink` | one active and two passive joints | gated by `G4_MULTILINK` |
| `pnp_single_head` | two active joints, horizontal, proposed Z/theta/vacuum head | gated by `G5_PNP_FEASIBILITY`; unreleased |

All retained RP01 inventories are synthetic `planned_fixture` identities, all authorization decisions explicitly withhold physical authorization, and all evidence is `static`. Nominal parameters are assumptions, not measurements.

## Deterministic use

Run the offline validator from the repository root:

```bash
python3 reference-platform/validate.py check-all
python3 reference-platform/validate.py validate reference-platform/fixtures/valid/drawbot-2r.json
python3 reference-platform/validate.py hash reference-platform/fixtures/valid/drawbot-2r.json
```

The validator is standard-library-only, bounded, read-only, and transport-free. `ral-json-c14n-v1` emits UTF-8 JSON with Unicode-code-point key order, preserved array order, NFC strings, no insignificant whitespace, deterministic finite-number spelling, and no trailing newline in hashed bytes. JSON strings escape quotation marks and reverse solidus, use the short `\b`, `\t`, `\n`, `\f`, and `\r` escapes, encode other U+0000–U+001F controls as lowercase `\u00xx`, leave solidus unescaped, and emit every other Unicode scalar directly as UTF-8. Negative zero and integral floats below `1e21` render as integers; other floats use lowercase shortest Python 3.12 representation with an integer exponent. A configuration digest is SHA-256 over the configuration after removing only `configuration_hash`. Golden values are retained in [`fixtures/canonical-hashes.json`](fixtures/canonical-hashes.json).

[`generate_fixtures.py`](generate_fixtures.py) reproduces fixtures in an explicitly chosen local directory. Each generated file is replaced atomically, and the generator fails closed if the output root, a generated parent directory, or a generated file is a symbolic link. It neither discovers nor contacts devices or services.

## Safety and compatibility

- [Safety and authorization boundary](SAFETY.md)
- [Compatibility and rollback](COMPATIBILITY.md)
- [Cross-repository handoffs](CROSS_REPOSITORY_HANDOFF.md)
- [Canonicalization decision](ADR-0001-CONTRACT-BASELINE.md)

Static schema and fixture success cannot satisfy simulation, MATLAB-runtime, protocol replay, low-energy bench, guarded motion, controls experiment, PnP validation, HIL, field, external-alpha, production, or release evidence.
