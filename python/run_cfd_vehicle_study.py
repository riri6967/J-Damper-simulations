"""Grip benefit of the J-damper layout (L4) with progressively more realistic inerter models.

    1. ideal        F = b xdd
    2. correlation  ideal inertance + quasi-steady curved-pipe loss, c_par = (c_par/b) b
    3. Womersley    exact laminar oscillatory STRAIGHT-pipe impedance: b_eq(w), c_eq(w)
    4. CFD          Womersley x curvature correction measured by the oscillatory torus CFD
                    (kappa_b = b_cfd/b_wom, kappa_c = c_cfd/c_wom, interpolated in log f,
                    held constant outside the simulated 1-20 Hz band)
    5. CFD + piston chambers   model 4 plus the damping of the piston chambers, ports and drilled elbows,
                    inerter_model.port_damping(): quasi-steady linearisation of (K_in + K_out) 1/2 rho v|v| at
                    stroke X, scaled by the oscillatory chamber CFD (r_cfd ~ 0.85). K_in, K_out are the model
                    defaults, from the 3D drilled-port CFD (cfd/results/port3d_summary.json). c_ports depends on
                    A_p, A_c only, not on the channel length, so it is added to the inerter admittance unscaled by b.
For models 3-4 the inerter admittance is Q(jw) = b * [ (b_eq(w)/b_ideal) jw + c_eq(w)/b_ideal ]:
b is the NOMINAL (ideal-formula) inertance rho l A_p^2/A_c, i.e. the design parameter.
The CFD amplitude used is X = 2 mm (closest to the inerter stroke RMS of ~1.4-2 mm found by
run_time_domain.py); the 5 mm data are reported for sensitivity.

Usage: python run_cfd_vehicle_study.py      (needs cfd/results/inerter_cfd_coeffs.json)
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import minimize

import inerter_model as im

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'results')
os.makedirs(OUT, exist_ok=True)
CFD = json.load(open(os.path.join(HERE, '..', 'cfd', 'results', 'inerter_cfd_coeffs.json')))
CHAMBER = json.load(open(os.path.join(HERE, '..', 'cfd', 'results', 'chamber_summary.json')))
p = im.params()
f = np.linspace(0.2, 50, 3000)
s = 1j * 2 * np.pi * f
b_w, c_w, _ = im.womersley_inerter(p, f)
yb_wom, yc_wom = b_w / p.b, c_w / p.b          # per unit nominal inertance


def cfd_factors(amp):
    d = CFD['amplitudes'][amp]
    lf = np.log(np.array(d['f']))
    kb = np.array(d['b_ratio']) / np.array(d['b_womersley_ratio'])
    kc = np.array(d['c_ratio']) / np.array(d['c_womersley_ratio'])
    lq = np.log(f)
    return np.interp(lq, lf, kb), np.interp(lq, lf, kc), d


def port_damping(amp='2mm'):
    """Piston chamber + port damping c_ports(w) [N s/m] at stroke amp."""
    return im.port_damping(p, f, float(amp.rstrip('mm')) * 1e-3, CHAMBER)


def unit_admittance(model, amp='2mm'):
    """Inerter admittance per kg of nominal inertance, Q/b [1/s * N s/m / kg]."""
    if model == 'ideal':
        return s
    if model == 'correlation':
        return s + im.parasitic_ratio(p)
    if model == 'womersley':
        return yb_wom * s + yc_wom
    kb, kc, _ = cfd_factors(amp)
    return kb * yb_wom * s + kc * yc_wom


def optimise(qb, c_add=0.0):
    """L4: k || c1 || (k2 ser c2 ser inerter); inerter admittance = b * qb + c_add."""
    ser = lambda a, b: 1 / (1 / a + 1 / b)
    Q = lambda x: p.ks / s + x[0] + ser(ser(x[3] / s, x[2]), x[1] * qb + c_add)
    best = None
    for scale in (0.3, 1.0, 3.0):
        r = minimize(lambda lx: im.grip_metric(p, lambda _s: Q(np.exp(lx)), f),
                     np.log(np.array([300.0, 300.0, 3500.0, 5e5]) * scale), method='Nelder-Mead',
                     options=dict(maxiter=4000, maxfev=8000, xatol=1e-6, fatol=1e-10))
        if best is None or r.fun < best.fun:
            best = r
    return np.exp(best.x), best.fun


r0 = minimize(lambda lc: im.grip_metric(p, lambda _s: p.ks / _s + np.exp(lc[0]), f), [np.log(3000.0)],
              method='Nelder-Mead')
J0 = r0.fun
models = [('ideal', 'Ideal inerter', '2mm'), ('correlation', 'Correlation (quasi-steady)', '2mm'),
          ('womersley', 'Womersley (straight pipe)', '2mm'), ('cfd', 'CFD curved channel, X = 2 mm', '2mm')]
if '5mm' in CFD['amplitudes']:
    models.append(('cfd', 'CFD curved channel, X = 5 mm', '5mm'))
models.append(('cfd_ports', 'CFD channel + piston chambers, 2 mm', '2mm'))
if '5mm' in CFD['amplitudes']:
    models.append(('cfd_ports', 'CFD channel + piston chambers, 5 mm', '5mm'))


def model_admittance(key, amp):
    """(admittance per kg nominal inertance, extra damping independent of b)."""
    if key == 'cfd_ports':
        return unit_admittance('cfd', amp), port_damping(amp)
    return unit_admittance(key, amp), 0.0


print(f'Conventional L1 (optimised damper): J_grip = {J0:.4f}\n')
print(f'{"Inerter model (L4 layout)":<38} {"J_grip":>7} {"gain":>6} {"b_nom":>7} {"c2":>7} {"k2":>9}')
results = []
for key, label, amp in models:
    x, J = optimise(*model_admittance(key, amp))
    results.append(dict(model=label, J=J, gain=100 * (J0 - J) / J0, c1=x[0], b=x[1], c2=x[2], k2=x[3]))
    print(f'{label:<38} {J:7.4f} {100 * (J0 - J) / J0:5.1f}% {x[1]:7.1f} {x[2]:7.0f} {x[3]:9.3g}')

print(f'\nPiston chamber + port damping: K_in + K_out = {p.K_in + p.K_out:.2f}')
for amp in ('2mm', '5mm'):
    cp = port_damping(amp)
    print(f'  X = {amp}: c_ports = ' + ', '.join(f'{np.interp(fi, f, cp):.0f}' for fi in (1, 5, 10, 20))
          + ' N s/m at 1, 5, 10, 20 Hz')

kb, kc, d2 = cfd_factors('2mm')
print('\nCFD curvature correction factors (X = 2 mm), relative to Womersley straight pipe:')
for fi, b_r, c_r, bw_r, cw_r in zip(d2['f'], d2['b_ratio'], d2['c_ratio'], d2['b_womersley_ratio'], d2['c_womersley_ratio']):
    print(f'  {fi:5g} Hz: inertance x{b_r / bw_r:.3f}, damping x{c_r / cw_r:.3f}')
json.dump(dict(J0=J0, results=results, ports=dict(K_in=p.K_in, K_out=p.K_out)), open(os.path.join(OUT, 'cfd_vehicle_study.json'), 'w'), indent=2)

fig, axs = plt.subplots(1, 2, figsize=(12, 4.5))
axs[0].barh([r['model'] for r in results][::-1], [r['gain'] for r in results][::-1],
            color=['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink'][:len(results)][::-1])
axs[0].set(xlabel='Reduction in dynamic tyre load vs conventional [%]',
           title='J-damper layout: grip benefit by inerter model')
axs[0].grid(True, axis='x', alpha=0.3)
for key, label, amp in models:
    qb, c_add = model_admittance(key, amp)
    axs[1].loglog(f, np.abs(qb + c_add / p.b), label=label)
axs[1].set(xlabel='Frequency [Hz]', ylabel='|Q/b| [1/s]', title=f'Inerter admittance per kg nominal inertance (b = {p.b:.1f} kg)')
axs[1].grid(True, which='both', alpha=0.3)
axs[1].legend(fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'cfd_vehicle_study.png'), dpi=200)
print(f'\nSaved {os.path.join(OUT, "cfd_vehicle_study.png")} and cfd_vehicle_study.json')
