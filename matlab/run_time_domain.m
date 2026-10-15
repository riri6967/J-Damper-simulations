%RUN_TIME_DOMAIN Nonlinear quarter-car simulation of the J-damper layout (L4).
%   Compares, on an ISO 8608 road:
%     1) L1 conventional spring || damper (optimised)
%     2) L4 with an ideal inerter
%     3) L4 with the nonlinear fluid inerter (curved-channel and minor losses from
%        INERTER_FORCE, with the inertance taken from the L4 optimisation)
%   Run RUN_QUARTER_CAR_STUDY first; it writes layout_opt.mat.
%
%   L4 branch: spring k2, damper c2 and inerter in series. Internal coordinates:
%     x1 = inerter stroke, x2 = damper stroke, branch spring deflection xk = x - x1 - x2
%     branch force Fb = k2*xk = c2*x2' = b*x1'' + F_loss(x1')
%   So the states are explicit and no mass matrix is needed:
%     y = [zs zu zs' zu' x1 x1' x2]
%   Once you have the CFD ROM, replace lossFn with the fitted c1*xd + c2*xd|xd|.

clear; close all; clc;
p = inerter_params();
assert(isfile('layout_opt.mat'), 'Run run_quarter_car_study.m first.');
S = load('layout_opt.mat');
xL1 = S.L(1).x_ideal;          % c
xid = S.L(4).x_ideal;          % [c1 b c2 k2]
xfl = S.L(4).x_real;

T = 10;
[t_r, zr] = iso8608_road(p, T, 'time');
zr_fun = griddedInterpolant(t_r, zr);

q = p;  q.b = xfl(2);          % fluid inerter: scale the channel so its inertance matches
q.l = q.b * q.A_c / (q.rho * q.A_p^2);

sims = {
  'L1 conventional',  @(t,y) rhsL1(t, y, p, xL1, zr_fun),                         zeros(4,1)
  'L4 ideal inerter', @(t,y) rhsL4(t, y, p, xid, @(v) 0*v, zr_fun),               zeros(7,1)
  'L4 fluid inerter', @(t,y) rhsL4(t, y, p, xfl, @(v) lossOnly(v, q), zr_fun),    zeros(7,1) };

Fstatic = (p.ms + p.mu_u) * p.g;
opts = odeset('RelTol', 1e-6, 'AbsTol', 1e-9, 'MaxStep', 1e-3);
tu = linspace(1, T, 20000)';                       % uniform grid; skip the first second
figure('Name','Time domain'); tiledlayout(2,1);
for k = 1:size(sims, 1)
    [t, y] = ode45(sims{k,2}, [0 T], sims{k,3}, opts);
    Ft = interp1(t, p.kt*(zr_fun(t) - y(:,2)), tu);
    st = interp1(t, y(:,1) - y(:,2), tu);
    fprintf('%-18s J_grip = %.4f   travel RMS = %.2f mm   lift-off = %.2f %%\n', sims{k,1}, ...
        sqrt(mean(Ft.^2))/Fstatic, 1e3*sqrt(mean(st.^2)), 100*mean(Fstatic + Ft < 0));
    nexttile(1); hold on; plot(tu, Ft/1e3, 'DisplayName', sims{k,1});
    nexttile(2); hold on; plot(tu, 1e3*st, 'DisplayName', sims{k,1});
    if size(y, 2) == 7
        fprintf('%18s inerter stroke RMS = %.2f mm, velocity RMS = %.3f m/s\n', '', ...
            1e3*sqrt(mean(interp1(t, y(:,5), tu).^2)), sqrt(mean(interp1(t, y(:,6), tu).^2)));
    end
end
nexttile(1); grid on; ylabel('Dynamic tyre force [kN]'); legend show;
title(sprintf('ISO 8608 class A, V = %.0f km/h', p.V*3.6));
nexttile(2); grid on; ylabel('Suspension travel [mm]'); xlabel('Time [s]');
fprintf(['\nCheck: the inerter velocity RMS should be close to xd_rep used in parasitic_ratio.m.\n', ...
         'If it is not, update xd_rep and rerun the frequency study.\n']);

function dy = rhsL1(t, y, p, x, zr_fun)
F = p.ks*(y(1)-y(2)) + x(1)*(y(3)-y(4));
dy = [y(3); y(4); -F/p.ms; (F - p.kt*(y(2) - zr_fun(t)))/p.mu_u];
end

function dy = rhsL4(t, y, p, x, lossFn, zr_fun)
c1 = x(1); b = x(2); c2 = x(3); k2 = x(4);
xs = y(1) - y(2);  vs = y(3) - y(4);
Fb = k2*(xs - y(5) - y(7));                        % branch force
F  = p.ks*xs + c1*vs + Fb;
dy = [ y(3); y(4);
      -F/p.ms;
      (F - p.kt*(y(2) - zr_fun(t)))/p.mu_u;
       y(6);
      (Fb - lossFn(y(6)))/b;                       % inerter: b*x1'' = Fb - F_loss
       Fb/c2 ];                                    % damper: c2*x2' = Fb
end

function F = lossOnly(xd, p)
[~, ~, F] = inerter_force(0, xd, p);
end
