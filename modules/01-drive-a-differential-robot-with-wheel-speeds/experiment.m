%% P01 - Drive a Differential Robot with Wheel Speeds
close all; clc;
out=model(6,9,0.08,0.35,8);

figure('Name','P01 baseline');
subplot(1,2,1);
plot(out.x,out.y,'LineWidth',1.4,'DisplayName','Robot center'); hold on;
plot(out.leftX,out.leftY,'--','DisplayName','Left wheel');
plot(out.rightX,out.rightY,'--','DisplayName','Right wheel');
axis equal; grid on; xlabel('x (m)'); ylabel('y (m)');
title('Wheel-speed difference bends the path'); legend('Location','best');
subplot(1,2,2);
plot(out.t,rad2deg(out.theta),'LineWidth',1.3);
grid on; xlabel('Time (s)'); ylabel('Heading (deg)'); title('Heading accumulation');

%% Sweep 1 - wheel-speed patterns
patterns=[6 6; 0 8; -6 6; 6 9];
figure('Name','P01 motion primitives'); hold on; grid on; axis equal;
for i=1:size(patterns,1)
    s=model(patterns(i,1),patterns(i,2),0.08,0.35,5);
    plot(s.x,s.y,'LineWidth',1.2,'DisplayName', ...
        sprintf('[%.0f, %.0f] rad/s',patterns(i,1),patterns(i,2)));
end
xlabel('x (m)'); ylabel('y (m)'); title('Straight, pivot, spin, and arc');
legend('Location','best');

%% Sweep 2 - track width
widths=[0.2 0.35 0.7];
fprintf('Track-width sweep:\n');
for i=1:numel(widths)
    s=model(6,9,0.08,widths(i),8);
    fprintf('  width %.2f m -> omega %.3f rad/s\n',widths(i),s.omega);
end

%% Broken case - integrate heading but pretend y stays zero
brokenX=out.v*out.t;
brokenY=zeros(size(out.t));
figure('Name','P01 broken case');
plot(out.x,out.y,'LineWidth',1.3,'DisplayName','Correct coupled kinematics'); hold on;
plot(brokenX,brokenY,'--','LineWidth',1.2,'DisplayName','Broken decoupled model');
axis equal; grid on; xlabel('x (m)'); ylabel('y (m)');
title('Broken: rotation changes the direction of translation'); legend('Location','best');

assert(abs(out.omega-(out.vR-out.vL)/0.35)<eps,'Turn-rate identity failed.');
