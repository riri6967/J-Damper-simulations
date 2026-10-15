"""Post-process S01 (OpenFOAM): friction factor vs Re from the turn-plane pressures.

f_D = (dp/ds) * d / (0.5 * v^2) using OpenFOAM's kinematic pressure (p/rho), with dp
taken between consecutive turn planes (one helix turn, arc length s_turn). The interior
turns (2..N-1) give the fully developed value; all turns are plotted to show development.
Compared with the Ito (1959) and White (1929) curved-pipe correlations.

Usage: python post_s01.py   (reads ../openfoam/s01/re*/postProcessing, writes ../results/)
"""
import glob
import json
import math
import os
import re

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
case_root = os.path.join(here, '..', 'openfoam', 's01')
res_dir = os.path.join(here, '..', 'results')
os.makedirs(res_dir, exist_ok=True)

with open(os.path.join(case_root, 'mesh', 'mesh_info.json')) as fh:
    info = json.load(fh)
D, S_TURN = info['d'], info['s_turn']
DELTA = (D / 2) / info['R_h']
NU = 0.028 / 870.0


AVG_WINDOW = 1000   # iterations averaged when a case did not meet residualControl


def last_value(dat_glob, average=False):
    """(last iteration, value) from an OpenFOAM surfaceFieldValue.dat (any start-time folder).
    average=True: mean over the last AVG_WINDOW iterations (for cases that did not converge)."""
    files = sorted(glob.glob(dat_glob), key=lambda f: float(os.path.basename(os.path.dirname(f))))
    if not files:
        return None, None
    rows = np.array([[float(x) for x in ln.split()[:2]] for ln in open(files[-1])
                     if ln.strip() and not ln.startswith('#')])
    if average:
        sel = rows[:, 0] > rows[-1, 0] - AVG_WINDOW
        return int(rows[-1, 0]), float(rows[sel, 1].mean())
    return int(rows[-1, 0]), float(rows[-1, 1])


def converged(case):
    log = os.path.join(case, 'log.simpleFoam')
    return os.path.exists(log) and 'converged in' in open(log).read()


def ratio_ito(De):
    De = np.atleast_1d(De).astype(float)
    r = np.ones_like(De)
    m = De > 13.5
    r[m] = 21.5 * De[m] / (1.56 + np.log10(De[m])) ** 5.73
    return np.maximum(r, 1)


def ratio_white(De):
    De = np.atleast_1d(De).astype(float)
    r = np.ones_like(De)
    m = De > 11.6
    r[m] = 1 / (1 - (1 - (11.6 / De[m]) ** 0.45) ** (1 / 0.45))
    return np.maximum(r, 1)


rows, per_turn = [], {}
for case in sorted(glob.glob(os.path.join(case_root, 're*'))):
    Re = int(re.search(r're(\d+)$', case).group(1))
    v = Re * NU / D
    p = []
    for i in range(info['turns'] + 1):
        it, val = last_value(os.path.join(case, 'postProcessing', f'pTurn{i}', '*', 'surfaceFieldValue.dat'),
                             average=not converged(case))
        if val is None:
            break
        p.append(val)
    if len(p) < 2:
        print(f'skip {os.path.basename(case)}: no turn-plane data (not run yet?)')
        continue
    _, flux = last_value(os.path.join(case, 'postProcessing', 'outletFlux', '*', 'surfaceFieldValue.dat'),
                         average=not converged(case))
    if not converged(case):
        print(f'note: {os.path.basename(case)} did not converge; values averaged over the last {AVG_WINDOW} iterations')
    fD = [(p[i] - p[i + 1]) / S_TURN * D / (0.5 * v ** 2) for i in range(len(p) - 1)]
    per_turn[Re] = fD
    De = Re * math.sqrt(DELTA)
    q_err = 100 * (flux / (v * info['inlet_area']) - 1) if flux is not None else float('nan')
    # Fully developed value: mean over the interior turns (excludes the first turn, still
    # developing, and the last turn, which feels the straight outlet leg)
    f_dev = float(np.mean(fD[1:-1])) if len(fD) > 2 else fD[-1]
    rows.append((Re, De, f_dev, f_dev * Re / 64, ratio_ito(De)[0], ratio_white(De)[0], it, q_err))

if not rows:
    raise SystemExit(f'No results found under {os.path.normpath(case_root)}. Run Allrun first.')

rows.sort()
arr = np.array(rows)
np.savetxt(os.path.join(res_dir, 's01_friction.csv'), arr, delimiter=',', comments='', fmt='%.6g',
           header='Re,De,fD_cfd,fc_over_fs_cfd,fc_over_fs_ito,fc_over_fs_white,iterations,flux_err_pct')
print(f'{"Re":>6} {"De":>7} {"f_D":>9} {"fc/fs CFD":>10} {"Ito":>7} {"White":>7} {"vs Ito":>7} {"iter":>6} {"Q err":>7}')
for r in rows:
    print(f'{r[0]:6.0f} {r[1]:7.1f} {r[2]:9.5f} {r[3]:10.3f} {r[4]:7.3f} {r[5]:7.3f} '
          f'{100 * (r[3] / r[4] - 1):6.1f}% {r[6]:6d} {r[7]:6.2f}%')

De = np.logspace(0.5, np.log10(3000), 300)
fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.semilogx(De, ratio_ito(De), 'b-', label='Ito (1959)')
ax.semilogx(De, ratio_white(De), 'r:', label='White (1929)')
ax.semilogx(arr[:, 1], arr[:, 3], 'ko', ms=7, label='OpenFOAM (interior turns, fully developed)')
ax.set_xlabel('Dean number De = Re (r/R)$^{1/2}$')
ax.set_ylabel('$f_c / f_s$')
ax.set_title(f'Helical channel, r/R = {DELTA:.3f}')
ax.grid(True, which='both', alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(res_dir, 's01_friction_ratio.png'), dpi=200)

fig, ax = plt.subplots(figsize=(6.5, 4.5))
for Re, fD in sorted(per_turn.items()):
    ax.plot(range(1, len(fD) + 1), np.array(fD) * Re / 64, 'o-', label=f'Re = {Re}')
ax.set_xlabel('Helix turn')
ax.set_ylabel('$f_c / f_s$ over the turn')
ax.set_title('Flow development along the helix')
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(res_dir, 's01_development.png'), dpi=200)
print(f'Plots and CSV written to {os.path.normpath(res_dir)}')
