"""Steady torus sector vs full helix: effect of neglecting the helix pitch (torsion).

Torus: imposed kinematic gradient G = jump / s_sector, measured bulk velocity u = |Q| / A_mesh,
       f_D = G d / (0.5 u^2), Re = u d / nu.
Helix: fully developed f_c/f_s from S01 (cfd/results/s01_friction.csv), interpolated in log(De).

Usage: python post_torus_steady.py [set]   (default torus_steady)
"""
import glob
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
SET = sys.argv[1] if len(sys.argv) > 1 else 'torus_steady'
root = os.path.join(here, '..', 'openfoam', SET)
res_dir = os.path.join(here, '..', 'results')
info = json.load(open(os.path.join(root, 'mesh', 'mesh_info.json')))
NU = 0.028 / 870.0
D, DELTA = info['d'], info['d'] / 2 / info['R_h']


def ito(De):
    return max(1.0, 21.5 * De / (1.56 + math.log10(De)) ** 5.73) if De > 13.5 else 1.0


rows = []
for case in sorted(glob.glob(os.path.join(root, 're*'))):
    m = json.load(open(os.path.join(case, 'case_info.json')))
    dat = glob.glob(os.path.join(case, 'postProcessing', 'flux', '*', 'surfaceFieldValue.dat'))
    if not dat:
        continue
    log = open(os.path.join(case, 'log.simpleFoam')).read() if os.path.exists(os.path.join(case, 'log.simpleFoam')) else ''
    vals = [ln.split() for ln in open(dat[0]) if ln.strip() and not ln.startswith('#')]
    u = abs(float(vals[-1][1])) / info['inlet_area']
    Re = u * D / NU
    De = Re * math.sqrt(DELTA)
    ratio = m['G_imposed'] * D / (0.5 * u ** 2) * Re / 64
    rows.append(dict(Re=Re, De=De, torus=ratio, ito=ito(De), converged='converged in' in log))

helix_csv = os.path.join(res_dir, 's01_friction.csv')
helix = np.genfromtxt(helix_csv, delimiter=',', names=True) if os.path.exists(helix_csv) else None
print(f'{"Re":>7} {"De":>7} {"torus":>7} {"helix":>7} {"Ito":>7} {"torus-helix":>11} {"conv":>5}')
for r in rows:
    h = float(np.interp(math.log(r['De']), np.log(helix['De']), helix['fc_over_fs_cfd'])) if helix is not None else float('nan')
    r['helix'] = h
    print(f'{r["Re"]:7.0f} {r["De"]:7.1f} {r["torus"]:7.3f} {h:7.3f} {r["ito"]:7.3f} '
          f'{100 * (r["torus"] / h - 1):10.2f}% {"yes" if r["converged"] else "NO":>5}')

with open(os.path.join(res_dir, f'{SET}.csv'), 'w') as fh:
    fh.write('Re,De,fc_over_fs_torus,fc_over_fs_helix,fc_over_fs_ito,converged\n')
    for r in rows:
        fh.write(f'{r["Re"]:.6g},{r["De"]:.6g},{r["torus"]:.6g},{r["helix"]:.6g},{r["ito"]:.6g},{int(r["converged"])}\n')

fig, ax = plt.subplots(figsize=(6.5, 4.5))
De = np.logspace(1, math.log10(2000), 200)
ax.semilogx(De, [ito(x) for x in De], 'b-', label='Ito (1959)')
if helix is not None:
    ax.semilogx(helix['De'], helix['fc_over_fs_cfd'], 'ko', mfc='none', ms=8, label='CFD full helix (S01)')
ax.semilogx([r['De'] for r in rows], [r['torus'] for r in rows], 'r^', label='CFD periodic torus sector (no pitch)')
ax.set(xlabel='Dean number De', ylabel='$f_c/f_s$', title='Effect of helix pitch (torsion) on friction')
ax.grid(True, which='both', alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(res_dir, f'{SET}.png'), dpi=200)
print(f'written {os.path.normpath(os.path.join(res_dir, SET))}.csv/.png')
