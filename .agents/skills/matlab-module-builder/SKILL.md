# MATLAB module builder skill

Use this skill only for an activated module implementation batch.

The module must include:

- `model.m`: deterministic computation with explicit units and validation.
- `experiment.m`: baseline, at least two independent parameter sweeps, and one deliberately broken case.
- `interactive.m`: a `uifigure` with meaningful levers and immediate plots.
- `lesson.m`: MATLAB `%%` notebook cells that launch the experiment and interactive view.
- `lesson.md`: physical mental model, equations after intuition, misconceptions.
- `walkthrough.md`: ordered observations and tutor prompts.
- `checks.md` plus `run_checks.m`: conceptual and deterministic numerical checks.

Prefer base MATLAB. Seed randomness. Do not hide the core operation behind a toolbox. Distinguish simulation from bench, field, or production evidence. Run `python scripts/verify.py` before claiming completion.
