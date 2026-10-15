"""Nonlinear time-domain quarter car: L1 conventional vs L4 ideal vs L4 fluid inerter
(port of matlab/run_time_domain.m). Run run_quarter_car_study.py first.

L4 branch: spring k2, damper c2, inerter in series. Internal coordinates
x1 = inerter stroke, x2 = damper stroke; branch force Fb = k2*(x - x1 - x2) = c2*x2'
= b*x1'' + F_loss(x1'). States y = [zs zu zs' zu' x1 x1' x2] (explicit, no mass matrix).
Once the CFD-fitted ROM exists, replace the loss model in loss_fn.

Usage: python run_time_domain.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

import inerter_model as im

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
p = im.params()
opt = json.load(open(os.path.join(OUT, 'layout_opt.json')))
xL1 = opt['layouts'][0]['x_ideal']
xid = opt['layouts'][3]['x_ideal']
xfl = opt['layouts'][3]['x_real']

T = 10.0
t_r, zr = im.iso8608_road(p, T)
zr_fun = lambda t: np.interp(t, t_r, zr)
q = p.with_inertance(xfl[1])          # fluid inerter scaled so its inertance matches the L4 optimum


def rhs_L1(t, y):
    F = p.ks * (y[0] - y[1]) + xL1[0] * (y[2] - y[3])
    return [y[2], y[3], -F / p.ms, (F - p.kt * (y[1] - zr_fun(t))) / p.mu_u]


def make_rhs_L4(x, loss_fn):
    c1, b, c2, k2 = x

    def rhs(t, y):
        xs, vs = y[0] - y[1], y[2] - y[3]
        Fb = k2 * (xs - y[4] - y[6])
        F = p.ks * xs + c1 * vs + Fb
        return [y[2], y[3], -F / p.ms, (F - p.kt * (y[1] - zr_fun(t))) / p.mu_u,
                y[5], (Fb - loss_fn(y[5])) / b, Fb / c2]
    return rhs


sims = [('L1 conventional', rhs_L1, 4),
        ('L4 ideal inerter', make_rhs_L4(xid, lambda v: 0.0), 7),
        ('L4 fluid inerter', make_rhs_L4(xfl, lambda v: float(im.inerter_force(0.0, v, q)[2])), 7)]

Fstatic = (p.ms + p.mu_u) * p.g
tu = np.linspace(1, T, 20000)                # skip the first second (start-up)
fig, axs = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
summary = []
for name, rhs, n in sims:
    sol = solve_ivp(rhs, (0, T), np.zeros(n), method='RK45', rtol=1e-6, atol=1e-9, max_step=1e-3)
    Ft = np.interp(tu, sol.t, p.kt * (zr_fun(sol.t) - sol.y[1]))
    st = np.interp(tu, sol.t, sol.y[0] - sol.y[1])
    J = np.sqrt(np.mean(Ft ** 2)) / Fstatic
    line = (f'{name:<18} J_grip = {J:.4f}   travel RMS = {1e3 * np.sqrt(np.mean(st ** 2)):.2f} mm   '
            f'lift-off = {100 * np.mean(Fstatic + Ft < 0):.2f} %')
    if n == 7:
        line += (f'\n{"":<18} inerter stroke RMS = {1e3 * np.sqrt(np.mean(np.interp(tu, sol.t, sol.y[4]) ** 2)):.2f} mm, '
                 f'velocity RMS = {np.sqrt(np.mean(np.interp(tu, sol.t, sol.y[5]) ** 2)):.3f} m/s')
    print(line)
    summary.append(dict(name=name, J_grip=J))
    axs[0].plot(tu, Ft / 1e3, lw=0.8, label=name)
    axs[1].plot(tu, 1e3 * st, lw=0.8, label=name)
J0 = summary[0]['J_grip']
for s in summary[1:]:
    print(f'{s["name"]}: {100 * (J0 - s["J_grip"]) / J0:.1f}% less dynamic tyre load than L1')
print('\nCheck: the inerter velocity RMS should be close to xd_rep = 0.04 m/s used in parasitic_ratio().')
axs[0].set(ylabel='Dynamic tyre force [kN]', title=f'ISO 8608 class A, V = {p.V * 3.6:.0f} km/h')
axs[1].set(ylabel='Suspension travel [mm]', xlabel='Time [s]')
for a in axs:
    a.grid(True, alpha=0.3)
axs[0].legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'time_domain.png'), dpi=200)
print(f'Plot saved to {OUT}')
