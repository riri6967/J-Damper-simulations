%ANALYSE_INERTER First-look analysis of the fluid inerter design.
%   Prints the key parameters and dimensionless groups, checks the flow regime
%   and cavitation risk over the CFD case matrix, and plots force maps.
%   Run this before you build the CFD geometry.

clear; close all; clc;
p = inerter_params();

fprintf('=== Fluid inerter: baseline design ===\n');
fprintf('Channel length l            : %.3f m\n', p.l);
fprintf('Area ratio A_p/A_c          : %.1f\n', p.A_p/p.A_c);
fprintf('Ideal inertance b           : %.1f kg\n', p.b);
fprintf('Oil mass in channel         : %.4f kg\n', p.rho*p.A_c*p.l);
fprintf('Laminar damping c_lin       : %.0f N s/m (straight pipe)\n', p.c_lin);
fprintf('Curvature ratio r/R         : %.3f\n', p.delta);
[~, ~, Re_crit] = friction_factor_helical(1, p.delta);
fprintf('Critical Re (curved, Schmidt): %.0f\n\n', Re_crit);

%% Operating points from the CFD case matrix
freq = [1 2 5 10 20 1 2 5 10 15];
X    = [5 5 5 5 2 2 2 2 2 2] * 1e-3;
fprintf('%5s %6s %9s %9s %8s %8s %6s %10s %10s\n', ...
    'f[Hz]','X[mm]','xd[m/s]','v[m/s]','Re','De','Wo','dp_b[MPa]','dp_l[MPa]');
for k = 1:numel(freq)
    w   = 2*pi*freq(k);
    xd  = X(k)*w;  xdd = X(k)*w^2;
    v   = p.A_p/p.A_c*xd;
    Re  = p.rho*v*p.d/p.mu;
    De  = Re*sqrt(p.delta);
    Wo  = p.d/2*sqrt(w*p.rho/p.mu);
    [~, ~, ~, dpl] = inerter_force(0, xd, p);
    dpb = p.b*xdd/p.A_p;
    fprintf('%5.0f %6.1f %9.3f %9.2f %8.0f %8.0f %6.2f %10.2f %10.2f\n', ...
        freq(k), X(k)*1e3, xd, v, Re, De, Wo, dpb/1e6, dpl/1e6);
end
fprintf(['\nRequired charge pressure is roughly max(dp_b + dp_l)/2 + p_vap.\n', ...
         'Any case with Re > Re_crit should use k-omega SST in Fluent.\n']);

%% Plot 1: friction factor vs Re (overlay this on the steady CFD results)
Re = logspace(2, log10(2e4), 300);
f_ito   = friction_factor_helical(Re, p.delta, 'ito');
f_white = friction_factor_helical(Re, p.delta, 'white');
figure('Name','Friction factor');
loglog(Re, 64./Re, 'k--', Re, f_ito, 'b-', Re, f_white, 'r:', 'LineWidth', 1.5);
xline(Re_crit, 'g-.', 'Re_{crit}');
grid on; xlabel('Re'); ylabel('Darcy friction factor f_D');
legend('Straight pipe 64/Re', 'Curved: Ito (1959)', 'Curved: White (1929)', 'Location', 'southwest');
title(sprintf('Helical channel, r/R = %.3f', p.delta));

%% Plot 2: loss force vs velocity (the parasitic "damper")
xd = linspace(-0.6, 0.6, 400);
[~, ~, F_loss] = inerter_force(0, xd, p);
figure('Name','Parasitic loss force');
plot(xd, F_loss/1e3, 'b', xd, p.c_lin*xd/1e3, 'k--', 'LineWidth', 1.5);
grid on; xlabel('Relative velocity [m/s]'); ylabel('Loss force [kN]');
legend('Nonlinear (curved + minor losses)', 'Linear straight-pipe c_{lin}', 'Location', 'northwest');
title('Parasitic damping of the fluid inerter');

%% Plot 3: force-displacement loops at 5 mm amplitude for several frequencies
figure('Name','Force loops'); hold on;
t = linspace(0, 1, 500);
for f = [1 5 10 20]
    w = 2*pi*f;  x = 5e-3*sin(w*t/f);  xdv = 5e-3*w*cos(w*t/f);  xddv = -5e-3*w^2*sin(w*t/f);
    F = inerter_force(xddv, xdv, p);
    plot(x*1e3, F/1e3, 'LineWidth', 1.3, 'DisplayName', sprintf('%d Hz', f));
end
grid on; xlabel('Displacement [mm]'); ylabel('Force [kN]'); legend show;
title('Quasi-steady model: force-displacement loops (X = 5 mm)');
