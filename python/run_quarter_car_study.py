"""Grip benefit of inerter suspension layouts, ideal vs fluid inerter
(port of matlab/run_quarter_car_study.m).

For each layout L1-L4 the element values are optimised (Nelder-Mead on log-parameters,
3 starting points) to minimise J_grip = RMS dynamic tyre load / static load on an
ISO 8608 road. The main spring ks is fixed. A fluid inerter is b*s + c_par with
c_par = (c_par/b)*b (see inerter_model.parasitic_ratio).
Also produces the L4 design chart: grip gain vs channel diameter.
Saves python/results/layout_opt.json for run_time_domain.py.

Usage: python run_quarter_car_study.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import minimize

import inerter_model as im

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT, exist_ok=True)
p = im.params()
f = np.linspace(0.2, 50, 3000)


def optimise(layout, cpb):
    _, _, x0, Q = layout
    obj = lambda lx: im.grip_metric(p, lambda s: Q(s, np.exp(lx), cpb, p), f)
    best = None
    for scale in (0.3, 1.0, 3.0):
        r = minimize(obj, np.log(np.array(x0) * scale), method='Nelder-Mead',
                     options=dict(maxiter=4000, maxfev=8000, xatol=1e-6, fatol=1e-10))
        if best is None or r.fun < best.fun:
            best = r
    return np.exp(best.x), best.fun


cpb6 = im.parasitic_ratio(p)
print(f'Fluid inerter, d = {p.d * 1e3:.0f} mm: c_par/b = {cpb6:.1f} 1/s\n')

res = []
for lay in im.LAYOUTS:
    xi, Ji = optimise(lay, 0.0)
    xr, Jr = optimise(lay, cpb6)
    res.append(dict(name=lay[0], pn=lay[1], x_ideal=xi.tolist(), J_ideal=Ji, x_real=xr.tolist(), J_real=Jr))
J0 = res[0]['J_ideal']
print(f'{"Layout":<36} {"J ideal":>9} {"J fluid":>9} {"gain id.":>9} {"gain fl.":>9}')
for r in res:
    print(f'{r["name"]:<36} {r["J_ideal"]:9.4f} {r["J_real"]:9.4f} '
          f'{100 * (J0 - r["J_ideal"]) / J0:8.1f}% {100 * (J0 - r["J_real"]) / J0:8.1f}%')
for tag in ('ideal', 'real'):
    vals = '  '.join(f'{n} = {v:.4g}' for n, v in zip(res[3]['pn'], res[3][f'x_{tag}']))
    print(f'Optimised L4 ({"fluid" if tag == "real" else tag}): {vals}')

# design chart: L4 gain vs channel diameter
d_list = np.arange(3, 13) * 1e-3
gain_d = []
for d in d_list:
    _, Jd = optimise(im.LAYOUTS[3], im.parasitic_ratio(p, d))
    gain_d.append(100 * (J0 - Jd) / J0)
print('\nL4 design chart (fluid inerter):')
for d, g in zip(d_list, gain_d):
    l_needed = res[3]['x_real'][1] * (np.pi * d ** 2 / 4) / (p.rho * p.A_p ** 2)
    print(f'  d = {d * 1e3:4.0f} mm: grip gain {g:5.1f}%   (channel length for b = {res[3]["x_real"][1]:.0f} kg: {l_needed:5.2f} m)')

with open(os.path.join(OUT, 'layout_opt.json'), 'w') as fh:
    json.dump(dict(layouts=res, cpb6=cpb6, J0=J0, d_list=d_list.tolist(), gain_d=gain_d), fh, indent=2)

# plots
fig, ax = plt.subplots(figsize=(8, 4.5))
xpos = np.arange(len(res))
ax.bar(xpos - 0.2, [100 * (J0 - r['J_ideal']) / J0 for r in res], 0.4, label='Ideal inerter')
ax.bar(xpos + 0.2, [100 * (J0 - r['J_real']) / J0 for r in res], 0.4, label=f'Fluid inerter (d = {p.d * 1e3:.0f} mm)')
ax.set_xticks(xpos, [r['name'] for r in res], fontsize=8)
ax.set(ylabel='Reduction in dynamic tyre load [%]',
       title=f'Grip benefit vs conventional, ISO 8608 class A, V = {p.V * 3.6:.0f} km/h')
ax.grid(True, axis='y', alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'layout_comparison.png'), dpi=200)

fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.plot(d_list * 1e3, gain_d, 'o-')
ax.axhline(100 * (J0 - res[3]['J_ideal']) / J0, color='k', ls='--', label='Ideal inerter limit')
ax.set(xlabel='Channel diameter d [mm]', ylabel='Reduction in dynamic tyre load [%]',
       title='L4 (J-damper branch): effect of fluid losses')
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'diameter_design_chart.png'), dpi=200)

fig, ax = plt.subplots(figsize=(6.5, 4.5))
s = 1j * 2 * np.pi * f
for lab, lay, x, cpb in (('L1 conventional', im.LAYOUTS[0], res[0]['x_ideal'], 0.0),
                         ('L4 ideal inerter', im.LAYOUTS[3], res[3]['x_ideal'], 0.0),
                         ('L4 fluid inerter', im.LAYOUTS[3], res[3]['x_real'], cpb6)):
    H = im.quarter_car_freq(f, p, lay[3](s, np.array(x), cpb, p))
    ax.semilogx(f, 20 * np.log10(np.abs(H['Ft'])), label=lab)
ax.set(xlabel='Frequency [Hz]', ylabel='|F$_t$ / z$_r$| [dB re 1 N/m]', title='Dynamic tyre force response')
ax.grid(True, which='both', alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'tyre_force_frf.png'), dpi=200)
print(f'\nPlots and layout_opt.json saved to {OUT}')
