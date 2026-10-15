"""Post-process the piston chamber + port cases (make_chamber_openfoam.py).

1. Steady (chamber = fine mesh, chamber_transient = coarser mesh): entry and exit loss coefficients
   from a mechanical-energy balance between the piston face and the developed flow at x = 0.30 m:
       E = p + <|U|^2>_phi / 2      (kinematic; flux-weighted kinetic energy)
       K_in  = (E_piston - E_300 - 32 nu v L / d^2) / (v^2/2)          (flow into the tube)
       K_out = (E_300 - E_piston - 32 nu v L / d^2) / (v^2/2)          (flow out of the tube)
   i.e. the loss beyond fully developed pipe friction over the same length (L = 0.30 m).
2. Oscillatory osc_T04: device force F = 2 rho A_p p_piston (antisymmetric two-chamber device),
   first-harmonic inertance and damping; minus the coupled outlet (rest of the coil, torus CFD) and
   the 2 x 0.6 m of straight tube (Womersley exact) = the contribution of the piston chambers and ports.
3. Cavitation cav_p*: vapour volume and minimum pressure over the cycles vs charge pressure.

Writes cfd/results/chamber_losses.csv, chamber_summary.json, chamber_losses.png,
chamber_oscillation.png, cavitation.png.   Usage: python post_chamber.py [--wsl]
"""
import glob
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
proj = os.path.normpath(os.path.join(here, '..', '..'))
sys.path.insert(0, os.path.join(proj, 'python'))
import inerter_model as im   # noqa: E402

OF = os.path.join(proj, 'cfd', 'openfoam')
if '--wsl' in sys.argv:                 # read the running cases directly from ~/inerter in Ubuntu
    import subprocess
    home = subprocess.run(['wsl.exe', '-e', 'bash', '-c', 'wslpath -w ~'], capture_output=True, text=True).stdout
    OF = os.path.join(home.replace(chr(0), '').strip(), 'inerter')
RES = os.path.join(proj, 'cfd', 'results')
RHO, MU = 870.0, 0.028
NU = MU / RHO
D, L300 = 6e-3, 0.30
OIL, INK, GREY, ACC = '#c2410c', '#1f2937', '#9ca3af', '#2563eb'


def series(case, fo, col=1):
    """(time, values, header area) of a function-object output file."""
    f = sorted(glob.glob(os.path.join(case, 'postProcessing', fo, '*', '*.dat')))
    if not f:
        return None
    area = None
    rows = []
    for fn in f:                                     # restarts write new time folders
        for ln in open(fn):
            if ln.startswith('# Area'):
                area = float(ln.split(':')[1])
            elif ln.strip() and not ln.startswith('#'):
                rows.append([float(v) for v in ln.split()[:col + 1]])
    a = np.array(rows)
    return a[:, 0], a[:, col], area


def last(case, fo, n=400):
    s = series(case, fo)
    return float(np.mean(s[1][-n:])), float(np.std(s[1][-n:]) / max(abs(np.mean(s[1][-n:])), 1e-12)), s[2]


def steady_losses():
    rows = []
    for set_name, mesh in (('chamber', 'fine'), ('chamber_transient', 'coarse')):
        for case in sorted(glob.glob(os.path.join(OF, set_name, '*_re*'))):
            if not glob.glob(os.path.join(case, 'postProcessing', 'pPiston')):
                continue
            info = json.load(open(os.path.join(case, 'case_info.json')))
            q, _, a_t = last(case, 'qOutlet')
            qp, _, a_p = last(case, 'qPiston')
            v, up = abs(q) / a_t, abs(qp) / a_p
            pp, pp_unsteady, _ = last(case, 'pPiston')
            p3, _, _ = last(case, 'z300')
            p4, _, _ = last(case, 'z450')
            ke3 = series(case, 'ke300')[1][-1]
            head = 0.5 * v ** 2
            fric = 32 * NU * v * L300 / D ** 2
            e_p, e_3 = pp + 0.5 * up ** 2, p3 + 0.5 * ke3
            loss = (e_p - e_3) if info['direction'] == 'in' else (e_3 - e_p)
            g_ratio = abs(p3 - p4) / 0.15 / (32 * NU * v / D ** 2)
            rows.append(dict(mesh=mesh, direction=info['direction'], Re=v * D / NU, v=v,
                             K=(loss - fric) / head, alpha_300=ke3 / v ** 2, developed_ratio=g_ratio,
                             p_piston_unsteadiness=pp_unsteady))
    return rows


def fit(t, y, f, basis):
    A = np.column_stack(basis + [np.ones_like(t)])
    th = np.linalg.lstsq(A, y, rcond=None)[0]
    return th


def oscillatory():
    case = os.path.join(OF, 'chamber_transient', 'osc_T04')
    s = series(case, 'pPiston')
    if s is None:
        return None
    info = json.load(open(os.path.join(case, 'case_info.json')))
    f, X, b, c, phi = info['f'], info['X'], info['b_eq'], info['c_eq'], info['phi']
    w = 2 * math.pi * f
    t, p = s[0], s[1]
    if t[-1] < info['n_cycles'] / f * 0.999:
        print(f'osc_T04 still running (t = {t[-1]:.4f} of {info["n_cycles"] / f:.3f} s)')
        return None
    sel = t >= (info['n_cycles'] - 1) / f                 # last cycle
    t, p = t[sel], p[sel]
    xd, xdd = X * w * np.sin(w * t), X * w ** 2 * np.cos(w * t)
    A_p = math.pi * 0.02 ** 2
    F = 2 * RHO * A_p * p                                 # device force (both chambers)
    b_tot, c_tot, _ = fit(t, F, f, [xdd, xd])
    F_lin = b_tot * xdd + c_tot * xd
    harm = math.sqrt(np.mean((F - F_lin - np.mean(F - F_lin)) ** 2)) / (F.max() - F.min())
    # parts: outlet boundary (rest of coil, from torus CFD) + straight tube (Womersley) + ports/chambers
    b_bc, c_bc = 2 * phi * b, 2 * phi * c
    p_tube = im.params(l_override=2 * 0.6)
    b_tube, c_tube, alpha = im.womersley_inerter(p_tube, f)
    b_port, c_port = b_tot - b_bc - float(b_tube), c_tot - c_bc - float(c_tube)
    out = dict(case='osc_T04', f=f, X_mm=X * 1e3, b_total=b_tot, c_total=c_tot, b_boundary=b_bc, c_boundary=c_bc,
               b_straight_tube=float(b_tube), c_straight_tube=float(c_tube), b_ports=b_port, c_ports=c_port,
               b_torus=b, c_torus=c, port_c_fraction=c_port / c, port_b_fraction=b_port / b,
               nonlinearity=harm, womersley_alpha=float(alpha))
    return out, (t, F, xd, xdd, b_tot, c_tot)


def cavitation():
    rows = []
    for case in sorted(glob.glob(os.path.join(OF, 'chamber_transient', 'cav_p*'))):
        v = series(case, 'vapour')
        pm = series(case, 'pMin')
        if v is None or pm is None:
            continue
        info = json.load(open(os.path.join(case, 'case_info.json')))
        V_tot = v[1][0]
        vap = (V_tot - v[1]) * 360 / 5.0                  # full-device (360 deg) vapour volume [m^3], one chamber side
        done = v[0][-1] >= info['n_cycles'] / info['f'] * 0.999
        rows.append(dict(case=os.path.basename(case), p_charge_MPa=info['p_charge'] / 1e6,
                         vapour_max_mm3=float(vap.max() * 1e9), p_min_MPa=float(pm[1].min() / 1e6),
                         finished=bool(done), t=v[0], vap=vap * 1e9, tp=pm[0], pmin=pm[1] / 1e6,
                         f=info['f'], X=info['X'], b=info['b_eq'], c=info['c_eq']))
    return rows


def main():
    os.makedirs(RES, exist_ok=True)
    summary = {}
    # ---------------------------------------------------------- 1. steady losses
    rows = steady_losses()
    if rows:
        with open(os.path.join(RES, 'chamber_losses.csv'), 'w') as fh:
            keys = list(rows[0])
            fh.write(','.join(keys) + '\n')
            for r in rows:
                fh.write(','.join(f'{r[k]:.5g}' if isinstance(r[k], float) else str(r[k]) for k in keys) + '\n')
        print(f"{'mesh':7s} {'dir':4s} {'Re':>6s} {'K':>7s} {'alpha':>6s} {'dev':>6s} {'unst':>7s}")
        for r in rows:
            print(f"{r['mesh']:7s} {r['direction']:4s} {r['Re']:6.0f} {r['K']:7.3f} {r['alpha_300']:6.3f} "
                  f"{r['developed_ratio']:6.3f} {r['p_piston_unsteadiness']:7.1e}")
        fine = [r for r in rows if r['mesh'] == 'fine']
        summary['K_in'] = {f"{r['Re']:.0f}": r['K'] for r in fine if r['direction'] == 'in'}
        summary['K_out'] = {f"{r['Re']:.0f}": r['K'] for r in fine if r['direction'] == 'out'}
        mesh_cmp = []
        for r in rows:
            if r['mesh'] == 'coarse':
                m = [q for q in fine if q['direction'] == r['direction'] and abs(q['Re'] / r['Re'] - 1) < 0.05]
                if m:
                    mesh_cmp.append(dict(direction=r['direction'], Re=round(r['Re']), K_fine=m[0]['K'], K_coarse=r['K']))
        summary['mesh_check'] = mesh_cmp
        fig, ax = plt.subplots(figsize=(7.2, 4.3))
        for d, col, lab, txt in (('in', ACC, 'Entry (chamber → channel)', 0.5), ('out', OIL, 'Exit (channel → chamber)', 1.0)):
            for mesh, mk, ls in (('fine', 'o', '-'), ('coarse', 's', 'none')):
                rr = sorted([r for r in rows if r['direction'] == d and r['mesh'] == mesh], key=lambda r: r['Re'])
                if rr:
                    ax.plot([r['Re'] for r in rr], [r['K'] for r in rr], marker=mk, ls=ls, color=col,
                            mfc=col if mesh == 'fine' else 'white', label=f'{lab}, CFD {mesh} mesh')
            ax.axhline(txt, color=col, ls=':', lw=1.2)
            ax.text(105, txt + 0.04, f'textbook {lab.split()[0].lower()} K = {txt}', color=col, fontsize=8)
        ax.set(xscale='log', xlabel='Channel Reynolds number', ylabel='Loss coefficient K (beyond pipe friction)',
               title='Port losses at the piston chamber (axisymmetric CFD)')
        ax.grid(alpha=0.3, which='both')
        ax.legend(fontsize=8, loc='center right')
        fig.tight_layout()
        fig.savefig(os.path.join(RES, 'chamber_losses.png'), dpi=160)
        plt.close(fig)
    # ---------------------------------------------------------- 2. oscillatory
    o = oscillatory()
    if o:
        out, (t, F, xd, xdd, b_tot, c_tot) = o
        summary['oscillatory'] = out
        print(json.dumps(out, indent=1))
        X = out['X_mm'] * 1e-3
        x = -X * np.cos(2 * math.pi * out['f'] * t)
        fig, ax = plt.subplots(figsize=(6.4, 4.6))
        Ft = out['b_torus'] * xdd + out['c_torus'] * xd
        Fp = (out['b_torus'] + out['b_ports']) * xdd + (out['c_torus'] + out['c_ports']) * xd
        ax.plot(x * 1e3, Fp / 1e3, color=OIL, lw=2,
                label=f'Channel + piston chambers/ports (damping +{100 * out["port_c_fraction"]:.1f} %)')
        ax.plot(x * 1e3, Ft / 1e3, color=ACC, lw=1.6, ls='--', label='Channel only (torus CFD, as before)')
        ax.plot(x * 1e3, F / 1e3, color=OIL, lw=0.8, alpha=0.45,
                label='Raw 2D chamber CFD (ends modelled as straight tube)')
        bi = im.params().b
        ax.plot(x * 1e3, bi * xdd / 1e3, color=GREY, lw=1.2, ls=':', label=f'Ideal inerter (b = {bi:.1f} kg)')
        ax.set(xlabel='Piston displacement [mm]', ylabel='Inerter force [kN]',
               title=f'Force loop, {out["f"]:g} Hz, ±{out["X_mm"]:.1f} mm')
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(RES, 'chamber_oscillation.png'), dpi=160)
        plt.close(fig)
    # ---------------------------------------------------------- 3. cavitation
    cav = cavitation()
    if cav:
        r0 = cav[0]
        w = 2 * math.pi * r0['f']
        A_p = math.pi * 0.02 ** 2
        dp_amp = math.hypot(r0['b'] * w ** 2 * r0['X'], r0['c'] * w * r0['X']) / A_p / 2   # half the device pressure
        summary['cavitation'] = dict(f=r0['f'], X_mm=r0['X'] * 1e3, hand_calc_onset_MPa=dp_amp / 1e6,
                                     cases=[{k: r[k] for k in ('case', 'p_charge_MPa', 'vapour_max_mm3', 'p_min_MPa', 'finished')}
                                            for r in cav])
        onset = [r['p_charge_MPa'] for r in cav if r['vapour_max_mm3'] > 1.0]
        summary['cavitation']['cavitates_at_or_below_MPa'] = max(onset) if onset else None
        clean = [r['p_charge_MPa'] for r in cav if r['vapour_max_mm3'] <= 1.0]
        summary['cavitation']['clean_at_or_above_MPa'] = min(clean) if clean else None
        for r in cav:
            print(f"cavitation {r['case']}: charge {r['p_charge_MPa']:.1f} MPa  vapour max {r['vapour_max_mm3']:.2f} mm3  "
                  f"p_min {r['p_min_MPa']:.3f} MPa  {'done' if r['finished'] else 'RUNNING'}")
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
        cm = plt.get_cmap('viridis')
        for i, r in enumerate(cav):
            col = cm(i / max(1, len(cav) - 1))
            a1.plot(r['t'] * 1e3, r['vap'], color=col, label=f"{r['p_charge_MPa']:.1f} MPa")
        a1.set(xlabel='Time [ms]', ylabel='Vapour volume in the chamber [mm³]',
               title=f"Cavitation, {r0['f']:g} Hz, ±{r0['X'] * 1e3:.2f} mm (case T05)")
        a1.legend(title='Charge pressure', fontsize=8)
        a1.grid(alpha=0.3)
        pc = [r['p_charge_MPa'] for r in cav]
        a2.plot(pc, [r['p_min_MPa'] for r in cav], 'o-', color=OIL, label='CFD minimum pressure')
        pcs = np.linspace(0, max(pc) * 1.05, 50)
        a2.plot(pcs, pcs - dp_amp / 1e6, ':', color=GREY, label='Hand calculation: p_charge − Δp/2')
        a2.axhline(0, color=INK, lw=0.8)
        lo = -0.6
        for r in cav:
            if r['p_min_MPa'] < lo:                       # liquid tension: the vapour model lags, fully cavitating
                a2.annotate(f"{r['p_min_MPa']:.1f} MPa\n(fully cavitating)", (r['p_charge_MPa'], lo),
                            xytext=(0.03, lo + 0.25), fontsize=8, color=OIL,
                            arrowprops=dict(arrowstyle='->', color=OIL))
        a2.set_ylim(lo, max(pc) * 0.6)
        a2.text(dp_amp / 1e6 + 0.04, lo + 0.1, f'predicted onset\n{dp_amp / 1e6:.2f} MPa', fontsize=8, color=GREY)
        a2.axvline(dp_amp / 1e6, color=GREY, lw=0.8, ls='--')
        a2.set(xlabel='Charge pressure [MPa]', ylabel='Minimum pressure in chamber [MPa]',
               title='Minimum pressure vs charge pressure')
        a2.legend(fontsize=8)
        a2.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(RES, 'cavitation.png'), dpi=160)
        plt.close(fig)
    json.dump(summary, open(os.path.join(RES, 'chamber_summary.json'), 'w'), indent=2)
    print('wrote', os.path.join(RES, 'chamber_summary.json'))


if __name__ == '__main__':
    main()
