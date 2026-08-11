%% P01 - Drive a Differential Robot with Wheel Speeds
% Guiding question:
% How do left and right wheel speeds determine a differential-drive robot's path?
%
% Mental model:
% A differential-drive robot moves by combining two wheel velocities. Their average creates forward motion; their difference creates rotation.

%% Read the baseline lesson
disp('How do left and right wheel speeds determine a differential-drive robot''s path?');
disp('A differential-drive robot moves by combining two wheel velocities. Their average creates forward motion; their difference creates rotation.');

%% Run the deterministic experiment
experiment;

%% Open the live lever panel
% Move one control at a time and connect the visible change to the model.
interactive;
