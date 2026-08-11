---
name: matlab-learning-module-builder
description: Implement one approved P## Robotics and Autonomy learning batch while preserving its curriculum identity and evidence boundary.
---

# MATLAB Learning Module Builder

Read the approved active batch, `curriculum/modules.json`, the module README, and its prerequisite
lesson. Work only inside allowed paths. Build a deterministic `model.m`, sectioned `experiment.m`,
`interactive.m`, tutor text, two independent parameter sweeps, a deliberately broken case, and
`run_checks.m`. Keep equations visible, prefer base MATLAB, label axes and units, and avoid opaque
toolbox shortcuts. Change the manifest to `implemented` only after focused and repository-wide
checks pass. Retain exact evidence and never imply MATLAB, bench, HIL, or field execution that did
not occur.
