function rom = fit_rom_from_cfd(src, X, freq, p, makePlot)
%FIT_ROM_FROM_CFD Fit inerter reduced-order models to transient CFD output.
%   rom = FIT_ROM_FROM_CFD(csvFile, X, freq)      reads a Fluent export
%   rom = FIT_ROM_FROM_CFD(tbl, X, freq)          uses a table directly
%   The input needs columns t [s] and either F [N] or dp [Pa] (total channel
%   pressure drop, already scaled to the full channel length; F = A_p*dp).
%   X    : piston displacement amplitude [m]
%   freq : excitation frequency [Hz]; motion assumed x = X sin(2*pi*freq*t)
%
%   Only the final full cycle is used (periodic steady state).
%   Outputs:
%     rom.b_eq, rom.c_eq   first-harmonic equivalent inertance [kg] and damping [N s/m]
%     rom.b, rom.c1, rom.c2  time-domain fit F = b xdd + c1 xd + c2 xd|xd|
%     rom.nrmse            normalised RMS error of the time-domain fit

if nargin < 4 || isempty(p), p = inerter_params(); end
if nargin < 5, makePlot = true; end
if ischar(src) || isstring(src), tbl = readtable(src); else, tbl = src; end

t = tbl.t(:);
if ismember('F', tbl.Properties.VariableNames)
    F = tbl.F(:);
else
    F = p.A_p * tbl.dp(:);
end

% Last full cycle
Tp = 1/freq;
m  = t >= t(end) - Tp;
t = t(m);  F = F(m);

w   = 2*pi*freq;
x   =  X*sin(w*t);
xd  =  X*w*cos(w*t);
xdd = -X*w^2*sin(w*t);

% First-harmonic: F ~ a*sin + c*cos + offset. Then b_eq = -a/(X w^2) and c_eq = c/(X w)
Ah = [sin(w*t), cos(w*t), ones(size(t))];
h  = Ah \ F;
rom.b_eq = -h(1)/(X*w^2);
rom.c_eq =  h(2)/(X*w);

% Time-domain ROM
A = [xdd, xd, xd.*abs(xd)];
theta = A \ F;
rom.b = theta(1);  rom.c1 = theta(2);  rom.c2 = theta(3);
Ffit = A*theta;
rom.nrmse = sqrt(mean((F - Ffit).^2)) / (max(F) - min(F));
rom.freq = freq;  rom.X = X;

if makePlot
    figure('Name', sprintf('ROM fit %.1f Hz', freq));
    plot(x*1e3, F/1e3, 'k.', x*1e3, Ffit/1e3, 'r-', 'LineWidth', 1.2);
    grid on; xlabel('Displacement [mm]'); ylabel('Force [kN]');
    legend('CFD', 'ROM fit', 'Location', 'best');
    title(sprintf('f = %.1f Hz, X = %.1f mm: b_{eq} = %.1f kg, c_{eq} = %.0f N s/m', ...
        freq, X*1e3, rom.b_eq, rom.c_eq));
end
end
