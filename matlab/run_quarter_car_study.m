%RUN_QUARTER_CAR_STUDY Grip benefit of inerter suspension layouts, ideal vs fluid inerter.
%   For each layout, the element values are optimised (fminsearch on log-parameters,
%   several starting points) to minimise the dynamic tyre-load ratio
%       J_grip = RMS(F_tyre,dyn) / static wheel load
%   on an ISO 8608 road. The main spring ks is fixed (ride height / aero platform).
%   A fluid inerter is modelled as b*s + c_par with c_par = (c_par/b)*b, see PARASITIC_RATIO.
%
%   Layouts (Q = admittance, k/s spring, c damper, b*s inerter):
%     L1  k || c                        conventional
%     L2  k || c || b                   parallel inerter
%     L3  k || (c ser b)                damper-inerter series
%     L4  k || c1 || (k2 ser c2 ser b)  J-damper style series branch
%
%   Saves optimised parameters to layout_opt.mat for RUN_TIME_DOMAIN.

clear; close all; clc;
p  = inerter_params();
f  = linspace(0.2, 50, 3000)';
s  = 1i*2*pi*f;
Gd = iso8608_road(p, f, 'psd');
Fstatic = (p.ms + p.mu_u) * p.g;
Jfun = @(Q) sqrt(trapz(f, abs(getfield(quarter_car_freq(f, p, Q), 'Ft')).^2 .* Gd)) / Fstatic;
ser  = @(a, b) 1 ./ (1./a + 1./b);
inr  = @(b, cpb) b.*s + cpb.*b;                 % fluid inerter admittance

L(1).name = 'L1: k || c';                        L(1).x0 = 3000;
L(1).Q = @(x, cpb) p.ks./s + x(1);               L(1).pn = {'c'};
L(2).name = 'L2: k || c || b';                   L(2).x0 = [3000 50];
L(2).Q = @(x, cpb) p.ks./s + x(1) + inr(x(2), cpb);  L(2).pn = {'c','b'};
L(3).name = 'L3: k || (c ser b)';                L(3).x0 = [3000 300];
L(3).Q = @(x, cpb) p.ks./s + ser(x(1), inr(x(2), cpb));  L(3).pn = {'c','b'};
L(4).name = 'L4: k || c1 || (k2 ser c2 ser b)';  L(4).x0 = [300 300 3500 5e5];
L(4).Q = @(x, cpb) p.ks./s + x(1) + ser(ser(x(4)./s, x(3)), inr(x(2), cpb));
L(4).pn = {'c1','b','c2','k2'};

cpb6 = parasitic_ratio(p, p.d);
fprintf('Fluid inerter, d = %.0f mm: c_par/b = %.1f 1/s\n\n', p.d*1e3, cpb6);

opts = optimset('MaxIter', 4000, 'MaxFunEvals', 8000, 'TolX', 1e-6, 'TolFun', 1e-10, 'Display', 'off');
optimise = @(lay, cpb) multistart(@(lx) Jfun(lay.Q(exp(lx), cpb)), log(lay.x0), opts);

for k = 1:numel(L)
    [L(k).x_ideal, L(k).J_ideal] = optimise(L(k), 0);
    [L(k).x_real,  L(k).J_real ] = optimise(L(k), cpb6);
end
J0 = L(1).J_ideal;
fprintf('%-36s %9s %9s %10s %10s\n', 'Layout', 'J ideal', 'J fluid', 'gain id.', 'gain fl.');
for k = 1:numel(L)
    fprintf('%-36s %9.4f %9.4f %9.1f%% %9.1f%%\n', L(k).name, L(k).J_ideal, L(k).J_real, ...
        100*(J0-L(k).J_ideal)/J0, 100*(J0-L(k).J_real)/J0);
end
printParams('Optimised L4 (ideal)', L(4).pn, L(4).x_ideal);
printParams('Optimised L4 (fluid)', L(4).pn, L(4).x_real);

%% Design chart: L4 grip gain vs channel diameter
d_list = (3:1:12) * 1e-3;
gain_d = zeros(size(d_list));
for i = 1:numel(d_list)
    [~, Jd] = optimise(L(4), parasitic_ratio(p, d_list(i)));
    gain_d(i) = 100*(J0 - Jd)/J0;
end

save('layout_opt.mat', 'L', 'cpb6', 'J0');

%% Plots
figure('Name','Layout comparison');
bar(categorical({L.name}, {L.name}), 100*(J0 - [[L.J_ideal]' [L.J_real]'])/J0);
ylabel('Reduction in dynamic tyre load [%]'); grid on;
legend('Ideal inerter', sprintf('Fluid inerter (d = %.0f mm)', p.d*1e3), 'Location', 'northwest');
title(sprintf('Grip benefit vs conventional, ISO 8608 class A, V = %.0f km/h', p.V*3.6));

figure('Name','Diameter design chart');
plot(d_list*1e3, gain_d, 'o-', 'LineWidth', 1.5); hold on;
yline(100*(J0 - L(4).J_ideal)/J0, 'k--', 'Ideal inerter limit');
grid on; xlabel('Channel diameter d [mm]'); ylabel('Reduction in dynamic tyre load [%]');
title('L4 (J-damper branch): effect of fluid losses');

figure('Name','Tyre-force FRF');
H1 = quarter_car_freq(f, p, L(1).Q(L(1).x_ideal, 0));
H4i = quarter_car_freq(f, p, L(4).Q(L(4).x_ideal, 0));
H4r = quarter_car_freq(f, p, L(4).Q(L(4).x_real, cpb6));
semilogx(f, 20*log10(abs([H1.Ft H4i.Ft H4r.Ft])), 'LineWidth', 1.5);
grid on; xlabel('Frequency [Hz]'); ylabel('|F_t / z_r| [dB re 1 N/m]');
legend('L1 conventional', 'L4 ideal inerter', 'L4 fluid inerter', 'Location', 'best');
title('Dynamic tyre force response');

function [x, J] = multistart(fun, lx0, opts)
J = inf;
for sc = log([0.3 1 3])
    [lx, Jk] = fminsearch(fun, lx0 + sc, opts);
    if Jk < J, J = Jk; x = exp(lx); end
end
end

function printParams(label, names, x)
fprintf('%s:', label);
for i = 1:numel(x), fprintf('  %s = %.4g', names{i}, x(i)); end
fprintf('\n');
end
