"""Render the flow-visualisation animation and the Dean-vortex figure from cfd/openfoam/torus_demo.

For each oscillatory case (10 Hz, 2 mm and 5 mm stroke), one frame per sampled phase:
    left   piston in its cylinder, moving with the CFD piston velocity; oil-flow direction in the coil
    middle channel cross-section: axial oil velocity (colour, + = along the drive) and the secondary
           (Dean) flow as streamlines; outer wall of the coil on the right
    right  piston force vs displacement over the cycle (CFD) with the ideal inerter, marker at this phase
Output: cfd/results/demo/<case>/frame_NN.png, cfd/results/demo/<case>.gif,
        cfd/results/dean_vortices.png (steady cases at three Dean numbers).
Usage: python render_demo.py
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
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
from scipy.interpolate import griddata
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', '..', 'python'))
import inerter_model as im   # noqa: E402

root = os.path.join(here, '..', 'openfoam', 'torus_demo')
res = os.path.join(here, '..', 'results')
info = json.load(open(os.path.join(root, 'mesh', 'mesh_info.json')))
p = im.params()
R, r = info['R_h'], info['d'] / 2
TH = math.radians(info['torus_deg'])
e_r = np.array([math.cos(TH), math.sin(TH), 0.0])
e_t = np.array([-math.sin(TH), math.cos(TH), 0.0])
A_mesh, A_c = info['inlet_area'], math.pi * info['d'] ** 2 / 4
NU = p.mu / p.rho

N = 61                                           # grid for plotting the section
gy, gz = np.meshgrid(np.linspace(-r, r, N), np.linspace(-r, r, N))
inside = gy ** 2 + gz ** 2 < (0.985 * r) ** 2
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
INK, OIL, STEEL, MUTED = '#14202b', '#b26d10', '#2c6496', '#566472'


def read_section(path):
    a = np.loadtxt(path, comments='#')
    xyz, U = a[:, :3], a[:, 3:6]
    y = xyz @ e_r - R                            # + towards the OUTER wall of the coil
    z = xyz[:, 2]
    w = -(U @ e_t)                               # axial velocity, + along the drive direction
    ur, uz = U @ e_r, U[:, 2]
    def grid(v):            # linear inside the sampled points, nearest for the thin ring next to the wall
        g = griddata((y, z), v, (gy, gz), method='linear')
        g = np.where(np.isnan(g), griddata((y, z), v, (gy, gz), method='nearest'), g)
        return np.where(inside, g, np.nan)
    return grid(w), grid(ur), grid(uz)


def section_axes(ax, W, Ur, Uz, vmax, title, cmap='RdBu_r', lw_scale=None):
    ax.imshow(W, origin='lower', extent=(-r * 1e3, r * 1e3, -r * 1e3, r * 1e3), cmap=cmap, vmin=-vmax, vmax=vmax,
              interpolation='bilinear')
    sp = np.hypot(Ur, Uz)
    lw = 0.6 + 2.2 * sp / (lw_scale or np.nanmax(sp) + 1e-12)
    ax.streamplot(gy[0] * 1e3, gz[:, 0] * 1e3, np.nan_to_num(Ur), np.nan_to_num(Uz), color='k', density=1.1,
                  linewidth=np.nan_to_num(lw), arrowsize=0.8)
    ax.add_patch(Circle((0, 0), r * 1e3, fill=False, lw=2, color=INK))
    ax.set_xlim(-r * 1e3 * 1.08, r * 1e3 * 1.08)
    ax.set_ylim(-r * 1e3 * 1.08, r * 1e3 * 1.08)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=9.5)
    ax.text(r * 1e3 * 1.02, -r * 1e3 * 1.05, 'outer wall →', ha='right', va='bottom', fontsize=7.5, color=MUTED)
    ax.text(-r * 1e3 * 1.02, -r * 1e3 * 1.05, '← coil axis', ha='left', va='bottom', fontsize=7.5, color=MUTED)


def render_case(name):
    case = os.path.join(root, name)
    m = json.load(open(os.path.join(case, 'case_info.json')))
    f, w0 = m['freq'], 2 * math.pi * m['freq']
    T = 1 / f
    # piston kinematics and force over the last cycle, from the flux monitor and the imposed gradient
    rows = np.array([[float(v) for v in ln.split()[:2]] for ln in
                     open(glob.glob(os.path.join(case, 'postProcessing', 'flux', '*', 'surfaceFieldValue.dat'))[0])
                     if ln.strip() and not ln.startswith('#')])
    t_all, flux = rows[:, 0], rows[:, 1]
    sel = t_all >= t_all[-1] - T - 1e-9
    t, xd = t_all[sel], -flux[sel] / A_mesh * A_c / p.A_p
    x = np.concatenate([[0], np.cumsum(0.5 * (xd[1:] + xd[:-1]) * np.diff(t))])
    x -= 0.5 * (x.max() + x.min())
    F = p.A_p * p.rho * p.l * m['G_amp'] * np.sin(w0 * t)
    F_ideal = None                                # set below: exact ideal inerter for harmonic motion
    X_amp = 0.5 * (x.max() - x.min())
    F_ideal = -p.b * w0 ** 2 * x                  # b*xdd with xdd = -w^2 x

    snaps = sorted(glob.glob(os.path.join(case, 'postProcessing', 'section', '*', 'U_cyc1.raw')),
                   key=lambda s: float(os.path.basename(os.path.dirname(s))))
    snaps = [s for s in snaps if float(os.path.basename(os.path.dirname(s))) >= t[0] - 1e-6][-m['frames']:]
    v_amp = np.max(np.abs(xd)) * p.A_p / A_c
    out = os.path.join(res, 'demo', name)
    os.makedirs(out, exist_ok=True)
    data = [read_section(s) for s in snaps]
    sec_max = max(np.nanmax(np.hypot(Ur, Uz)) for _, Ur, Uz in data)
    frames = []
    for k, (s, (W, Ur, Uz)) in enumerate(zip(snaps, data)):
        tk = float(os.path.basename(os.path.dirname(s)))
        xk, xdk, Fk = (np.interp(tk, t, v) for v in (x, xd, F))
        phase = ((tk - t[0]) / T) % 1.0
        fig = plt.figure(figsize=(11.2, 3.9), dpi=90)
        gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 1.15], wspace=0.28, left=0.03, right=0.98, top=0.83, bottom=0.14)
        # --- left: piston and cylinder
        a0 = fig.add_subplot(gs[0])
        a0.set_xlim(-60, 60)
        a0.set_ylim(-30, 34)
        a0.axis('off')
        a0.add_patch(Rectangle((-45, -14), 90, 28, fill=False, lw=2, ec=STEEL))
        a0.add_patch(Rectangle((-44, -13), 88, 26, color=OIL, alpha=0.15, lw=0))
        px = 32 * xk / max(X_amp, 1e-9) * 0.5                   # exaggerated for visibility
        a0.add_patch(Rectangle((px - 3, -13), 6, 26, color=STEEL))
        a0.add_patch(Rectangle((-58, -2), 55 + px, 4, color=STEEL, alpha=0.85))
        sgn = 1 if xdk >= 0 else -1
        for yy in (-24, 24):                                    # oil leaving / entering through the coil
            a0.add_patch(FancyArrowPatch((-30 * sgn, yy), (30 * sgn, yy), arrowstyle='-|>', mutation_scale=14,
                                         lw=2.2, color=OIL, alpha=min(1, 0.25 + abs(xdk) / max(np.abs(xd)))))
        a0.text(0, 31, f'piston  x = {xk * 1e3:+.2f} mm   ẋ = {xdk:+.3f} m/s', ha='center', fontsize=9, color=INK)
        a0.text(0, -30, f'oil in coil: {xdk * p.A_p / A_c:+.2f} m/s  ({p.A_p / A_c:.0f}× piston)', ha='center', fontsize=8.5, color=OIL)
        # --- middle: cross-section
        a1 = fig.add_subplot(gs[1])
        section_axes(a1, W / v_amp, Ur, Uz, 1.6, 'Channel cross-section: oil speed + Dean vortices', lw_scale=sec_max)
        # --- right: force loop
        a2 = fig.add_subplot(gs[2])
        a2.plot(x * 1e3, F_ideal / 1e3, ':', color=STEEL, lw=1.6, label='ideal inerter (b·ẍ)')
        a2.plot(x * 1e3, F / 1e3, '-', color=OIL, lw=2, label='CFD (oil)')
        a2.plot([xk * 1e3], [Fk / 1e3], 'o', color=OIL, ms=9, mec=INK)
        a2.set_xlabel('piston displacement [mm]')
        a2.set_ylabel('piston force [kN]')
        a2.grid(alpha=0.3)
        a2.legend(fontsize=7.5, loc='lower left')
        a2.set_title('Force loop: area = energy lost to the oil', fontsize=9.5)
        fig.suptitle(f'Helical fluid inerter, {f:g} Hz, stroke ±{X_amp * 1e3:.1f} mm   |   phase {phase * 360:5.0f}°   '
                     f'|   Dean number now {abs(xdk) * p.A_p / A_c * info["d"] / NU * math.sqrt(r / R):4.0f}',
                     fontsize=11, color=INK, x=0.5, y=0.97)
        path = os.path.join(out, f'frame_{k:02d}.png')
        fig.savefig(path)
        plt.close(fig)
        frames.append(Image.open(path).convert('P', palette=Image.ADAPTIVE, colors=128))
        frames[-1].save(path, optimize=True)        # palette PNG: ~4x smaller, for the web player
    frames[0].save(os.path.join(res, 'demo', f'{name}.gif'), save_all=True, append_images=frames[1:],
                   duration=int(2400 / len(frames)), loop=0, optimize=True)
    print(f'{name}: {len(frames)} frames, stroke ±{X_amp * 1e3:.2f} mm -> {os.path.normpath(out)} and {name}.gif')
    return dict(name=name, freq=f, stroke_mm=round(X_amp * 1e3, 2), frames=len(frames))


def render_steady():
    cases = sorted(glob.glob(os.path.join(root, 'st_re*')))
    fig, axs = plt.subplots(1, len(cases), figsize=(3.6 * len(cases), 3.9), dpi=110)
    for ax, case in zip(np.atleast_1d(axs), cases):
        raw = glob.glob(os.path.join(case, 'postProcessing', 'section', '*', 'U_cyc1.raw'))[-1]
        W, Ur, Uz = read_section(raw)
        flux = [ln.split() for ln in open(glob.glob(os.path.join(case, 'postProcessing', 'flux', '*', 'surfaceFieldValue.dat'))[0])
                if ln.strip() and not ln.startswith('#')]
        ub = abs(float(flux[-1][1])) / A_mesh
        Re = ub * info['d'] / NU
        section_axes(ax, W / ub, Ur, Uz, 2.2, f'De = {Re * math.sqrt(r / R):.0f}  (Re = {Re:.0f})', cmap='YlOrBr')
    fig.suptitle('Steady flow in the curved channel: axial speed / bulk speed (colour) and Dean vortices (streamlines)',
                 fontsize=10.5)
    fig.tight_layout()
    path = os.path.join(res, 'dean_vortices.png')
    fig.savefig(path)
    print(f'steady figure -> {os.path.normpath(path)}')


if __name__ == '__main__':
    meta = [render_case(n) for n in ('osc_X2', 'osc_X5')]
    json.dump(meta, open(os.path.join(res, 'demo', 'demo_meta.json'), 'w'), indent=2)
    render_steady()
