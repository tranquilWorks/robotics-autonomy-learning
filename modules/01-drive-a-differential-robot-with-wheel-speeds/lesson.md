# Lesson: Drive a Differential Robot with Wheel Speeds

## Guiding question

How do left and right wheel speeds determine a differential-drive robot's path?

## Mental model

A differential-drive robot moves by combining two wheel velocities. Their average creates forward motion; their difference creates rotation.

## What to manipulate

Use `interactive.m`. Change one lever at a time before combining effects.

## First observation

Set both wheels equal for a straight line, stop one wheel for an arc, and reverse one wheel for an in-place turn. Change track width and watch the same wheel-speed difference create a different turn rate.

## Common mistakes

- Wheel speeds do not independently map to x and y motion.
- A commanded wheel speed is not the same as achieved speed when actuators saturate or slip.
- Odometry integrates small errors, so long-term pose can drift badly.

## Completion standard

The learner can explain the baseline, identify what each lever changes, diagnose the deliberately broken case, and pass `run_checks.m`.
