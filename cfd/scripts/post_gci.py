"""Grid Convergence Index (GCI) for the S01 friction factor, after Celik et al. (2008),
"Procedure for estimation and reporting of uncertainty due to discretization in CFD
applications", J. Fluids Eng. 130(7), 078001.

Meshes: coarse (cfd/openfoam/gci_coarse), medium (cfd/openfoam/s01), fine (cfd/openfoam/gci_fine).
Quantity: phi = f_c/f_s, fully developed (mean over interior helix turns).

Usage: python post_gci.py      -> table on screen, cfd/results/gci_s01.csv, gci_s01.png
"""
import glob
import json
import math
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
base = os.path.join(here, '..', 'openfoam')
res_dir = os.path.join(here, '..', 'results')
os.makedirs(res_dir, exist_ok=True)
LEVELS = [('fine', 'gci_fine'), ('medium', 's01'), ('coarse', 'gci_coarse')]   # 1, 2, 3
NU = 0.028 / 870.0


AVG_WINDOW = 1000   # iterations averaged when a case did not meet residualControl


def monitor(pattern):
    """(iterations, values) of an OpenFOAM surfaceFieldValue monitor."""
    files = sorted(glob.glob(pattern), key=lambda f: float(os.path.basename(os.path.dirname(f))))
    rows = np.array([[float(x) for x in ln.split()[:2]] for ln in open(files[-1])
                     if ln.strip() and not ln.startswith('#')])
    return rows[:, 0], rows[:, 1]


def converged(case):
    log = os.path.join(case, 'log.simpleFoam')
    return os.path.exists(log) and 'converged in' in open(log).read()


def n_cells(mesh_dir):
    with open(os.path.join(mesh_dir, 'constant', 'polyMesh', 'owner')) as fh:
        for line in fh:
            if 'nCells:' in line:
                return int(line.split('nCells:')[1].split()[0])
    raise RuntimeError(f'nCells not found in {mesh_dir}')


def fc_over_fs(case, info, Re):
    """Fully developed f_c/f_s (mean over interior turns). Returns (value, iterative std).
    Converged case: final monitored value, std 0. Non-converged (residuals stalled, e.g.
    the coarse mesh at high Dean number): mean and std over the last AVG_WINDOW iterations."""
    series = [monitor(os.path.join(case, 'postProcessing', f'pTurn{i}', '*', 'surfaceFieldValue.dat'))
              for i in range(info['turns'] + 1)]
    it = series[0][0]
    P = np.array([s[1] for s in series])                    # [plane, iteration]
    v = Re * NU / info['d']
    fD = (P[:-1] - P[1:]) / info['s_turn'] * info['d'] / (0.5 * v ** 2)
    phi = fD[1:-1].mean(axis=0) * Re / 64                   # per iteration
    if converged(case):
        return float(phi[-1]), 0.0
    win = it > it[-1] - AVG_WINDOW
    print(f'  note: {os.path.relpath(case, base)} did not converge; averaging last '
          f'{AVG_WINDOW} iterations (std {100 * phi[win].std() / phi[win].mean():.2f}%)')
    return float(phi[win].mean()), float(phi[win].std())


def ito(De):
    return max(1.0, 21.5 * De / (1.56 + math.log10(De)) ** 5.73) if De > 13.5 else 1.0


def gci(phi, N):
    """phi, N ordered fine (1), medium (2), coarse (3). 3D: h ~ N^(-1/3)."""
    h = [n ** (-1 / 3) for n in N]
    r21, r32 = h[1] / h[0], h[2] / h[1]
    e21, e32 = phi[1] - phi[0], phi[2] - phi[1]
    s = math.copysign(1, e32 / e21)
    p = abs(math.log(abs(e32 / e21))) / math.log(r21)
    for _ in range(100):                       # fixed-point iteration for the apparent order
        q = math.log((r21 ** p - s) / (r32 ** p - s))
        p_new = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(p_new - p) < 1e-10:
            break
        p = p_new
    # Outside 0.5 < p < 3 (formal order of the schemes is 2) or oscillatory convergence, the
    # three-grid estimate is unreliable: fall back to a two-grid (fine/medium) estimate with
    # p = 2 and the conservative safety factor Fs = 3 (Roache 1998).
    fallback = s < 0 or not (0.5 < p < 3.0)
    p_used, Fs = (2.0, 3.0) if fallback else (p, 1.25)
    phi_ext = (r21 ** p_used * phi[0] - phi[1]) / (r21 ** p_used - 1)
    ea21 = abs((phi[0] - phi[1]) / phi[0])
    eext21 = abs((phi_ext - phi[0]) / phi_ext)
    gci21 = Fs * ea21 / (r21 ** p_used - 1)
    return dict(r21=r21, r32=r32, p=p, oscillatory=s < 0, fallback=fallback, phi_ext=phi_ext,
                ea21=ea21, eext21=eext21, gci_fine=gci21)


infos = {lvl: json.load(open(os.path.join(base, d, 'mesh', 'mesh_info.json'))) for lvl, d in LEVELS}
N = [n_cells(os.path.join(base, d, 'mesh')) for _, d in LEVELS]
delta = infos['fine']['d'] / 2 / infos['fine']['R_h']
print('Cells: ' + ', '.join(f'{lvl} {n:,}' for (lvl, _), n in zip(LEVELS, N)))

rows = []
import sys
RE = [int(x) for x in sys.argv[1:]] or [100, 1000, 4000]
for Re in RE:
    vals = [fc_over_fs(os.path.join(base, d, f're{Re:05d}'), infos[lvl], Re) for lvl, d in LEVELS]
    phi = [v[0] for v in vals]
    g = gci(phi, N)
    De = Re * math.sqrt(delta)
    rows.append(dict(Re=Re, De=De, fine=phi[0], medium=phi[1], coarse=phi[2], ito=ito(De),
                     iter_std_max=max(v[1] / v[0] for v in vals), **g))

hdr = f'{"Re":>5} {"De":>6} {"coarse":>8} {"medium":>8} {"fine":>8} {"extrap.":>8} {"p":>5} {"GCI_fine":>9} {"iter.std":>8} {"Ito":>7} {"ext vs Ito":>10}'
print(hdr)
for r in rows:
    flag = (' (oscillatory)' if r['oscillatory'] else '') + \
           (' -> 2-grid fallback: p=2, Fs=3' if r['fallback'] else '')
    print(f'{r["Re"]:5d} {r["De"]:6.0f} {r["coarse"]:8.4f} {r["medium"]:8.4f} {r["fine"]:8.4f} '
          f'{r["phi_ext"]:8.4f} {r["p"]:5.2f} {100 * r["gci_fine"]:8.2f}% {100 * r["iter_std_max"]:7.2f}% {r["ito"]:7.3f} '
          f'{100 * (r["phi_ext"] / r["ito"] - 1):9.1f}%{flag}')

keys = ['Re', 'De', 'coarse', 'medium', 'fine', 'phi_ext', 'p', 'r21', 'r32', 'ea21', 'eext21', 'gci_fine',
        'iter_std_max', 'ito']
np.savetxt(os.path.join(res_dir, 'gci_s01.csv'), np.array([[r[k] for k in keys] for r in rows]),
           delimiter=',', header=','.join(keys), comments='', fmt='%.6g')

fig, ax = plt.subplots(figsize=(6.5, 4.5))
De = np.logspace(1, np.log10(2000), 200)
ax.semilogx(De, [ito(x) for x in De], 'b-', label='Ito (1959)')
for lvl, mk in (('coarse', 's'), ('medium', '^'), ('fine', 'o')):
    ax.semilogx([r['De'] for r in rows], [r[lvl] for r in rows], mk, mfc='none', label=f'OpenFOAM {lvl}')
ax.errorbar([r['De'] for r in rows], [r['phi_ext'] for r in rows],
            yerr=[r['gci_fine'] * r['fine'] for r in rows], fmt='k*', ms=9, capsize=4,
            label='Richardson extrapolated ± GCI$_{fine}$')
ax.set_xlabel('Dean number De')
ax.set_ylabel('$f_c / f_s$')
ax.set_title('Mesh independence (GCI, Celik et al. 2008)')
ax.grid(True, which='both', alpha=0.3)
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(res_dir, 'gci_s01.png'), dpi=200)
print(f'Written {os.path.normpath(os.path.join(res_dir, "gci_s01.csv"))} and gci_s01.png')
