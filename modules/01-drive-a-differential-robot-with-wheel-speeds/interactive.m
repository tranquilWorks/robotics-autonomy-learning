function interactive
fig=uifigure('Name','P01 Differential Drive','Position',[100 100 1120 720]);
g=uigridlayout(fig,[3 5]); g.RowHeight={'1x','1x',100};
axPath=uiaxes(g); axPath.Layout.Row=[1 2]; axPath.Layout.Column=[1 3];
axHead=uiaxes(g); axHead.Layout.Row=1; axHead.Layout.Column=[4 5];
summary=uilabel(g,'WordWrap','on'); summary.Layout.Row=2; summary.Layout.Column=[4 5];

l=uislider(g,'Limits',[-15 15],'Value',6,'MajorTicks',[-15 -10 -5 0 5 10 15]);
l.Layout.Row=3; l.Layout.Column=1;
r=uislider(g,'Limits',[-15 15],'Value',9,'MajorTicks',[-15 -10 -5 0 5 10 15]);
r.Layout.Row=3; r.Layout.Column=2;
wr=uislider(g,'Limits',[0.02 0.25],'Value',0.08); wr.Layout.Row=3; wr.Layout.Column=3;
tw=uislider(g,'Limits',[0.15 1.0],'Value',0.35); tw.Layout.Row=3; tw.Layout.Column=4;
dur=uislider(g,'Limits',[1 20],'Value',8); dur.Layout.Row=3; dur.Layout.Column=5;
controls=[l r wr tw dur];
for i=1:numel(controls)
    controls(i).ValueChangingFcn=@(~,~) updatePlots();
    controls(i).ValueChangedFcn=@(~,~) updatePlots();
end
updatePlots();

    function updatePlots
        out=model(l.Value,r.Value,wr.Value,tw.Value,dur.Value);
        cla(axPath); plot(axPath,out.x,out.y,'LineWidth',1.4); hold(axPath,'on');
        plot(axPath,out.leftX,out.leftY,'--'); plot(axPath,out.rightX,out.rightY,'--');
        hold(axPath,'off'); axis(axPath,'equal'); grid(axPath,'on');
        xlabel(axPath,'x (m)'); ylabel(axPath,'y (m)'); title(axPath,'Robot and wheel paths');

        cla(axHead); plot(axHead,out.t,rad2deg(out.theta),'LineWidth',1.2);
        grid(axHead,'on'); xlabel(axHead,'Time (s)'); ylabel(axHead,'Heading (deg)');
        title(axHead,'Heading');

        summary.Text=sprintf(['left %.2f rad/s\nright %.2f rad/s\nv %.3f m/s\n' ...
            'omega %.3f rad/s\nfinal pose [%.2f, %.2f, %.1f deg]'], ...
            l.Value,r.Value,out.v,out.omega,out.x(end),out.y(end),rad2deg(out.theta(end)));
    end
end
