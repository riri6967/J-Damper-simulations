"""Self-test of inerter_model.fit_rom on synthetic data with known parameters
(port of matlab/test_fit_rom.m). Run before trusting the fit on real CFD output.

Usage: python test_fit_rom.py      (exit code 1 on failure)
"""
import sys

import numpy as np

import inerter_model as im

b_true, c1_true, c2_true, X = 90.0, 3000.0, 800.0, 5e-3
rng = np.random.default_rng(0)
ok = True
print(f'{"f[Hz]":>6} {"b":>8} {"c1":>8} {"c2":>8} {"b_eq":>8} {"nrmse":>8}')
for freq in (1, 5, 10, 20):
    w = 2 * np.pi * freq
    t = np.linspace(0, 4 / freq, 4 * 400)
    xd, xdd = X * w * np.cos(w * t), -X * w ** 2 * np.sin(w * t)
    F = b_true * xdd + c1_true * xd + c2_true * xd * np.abs(xd)
    F = F + 0.01 * F.std() * rng.standard_normal(F.size)
    r = im.fit_rom(t, F, X, freq)
    print(f'{freq:6.0f} {r["b"]:8.1f} {r["c1"]:8.0f} {r["c2"]:8.0f} {r["b_eq"]:8.1f} {r["nrmse"]:8.4f}')
    ok &= abs(r['b'] - b_true) / b_true < 0.02
print('\nPASS: inertance recovered within 2% at all frequencies.' if ok else '\nFAIL')
print('(c1 and c2 are only weakly separable from a single amplitude: fit them jointly across amplitudes.)')
sys.exit(0 if ok else 1)
