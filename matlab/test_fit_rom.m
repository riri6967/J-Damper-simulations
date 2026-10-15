%TEST_FIT_ROM Self-test of FIT_ROM_FROM_CFD on synthetic data with known parameters.
%   Builds "fake CFD" force histories (b, c1, c2 known, 1% noise, 4 cycles),
%   fits them, and checks that the parameters are recovered. Run this before
%   you trust the fitting routine on real Fluent output.

clear; close all; clc;
p = inerter_params();
b_true = 90; c1_true = 3000; c2_true = 800;
X = 5e-3;
rng(0);
fprintf('%6s %8s %8s %8s %8s %8s\n', 'f[Hz]', 'b', 'c1', 'c2', 'b_eq', 'nrmse');
for freq = [1 5 10 20]
    w = 2*pi*freq;
    t = linspace(0, 4/freq, 4*400)';
    xd = X*w*cos(w*t);  xdd = -X*w^2*sin(w*t);
    F = b_true*xdd + c1_true*xd + c2_true*xd.*abs(xd);
    F = F + 0.01*std(F)*randn(size(F));
    rom = fit_rom_from_cfd(table(t, F), X, freq, p, false);
    fprintf('%6.0f %8.1f %8.0f %8.0f %8.1f %8.4f\n', freq, rom.b, rom.c1, rom.c2, rom.b_eq, rom.nrmse);
    assert(abs(rom.b - b_true)/b_true < 0.02, 'Inertance not recovered at %g Hz', freq);
end
fprintf('\nPASS: inertance recovered within 2%% at all frequencies.\n');
fprintf('(c1 and c2 are only weakly separable from a single amplitude. Fit them jointly across\n');
fprintf(' the 2 mm and 5 mm cases for a robust estimate.)\n');
