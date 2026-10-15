"""First-look analysis of the fluid inerter design (port of matlab/analyse_inerter.m).

Prints the key parameters, flow regime and cavitation risk over the CFD case matrix,
and saves friction-factor, loss-force and force-loop plots to python/results/.
Usage: python analyse_inerter.py
"""
import math
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import inerter_model as im

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
os.makedirs(OUT, exist_ok=True)
p = im.params()
_, _, Re_crit = im.friction_factor_helical(1, p.delta)

print('=== Fluid inerter: baseline design ===')
print(f'Channel length l             : {p.l:.3f} m')
print(f'Area ratio A_p/A_c           : {p.A_p / p.A_c:.1f}')
print(f'Ideal inertance b            : {p.b:.1f} kg')
print(f'Oil mass in channel          : {p.rho * p.A_c * p.l:.4f} kg')
print(f'Laminar damping c_lin        : {p.c_lin:.0f} N s/m (straight pipe)')
print(f'Curvature ratio r/R          : {p.delta:.3f}')
print(f'Critical Re (curved, Schmidt): {Re_crit:.0f}\n')

freq = [1, 2, 5, 10, 20, 1, 2, 5, 10, 15]
X = [x * 1e-3 for x in (5, 5, 5, 5, 2, 2, 2, 2, 2, 2)]
print(f'{"f[Hz]":>5} {"X[mm]":>6} {"xd[m/s]":>9} {"v[m/s]":>9} {"Re":>8} {"De":>8} {"Wo":>6} '
      f'{"dp_b[MPa]":>10} {"dp_l[MPa]":>10}')
for fk, Xk in zip(freq, X):
    w = 2 * math.pi * fk
    xd, xdd = Xk * w, Xk * w ** 2
    v = p.A_p / p.A_c * xd
    Re = p.rho * v * p.d / p.mu
    dpl = float(im.inerter_force(0.0, xd, p)[3])
    print(f'{fk:5.0f} {Xk * 1e3:6.1f} {xd:9.3f} {v:9.2f} {Re:8.0f} {Re * math.sqrt(p.delta):8.0f} '
          f'{p.d / 2 * math.sqrt(w * p.rho / p.mu):6.2f} {p.b * xdd / p.A_p / 1e6:10.2f} {dpl / 1e6:10.2f}')
print('\nRequired charge pressure is roughly max(dp_b + dp_l)/2 + p_vap.'
      '\nAny case with Re > Re_crit should use a turbulence model in the CFD.')

# friction factor vs Re
Re = np.logspace(2, math.log10(2e4), 300)
fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.loglog(Re, 64 / Re, 'k--', label='Straight pipe 64/Re')
ax.loglog(Re, im.friction_factor_helical(Re, p.delta, 'ito')[0], 'b-', label='Curved: Ito (1959)')
ax.loglog(Re, im.friction_factor_helical(Re, p.delta, 'white')[0], 'r:', label='Curved: White (1929)')
ax.axvline(Re_crit, color='g', ls='-.', label='Re$_{crit}$')
ax.set(xlabel='Re', ylabel='Darcy friction factor $f_D$', title=f'Helical channel, r/R = {p.delta:.3f}')
ax.grid(True, which='both', alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'friction_factor.png'), dpi=200)

# parasitic loss force vs velocity
xd = np.linspace(-0.6, 0.6, 400)
F_loss = im.inerter_force(0.0, xd, p)[2]
fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.plot(xd, F_loss / 1e3, 'b', label='Nonlinear (curved + minor losses)')
ax.plot(xd, p.c_lin * xd / 1e3, 'k--', label='Linear straight-pipe $c_{lin}$')
ax.set(xlabel='Relative velocity [m/s]', ylabel='Loss force [kN]', title='Parasitic damping of the fluid inerter')
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'parasitic_loss_force.png'), dpi=200)

# force-displacement loops
fig, ax = plt.subplots(figsize=(6.5, 4.5))
tau = np.linspace(0, 1, 500)
for fk in (1, 5, 10, 20):
    w = 2 * math.pi * fk
    x, xdv, xddv = 5e-3 * np.sin(2 * np.pi * tau), 5e-3 * w * np.cos(2 * np.pi * tau), -5e-3 * w ** 2 * np.sin(2 * np.pi * tau)
    ax.plot(x * 1e3, im.inerter_force(xddv, xdv, p)[0] / 1e3, label=f'{fk} Hz')
ax.set(xlabel='Displacement [mm]', ylabel='Force [kN]',
       title='Quasi-steady model: force-displacement loops (X = 5 mm)')
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'force_loops.png'), dpi=200)
print(f'\nPlots saved to {OUT}')
