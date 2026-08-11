# Curriculum readiness audit

**Track:** Robotics and Autonomy

## Baseline conclusion

The repository has 24 uniquely identified modules in a six-phase, prerequisite-ordered sequence. P01 is the complete reference slice; P02-P24 are explicit non-runnable batch scaffolds. The learner flow is read → visualize → move one lever → visualize the delta → read/explain, followed by a broken case, checks, and teach-back.

Static structure and CLI behavior are verified in CI. MATLAB was not available during the 2026-08-11 baseline audit, so numerical execution, UI behavior, and instructional efficacy remain named validation gaps rather than implied evidence.

## Coverage and compounding order

### Phase 1: Kinematics

- **P01 — Drive a Differential Robot with Wheel Speeds:** How do left and right wheel speeds determine a differential-drive robot's path?
- **P02 — Transform Coordinates Between Frames:** What inputs, observable effects, and failure modes matter when you transform Coordinates Between Frames?
- **P03 — Compute Arm Forward Kinematics:** What inputs, observable effects, and failure modes matter when you compute Arm Forward Kinematics?
- **P04 — Solve Inverse Kinematics:** What inputs, observable effects, and failure modes matter when you solve Inverse Kinematics?

### Phase 2: Dynamics and actuation

- **P05 — Model a DC Motor and Geartrain:** What inputs, observable effects, and failure modes matter when you model a DC Motor and Geartrain?
- **P06 — Close a Wheel-Speed Loop:** What inputs, observable effects, and failure modes matter when you close a Wheel-Speed Loop?
- **P07 — Generate a Smooth Trajectory:** What inputs, observable effects, and failure modes matter when you generate a Smooth Trajectory?
- **P08 — Control Contact with Impedance:** What inputs, observable effects, and failure modes matter when you control Contact with Impedance?

### Phase 3: Sensing and calibration

- **P09 — Measure Motion with Encoders:** What inputs, observable effects, and failure modes matter when you measure Motion with Encoders?
- **P10 — Integrate an IMU and Observe Drift:** What inputs, observable effects, and failure modes matter when you integrate an IMU and Observe Drift?
- **P11 — Build a Range Sensor Model:** What inputs, observable effects, and failure modes matter when you build a Range Sensor Model?
- **P12 — Calibrate Sensor Extrinsics:** What inputs, observable effects, and failure modes matter when you calibrate Sensor Extrinsics?

### Phase 4: Localization and mapping

- **P13 — Integrate Wheel Odometry:** What inputs, observable effects, and failure modes matter when you integrate Wheel Odometry?
- **P14 — Fuse Sensors with an EKF:** What inputs, observable effects, and failure modes matter when you fuse Sensors with an EKF?
- **P15 — Localize with a Particle Filter:** What inputs, observable effects, and failure modes matter when you localize with a Particle Filter?
- **P16 — Build a Small SLAM Problem:** What inputs, observable effects, and failure modes matter when you build a Small SLAM Problem?

### Phase 5: Planning and behavior

- **P17 — Search a Grid with A-Star:** What inputs, observable effects, and failure modes matter when you search a Grid with A-Star?
- **P18 — Plan with Random Samples:** What inputs, observable effects, and failure modes matter when you plan with Random Samples?
- **P19 — Avoid Moving Obstacles:** What inputs, observable effects, and failure modes matter when you avoid Moving Obstacles?
- **P20 — Coordinate Actions with a Behavior Tree:** What inputs, observable effects, and failure modes matter when you coordinate Actions with a Behavior Tree?

### Phase 6: Autonomous system integration

- **P21 — Execute a Mission State Machine:** What inputs, observable effects, and failure modes matter when you execute a Mission State Machine?
- **P22 — Meet Real-Time Perception and Control Deadlines:** What inputs, observable effects, and failure modes matter when you meet Real-Time Perception and Control Deadlines?
- **P23 — Design Safety Monitors:** What inputs, observable effects, and failure modes matter when you design Safety Monitors?
- **P24 — Validate Autonomy in HIL:** What inputs, observable effects, and failure modes matter when you validate Autonomy in HIL?

## Batch readiness gates

A scaffold may become `implemented` only when it has a deterministic model, a sectioned experiment, two independent parameter sweeps, one deliberately broken case, interactive controls, interpretation-focused tutor text, numerical checks, focused static tests, and evidence that says exactly what did and did not run.
