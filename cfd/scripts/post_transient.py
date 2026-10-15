"""Post-process the oscillatory torus-sector cases T01-T10: CFD-measured inertance and damping.

Each case imposes a sinusoidal kinematic pressure gradient G(t) = G_amp sin(wt) along the
channel (pressure jump over the periodic sector) and records the flow rate Q(t). For the
full inerter (channel length l = 1.888 m, piston area A_p):
    F(t)  = A_p * rho * l * G(t)                piston force
    xd(t) = u(t) * A_c / A_p,  u = Q / A_mesh   piston velocity (A_c: exact channel area)
Harmonic analysis over the last cycle gives the complex impedance at the drive frequency
    Z = F_hat / xd_hat = c_eq + i w b_eq
i.e. the equivalent inertance b_eq and parasitic damping c_eq (first harmonic). The previous
cycle is analysed too; the change shows how periodic (converged) the run is.

Compared with: the ideal inertance b = rho l A_p^2/A_c; Womersley's exact straight-pipe
solution (isolates the effect of curvature); and the quasi-steady curved-pipe correlation
model (python/inerter_model.inerter_force, friction only).
A nonlinear ROM F = b xdd + c1 xd + c2 xd|xd| is fitted jointly over both amplitudes per frequency.

Writes cfd/results/transient_summary.csv, transient_rom.csv, inerter_cfd_coeffs.json + plots.
Usage: python post_transient.py [set]       (default set: torus_oscillatory)
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
sys.path.insert(0, os.path.join(here, '..', '..', 'python'))
import inerter_model as im   # noqa: E402

SET = sys.argv[1] if len(sys.argv) > 1 else 'torus_oscillatory'
root = os.path.join(here, '..', 'openfoam', SET)
res_dir = os.path.join(here, '..', 'results')
os.makedirs(res_dir, exist_ok=True)
tag = '' if SET == 'torus_oscillatory' else '_' + SET
info = json.load(open(os.path.join(root, 'mesh', 'mesh_info.json')))
A_mesh = info['inlet_area']
A_c = math.pi * info['d'] ** 2 / 4
p = im.params()                                  # physical inerter: l = 1.888 m, b = 91.7 kg
p_fric = im.params(K_in=0.0, K_out=0.0)          # friction only (no entry/exit losses in the CFD)


def monitor(case, name):
    files = sorted(glob.glob(os.path.join(case, 'postProcessing', name, '*', 'surfaceFieldValue.dat')),
                   key=lambda f: float(os.path.basename(os.path.dirname(f))))
    rows = []
    for fpath in files:
        rows += [[float(x) for x in ln.split()[:2]] for ln in open(fpath) if ln.strip() and not ln.startswith('#')]
    a = np.array(rows)
    _, idx = np.unique(a[:, 0], return_index=True)
    return a[idx, 0], a[idx, 1]


def harmonic(t, y, w, k=1):
    """Complex Fourier coefficient of y at k*w over one period (y ~ Re(Y e^{iwt})).
    Trapezoidal integration: valid for the non-uniform (adaptive) time steps."""
    T = 2 * np.pi / w
    tt = np.concatenate([[t[-1] - T], t])                    # close the period with the periodic image
    yy = np.concatenate([[y[-1]], y]) * np.exp(-1j * k * w * tt)
    return 2 / T * im.trapz(yy, tt)


rows, series = [], {}
for case in sorted(glob.glob(os.path.join(root, 'T*'))):
    cid = os.path.basename(case)
    m = json.load(open(os.path.join(case, 'case_info.json')))
    try:
        t, flux = monitor(case, 'flux')
    except (ValueError, IndexError):
        print(f'skip {cid}: no results')
        continue
    if t[-1] < m['end_time'] * 0.999:
        print(f'skip {cid}: incomplete (t = {t[-1]:.4f} of {m["end_time"]:.4f} s)')
        continue
    f = m['freq']
    w = 2 * math.pi * f
    T = 1 / f
    G = m['G_amp'] * np.sin(w * t)                 # imposed kinematic gradient (drives -theta flow)
    u = -flux / A_mesh                             # bulk velocity, positive along the drive
    F = p.A_p * p.rho * p.l * G
    xd = u * A_c / p.A_p
    out = {}
    for lab, sel in (('last', t > t[-1] - T + 1e-12), ('prev', (t > t[-1] - 2 * T + 1e-12) & (t <= t[-1] - T + 1e-12))):
        Fh, Vh = harmonic(t[sel], F[sel], w), harmonic(t[sel], xd[sel], w)
        Z = Fh / Vh
        out[lab] = (Z.imag / w, Z.real, abs(Vh) / w, abs(harmonic(t[sel], xd[sel], w, 3)) / abs(Vh))
    b_eq, c_eq, X_ach, thd3 = out['last']
    b_prev, c_prev, _, _ = out['prev']
    v_amp = X_ach * w * p.A_p / A_c
    Re_amp = v_amp * info['d'] / (p.mu / p.rho)
    b_w, c_w, alpha = im.womersley_inerter(p, f)
    tq = np.linspace(0, T, 2000, endpoint=False)
    xq = X_ach * w * np.sin(w * tq)
    Fq = im.inerter_force(0.0, xq, p_fric)[2]
    c_qs = np.sum(Fq * xq) / np.sum(xq * xq)       # first harmonic of the quasi-steady correlation model
    rows.append(dict(case=cid, f=f, X_target_mm=m['X'] * 1e3, X_mm=X_ach * 1e3, alpha=float(alpha),
                     Re_amp=Re_amp, De_amp=Re_amp * math.sqrt(p.delta),
                     b_eq=b_eq, b_ratio=b_eq / p.b, b_womersley_ratio=float(b_w) / p.b,
                     c_eq=c_eq, c_ratio=c_eq / p.c_lin, c_womersley_ratio=float(c_w) / p.c_lin,
                     c_qs_ratio=c_qs / p.c_lin, harmonic3=thd3,
                     cycle_change_b=abs(b_eq / b_prev - 1), cycle_change_c=abs(c_eq / c_prev - 1)))
    last = t > t[-1] - T + 1e-12
    xdd = np.gradient(xd, t)
    x = np.cumsum(xd * np.gradient(t))
    series[cid] = dict(t=t[last], F=F[last], xd=xd[last], xdd=xdd[last], x=x[last] - x[last].mean(),
                       f=f, X=m['X'], b_eq=b_eq, c_eq=c_eq)

if not rows:
    raise SystemExit(f'No finished cases under {os.path.normpath(root)}')

keys = list(rows[0])
with open(os.path.join(res_dir, f'transient_summary{tag}.csv'), 'w') as fh:
    fh.write(','.join(keys) + '\n')
    for r in rows:
        fh.write(','.join(f'{r[k]:.6g}' if isinstance(r[k], float) else str(r[k]) for k in keys) + '\n')

print(f'Set {SET}: ideal inertance b = {p.b:.2f} kg, straight-pipe laminar damping c_lin = {p.c_lin:.0f} N s/m\n')
print(f'{"case":>4} {"f":>4} {"X":>4} {"Wo":>5} {"De":>5} | {"b_eq":>6} {"/b_id":>6} {"Wom.":>6} | '
      f'{"c_eq":>6} {"/c_lin":>6} {"Wom.":>6} {"q-s":>6} | {"cyc.chg":>7} {"H3":>5}')
for r in rows:
    print(f'{r["case"]:>4} {r["f"]:4g} {r["X_mm"]:4.1f} {r["alpha"]:5.2f} {r["De_amp"]:5.0f} | '
          f'{r["b_eq"]:6.1f} {r["b_ratio"]:6.3f} {r["b_womersley_ratio"]:6.3f} | '
          f'{r["c_eq"]:6.0f} {r["c_ratio"]:6.3f} {r["c_womersley_ratio"]:6.3f} {r["c_qs_ratio"]:6.3f} | '
          f'{100 * max(r["cycle_change_b"], r["cycle_change_c"]):6.2f}% {100 * r["harmonic3"]:4.1f}%')
print('(X = achieved piston amplitude [mm]; De = Dean number at peak velocity; '
      'H3 = 3rd-harmonic content of the velocity response)')

# Joint nonlinear ROM per frequency (both amplitudes)
rom = []
for f in sorted({r['f'] for r in rows}):
    ids = [r['case'] for r in rows if r['f'] == f]
    A = np.vstack([np.column_stack([series[c]['xdd'], series[c]['xd'], series[c]['xd'] * np.abs(series[c]['xd'])])
                   for c in ids])
    Fv = np.concatenate([series[c]['F'] for c in ids])
    if len(ids) < 2:
        th = np.append(np.linalg.lstsq(A[:, :2], Fv, rcond=None)[0], np.nan)
        Ff = A[:, :2] @ th[:2]
    else:
        th = np.linalg.lstsq(A, Fv, rcond=None)[0]
        Ff = A @ th
    rom.append(dict(f=f, cases='+'.join(ids), b=th[0], c1=th[1], c2=th[2],
                    nrmse=math.sqrt(np.mean((Fv - Ff) ** 2)) / (Fv.max() - Fv.min())))
with open(os.path.join(res_dir, f'transient_rom{tag}.csv'), 'w') as fh:
    fh.write('f,cases,b,c1,c2,nrmse\n')
    for r in rom:
        fh.write(f'{r["f"]:g},{r["cases"]},{r["b"]:.6g},{r["c1"]:.6g},{r["c2"]:.6g},{r["nrmse"]:.4g}\n')
print('\nNonlinear ROM  F = b xdd + c1 xd + c2 xd|xd|  (joint fit over amplitudes):')
for r in rom:
    print(f'  f = {r["f"]:4g} Hz ({r["cases"]}): b = {r["b"]:6.1f} kg, c1 = {r["c1"]:6.0f} N s/m, '
          f'c2 = {r["c2"]:8.0f} N s^2/m^2, nrmse = {100 * r["nrmse"]:.2f}%')

# coefficients for the vehicle study (ratios to the ideal values), per nominal amplitude
coeffs = {}
for X_mm in sorted({r['X_target_mm'] for r in rows}):
    sel = sorted([r for r in rows if r['X_target_mm'] == X_mm], key=lambda r: r['f'])
    coeffs[f'{X_mm:g}mm'] = {k: [r[k] for r in sel] for k in
                             ('f', 'X_mm', 'b_ratio', 'c_ratio', 'b_womersley_ratio', 'c_womersley_ratio')}
json.dump(dict(set=SET, b_ideal=p.b, c_lin=p.c_lin, d=p.d, R_h=p.R_h, l=p.l, amplitudes=coeffs),
          open(os.path.join(res_dir, f'inerter_cfd_coeffs{tag}.json'), 'w'), indent=2)

# ---- plots
fw = np.logspace(-0.3, math.log10(30), 200)
bw, cw, _ = im.womersley_inerter(p, fw)
mk = {2.0: 'o', 5.0: 's'}
fig, axs = plt.subplots(1, 2, figsize=(11, 4.3))
axs[0].semilogx(fw, bw / p.b, 'k-', label='Womersley (straight pipe, exact)')
axs[0].axhline(1, color='gray', ls=':', label='Ideal inerter ($\\rho l A_p^2/A_c$)')
axs[1].semilogx(fw, cw / p.c_lin, 'k-', label='Womersley (straight pipe, exact)')
for X_mm in sorted({r['X_target_mm'] for r in rows}):
    sel = sorted([r for r in rows if r['X_target_mm'] == X_mm], key=lambda r: r['f'])
    fs = [r['f'] for r in sel]
    axs[0].semilogx(fs, [r['b_ratio'] for r in sel], mk.get(X_mm, 'd') + '-', label=f'CFD curved channel, X = {X_mm:g} mm')
    axs[1].semilogx(fs, [r['c_ratio'] for r in sel], mk.get(X_mm, 'd') + '-', label=f'CFD curved channel, X = {X_mm:g} mm')
    axs[1].semilogx(fs, [r['c_qs_ratio'] for r in sel], mk.get(X_mm, 'd') + ':', mfc='none',
                    label=f'Quasi-steady correlation, X = {X_mm:g} mm')
axs[0].set(xlabel='Frequency [Hz]', ylabel='$b_{eq}$ / $b_{ideal}$', title='Effective inertance')
axs[1].set(xlabel='Frequency [Hz]', ylabel='$c_{eq}$ / $c_{lin}$', title='Effective (parasitic) damping')
for a in axs:
    a.grid(True, which='both', alpha=0.3)
    a.legend(fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(res_dir, f'transient_coefficients{tag}.png'), dpi=200)

fig, axs = plt.subplots(1, 2, figsize=(11, 4.3))
for ax, X_mm in zip(axs, (2.0, 5.0)):
    for cid, s in series.items():
        if abs(s['X'] * 1e3 - X_mm) > 1e-9:
            continue
        o = np.argsort(s['t'])
        ln, = ax.plot(s['x'][o] * 1e3, s['F'][o] / 1e3, label=f'{s["f"]:g} Hz CFD')
        ax.plot(s['x'][o] * 1e3, p.b * s['xdd'][o] / 1e3, ':', color=ln.get_color())
    ax.set(xlabel='Piston displacement [mm]', ylabel='Force [kN]',
           title=f'Force loops, nominal X = {X_mm:g} mm (dotted: ideal inerter)')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(res_dir, f'transient_force_loops{tag}.png'), dpi=200)
print(f'\nCSV, JSON and plots written to {os.path.normpath(res_dir)}')
