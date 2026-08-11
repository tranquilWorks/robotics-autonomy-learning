# Repository instructions — Robotics and Autonomy

## Product purpose

This repository is the **Robotics and Autonomy** interactive MATLAB learning system, not a collection of disconnected demos. Teach concepts through controlled experiments, notebook-style sections, plots, parameter levers, deliberately broken cases, and concise dialogue.

## User command routing

- `start`: run `./bin/learn start`, then enter tutor mode.
- `start P##` or `teach P##`: select that module.
- `continue`: resume the current module.
- `status`: summarize learner progress and implementation frontier.
- `complete P##`: first run checks and request a short teach-back.
- `implement next`: enter governed build mode for exactly one scaffolded module.

## Tutor rules

- Ask at most one prediction before showing a baseline.
- Present one plot or processing transition at a time.
- Tie every control to physical or computational meaning.
- Correct misunderstandings directly.
- Use equations to explain observed behavior, not as an entrance exam.
- Never implement a scaffolded module during tutor mode.
- Keep learner progress under ignored `.learning/`.

## Build rules

- Preserve the canonical module order and guiding questions.
- Prefer base MATLAB and deterministic seeded data.
- Separate model, presentation, validation, and tutor text.
- Include two parameter sweeps and one broken case.
- Do not claim MATLAB runtime, bench, field, or production evidence unless actually obtained.
- Run `python scripts/verify.py` before declaring completion.

<!-- BEGIN PORTFOLIO-CONTROL MANAGED -->
## Governed agentic delivery

- Product: `robotics-autonomy-learning`; delivery profile: `product-data`.
- Control revision: `c30242144225e1d438079ea1310025f92d7709aa`; harness version: `2`.
- Read `contracts/profile-requirements.yaml` and the approved
  `contracts/active-batch.yaml` before implementation.
- Stay inside active-batch allowed paths and preserve every forbidden path.
- Run the repository-local verification contract before claiming completion.
- Record exact evidence and distinguish static, simulated, protocol, bench,
  field, playtest, staging, and production validation.
- Do not claim physical, release, deployment, or production evidence that was
  not actually produced.
<!-- END PORTFOLIO-CONTROL MANAGED -->
