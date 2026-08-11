function out = model(leftRadPerSec,rightRadPerSec,wheelRadius,trackWidth,duration)
%MODEL Differential-drive kinematics.
arguments
    leftRadPerSec (1,1) double = 6
    rightRadPerSec (1,1) double = 9
    wheelRadius (1,1) double {mustBePositive} = 0.08
    trackWidth (1,1) double {mustBePositive} = 0.35
    duration (1,1) double {mustBePositive} = 8
end
vL=wheelRadius*leftRadPerSec;
vR=wheelRadius*rightRadPerSec;
v=0.5*(vL+vR);
omega=(vR-vL)/trackWidth;
t=linspace(0,duration,500);
if abs(omega)<1e-10
    theta=zeros(size(t));
    x=v*t; y=zeros(size(t));
else
    theta=omega*t;
    R=v/omega;
    x=R*sin(theta);
    y=R*(1-cos(theta));
end
leftX=x-0.5*trackWidth*sin(theta);
leftY=y+0.5*trackWidth*cos(theta);
rightX=x+0.5*trackWidth*sin(theta);
rightY=y-0.5*trackWidth*cos(theta);
out=struct('t',t,'x',x,'y',y,'theta',theta,'leftX',leftX,'leftY',leftY, ...
    'rightX',rightX,'rightY',rightY,'v',v,'omega',omega,'vL',vL,'vR',vR);
end
