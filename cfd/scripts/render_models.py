"""Render pictures of every model built in the project (geometry, meshes, suspension networks).

Writes to cfd/results/models/:
    01_helix_geometry.png     full helical channel used for the steady validation (5 turns + legs)
    02_cross_section_meshes.png  O-grid cross-section meshes: coarse / medium / fine (GCI study)
    03_mesh_detail.png        structured hex mesh on the helix wall, close-up
    04_torus_sector.png       periodic 10 deg torus sector used for the oscillating-flow cases
    05_suspension_layouts.png quarter-car model and suspension layouts L1-L4
Usage: python render_models.py
"""
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import make_helix_mesh as M   # noqa: E402

OUT = os.path.join(here, '..', 'results', 'models')
os.makedirs(OUT, exist_ok=True)
INK, OIL, STEEL, MUTED, LIGHT = '#14202b', '#b26d10', '#2c6496', '#566472', '#f3e6d0'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9})
d, R, pitch = 6e-3, 30e-3, 10e-3


def tube(C, N, B, r, nth=40):
    th = np.linspace(0, 2 * np.pi, nth)
    return [C[:, k][:, None] + r * (np.cos(th)[None, :] * N[:, k][:, None] + np.sin(th)[None, :] * B[:, k][:, None])
            for k in range(3)]


def set_equal_3d(ax, X, Y, Z):
    mx = max(np.ptp(X), np.ptp(Y), np.ptp(Z)) / 2
    cx, cy, cz = (np.max(X) + np.min(X)) / 2, (np.max(Y) + np.min(Y)) / 2, (np.max(Z) + np.min(Z)) / 2
    ax.set_xlim(cx - mx, cx + mx); ax.set_ylim(cy - mx, cy + mx); ax.set_zlim(cz - mx, cz + mx)


def helix_geometry():
    C, T, N, B, ts = M.centreline(R, pitch, 5, 60, 5 * d, 6)
    X, Y, Z = (a * 1e3 for a in tube(C, N, B, d / 2))
    fig = plt.figure(figsize=(9, 6.2), dpi=120)
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(X, Y, Z, color=OIL, alpha=0.85, linewidth=0, shade=True, rstride=1, cstride=2)
    ax.plot(*(C.T * 1e3), color=INK, lw=0.8, ls='--')
    for k, lab in ((0, 'inlet'), (len(C) - 1, 'outlet')):
        ax.text(*(C[k] * 1e3 + np.array([0, 0, 6])), lab, color=INK, fontsize=9)
    ax.set_xlabel('x [mm]'); ax.set_ylabel('y [mm]'); ax.set_zlabel('z [mm]')
    set_equal_3d(ax, X, Y, Z)
    ax.view_init(elev=18, azim=-60)
    ax.set_title('Model 1: full helical channel (steady validation, S01 + GCI)\n'
                 'd = 6 mm, coil radius 30 mm, pitch 10 mm, 5 turns + 30 mm straight legs (0.38M hex cells)',
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, '01_helix_geometry.png'))
    plt.close(fig)


def cross_sections():
    fig, axs = plt.subplots(1, 3, figsize=(12, 4.4), dpi=120)
    for ax, (lab, n, cells) in zip(axs, (('Coarse', 9, '160,785'), ('Medium', 12, '381,600'), ('Fine', 16, '902,400'))):
        pts, quads, _ = M.cross_section(3.0, n, n)
        polys = pts[quads]
        ax.add_collection(PolyCollection(polys, facecolor=LIGHT, edgecolor=INK, linewidth=0.35))
        ax.add_patch(plt.Circle((0, 0), 3.0, fill=False, lw=1.6, color=OIL))
        ax.set_xlim(-3.2, 3.2); ax.set_ylim(-3.2, 3.2); ax.set_aspect('equal'); ax.axis('off')
        ax.set_title(f'{lab}: {len(quads)} cells per slice\n({cells} cells in the full helix)', fontsize=10)
    fig.suptitle('Model 2: structured O-grid cross-section (central block + 4 blocks graded toward the wall), '
                 'refinement ratio 1.33', fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, '02_cross_section_meshes.png'))
    plt.close(fig)


def mesh_detail():
    pts, quads, wall = M.cross_section(d / 2, 12, 12)
    C, T, N, B, _ = M.centreline(R, pitch, 1, 100, 0.0, 1)
    C, T, N, B = C[1:9], T[1:9], N[1:9], B[1:9]                     # a short stretch (~25 deg) of one turn
    Lw = [e[0] for e in wall]
    ring = pts[Lw]                                                  # wall nodes around the section
    P = C[:, None, :] + ring[None, :, 0, None] * N[:, None, :] + ring[None, :, 1, None] * B[:, None, :]
    P *= 1e3
    faces = []
    nW = len(Lw)
    for k in range(len(C) - 1):
        for j in range(nW):
            jn = (j + 1) % nW
            faces.append([P[k, j], P[k, jn], P[k + 1, jn], P[k + 1, j]])
    sec = C[-1][None, :] + pts[:, 0, None] * N[-1][None, :] + pts[:, 1, None] * B[-1][None, :]
    sec *= 1e3
    fig = plt.figure(figsize=(9, 6), dpi=120)
    ax = fig.add_subplot(111, projection='3d')
    ax.add_collection3d(Poly3DCollection(faces, facecolor=OIL, edgecolor=INK, linewidths=0.25, alpha=0.55))
    ax.add_collection3d(Poly3DCollection([sec[q] for q in quads], facecolor=LIGHT, edgecolor=INK, linewidths=0.3))
    allp = np.vstack([P.reshape(-1, 3), sec])
    set_equal_3d(ax, allp[:, 0], allp[:, 1], allp[:, 2])
    ax.view_init(elev=12, azim=-20)
    ax.set_axis_off()
    ax.set_title('Model 2 (detail): hex cells swept along the helix with Frenet frames\n'
                 'wall grid + end cross-section; first cell at the wall about 0.04 mm', fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, '03_mesh_detail.png'))
    plt.close(fig)


def torus_sector():
    pts, quads, wall = M.cross_section(d / 2, 16, 16)
    C, T, N, B, _ = M.centreline_torus(R, 10.0, 2)
    Lw = [e[0] for e in wall]
    ring = pts[Lw]
    P = (C[:, None, :] + ring[None, :, 0, None] * N[:, None, :] + ring[None, :, 1, None] * B[:, None, :]) * 1e3
    faces = [[P[k, j], P[k, (j + 1) % len(Lw)], P[k + 1, (j + 1) % len(Lw)], P[k + 1, j]]
             for k in range(len(C) - 1) for j in range(len(Lw))]
    secs = [(C[k][None, :] + pts[:, 0, None] * N[k][None, :] + pts[:, 1, None] * B[k][None, :]) * 1e3 for k in (0, len(C) - 1)]
    fig = plt.figure(figsize=(9, 6), dpi=120)
    ax = fig.add_subplot(111, projection='3d')
    ax.add_collection3d(Poly3DCollection(faces, facecolor=OIL, edgecolor=INK, linewidths=0.2, alpha=0.35))
    for s, col in zip(secs, (STEEL, STEEL)):
        ax.add_collection3d(Poly3DCollection([s[q] for q in quads], facecolor=LIGHT, edgecolor=col, linewidths=0.25))
    th = np.linspace(0, 2 * np.pi, 200)                              # ghost of the full coil for context
    ax.plot(R * 1e3 * np.cos(th), R * 1e3 * np.sin(th), 0 * th, color=MUTED, lw=0.8, ls=':')
    ax.text(*(secs[0].mean(axis=0) + np.array([4, -4, 4])), 'cyc0', color=STEEL)
    ax.text(*(secs[1].mean(axis=0) + np.array([-4, 4, 4])), 'cyc1', color=STEEL)
    allp = np.vstack([P.reshape(-1, 3)] + secs)
    set_equal_3d(ax, allp[:, 0], allp[:, 1], allp[:, 2])
    ax.view_init(elev=28, azim=-35)
    ax.set_axis_off()
    ax.set_title('Model 3: periodic 10° torus sector (oscillating-flow cases)\n'
                 '2,560 cells; the two blue faces are linked (cyclic), so the flow repeats as in an endless coil;\n'
                 'an oscillating pressure jump between them drives the oil', fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, '04_torus_sector.png'))
    plt.close(fig)


# ---------------- suspension network drawings ----------------
def spring(ax, x, y0, y1, w=0.25, n=6, color=INK):
    ys = np.linspace(y0, y1, 2 * n + 3)
    xs = [x] + [x + (w if i % 2 else -w) for i in range(2 * n + 1)] + [x]
    ys = np.concatenate([[y0], np.linspace(y0 + 0.15 * (y1 - y0), y1 - 0.15 * (y1 - y0), 2 * n + 1), [y1]])
    ax.plot(xs, ys, color=color, lw=1.4)


def damper(ax, x, y0, y1, w=0.28, color=INK):
    ym = (y0 + y1) / 2
    ax.plot([x, x], [y0, ym - 0.05], color=color, lw=1.4)
    ax.plot([x - w, x - w, x + w, x + w], [ym + 0.35, ym - 0.25, ym - 0.25, ym + 0.35], color=color, lw=1.4)
    ax.plot([x - w * 0.7, x + w * 0.7], [ym + 0.05, ym + 0.05], color=color, lw=2.2)
    ax.plot([x, x], [ym + 0.05, y1], color=color, lw=1.4)


def inerter(ax, x, y0, y1, w=0.3, color=OIL):
    ym = (y0 + y1) / 2
    ax.plot([x, x], [y0, ym - 0.3], color=color, lw=1.6)
    ax.add_patch(plt.Rectangle((x - w, ym - 0.3), 2 * w, 0.6, fill=False, ec=color, lw=1.6))
    ax.plot([x - w * 0.6, x + w * 0.6], [ym + 0.12, ym - 0.12], color=color, lw=1.2)
    ax.plot([x - w * 0.6, x + w * 0.6], [ym - 0.12, ym + 0.12], color=color, lw=1.2)
    ax.plot([x, x], [ym + 0.3, y1], color=color, lw=1.6)


def series(ax, x, y0, y1, parts):
    """Draw elements in series between y0 and y1 at x."""
    ys = np.linspace(y0, y1, len(parts) + 1)
    for (fn, kw), a, b in zip(parts, ys[:-1], ys[1:]):
        fn(ax, x, a, b, **kw)


def quarter_car(ax, title, branches):
    """branches: list of callables(ax, x, y0, y1) placed side by side between the two masses."""
    ax.set_xlim(-2.4, 2.4); ax.set_ylim(-0.6, 7.3); ax.axis('off')
    ax.add_patch(plt.Rectangle((-1.8, 5.2), 3.6, 1.0, fc=LIGHT, ec=INK, lw=1.4))
    ax.text(0, 5.7, 'sprung mass  m_s = 250 kg', ha='center', va='center', fontsize=8)
    ax.add_patch(plt.Rectangle((-1.2, 1.6), 2.4, 0.8, fc=LIGHT, ec=INK, lw=1.4))
    ax.text(0, 2.0, 'unsprung  m_u = 35 kg', ha='center', va='center', fontsize=8)
    xs = np.linspace(-1.3, 1.3, len(branches)) if len(branches) > 1 else [0]
    ax.plot([xs[0], xs[-1]], [2.6, 2.6], color=INK, lw=1.2); ax.plot([xs[0], xs[-1]], [5.0, 5.0], color=INK, lw=1.2)
    ax.plot([0, 0], [2.4, 2.6], color=INK, lw=1.2); ax.plot([0, 0], [5.0, 5.2], color=INK, lw=1.2)
    for x, br in zip(xs, branches):
        br(ax, x, 2.6, 5.0)
    spring(ax, 0, 0.2, 1.6, w=0.2, n=4)                            # tyre
    ax.text(0.35, 0.9, 'tyre k_t', fontsize=8, color=MUTED)
    ax.plot(np.linspace(-2, 2, 50), 0.12 * np.sin(np.linspace(0, 9, 50)), color=MUTED, lw=1.5)
    ax.text(-2.3, -0.45, 'road z_r (ISO 8608)', fontsize=8, color=MUTED)
    ax.set_title(title, fontsize=9.5)


def suspension_layouts():
    k = lambda ax, x, a, b: spring(ax, x, a, b)
    c = lambda ax, x, a, b: damper(ax, x, a, b)
    bi = lambda ax, x, a, b: inerter(ax, x, a, b)
    c_ser_b = lambda ax, x, a, b: series(ax, x, a, b, [(damper, {}), (inerter, {})])
    jbranch = lambda ax, x, a, b: series(ax, x, a, b, [(spring, dict(n=3)), (damper, {}), (inerter, {})])
    fig, axs = plt.subplots(1, 4, figsize=(13, 5), dpi=120)
    quarter_car(axs[0], 'L1: conventional\nspring ‖ damper', [k, c])
    quarter_car(axs[1], 'L2: parallel inerter\n(no grip benefit)', [k, c, bi])
    quarter_car(axs[2], 'L3: damper–inerter in series\n(3.1 % ideal, 0 % with oil losses)', [k, c_ser_b])
    quarter_car(axs[3], 'L4: J-damper branch\n(8.7 % ideal, 5.0 % with CFD inerter)', [k, c, jbranch])
    fig.suptitle('Model 4: quarter-car suspension networks (black = spring/damper, orange = inerter = fluid inerter in the CFD study)',
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, '05_suspension_layouts.png'))
    plt.close(fig)


if __name__ == '__main__':
    for fn in (helix_geometry, cross_sections, mesh_detail, torus_sector, suspension_layouts):
        fn()
        print('rendered', fn.__name__)
    print('->', os.path.normpath(OUT))
