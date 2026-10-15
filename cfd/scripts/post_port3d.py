"""Post-process the 3D port cases (make_port3d_openfoam.py) and compare with the axisymmetric chamber CFD.

Mechanical energy per unit mass E = p/rho + |U|^2/2, flux-weighted over a section:
    piston                 surfaceFieldValue on the patch (weighted by phi)
    planes at 300, 450 mm  cutting planes through the helix (VTK), integrated here: E = sum(e u_n dA) / sum(u_n dA)
Developed helix loss gradient G (per metre of channel) from the OUT cases, whose recycled inlet delivers
fully developed helix flow to both planes: G = (E_450 - E_300) / 0.15 m.
Loss coefficients use the same definition as the 2D cases (post_chamber.py): the developed channel loss over
the 300 mm from the bore wall is subtracted, so K is the EXTRA loss of the port compared with a
developed channel of the same length (here: a developed HELIX, which the coil model already counts).
    K_in  = (E_piston - E_300 - 0.3 G) / (v^2/2)      (in cases: chamber -> port -> elbows -> helix)
    K_out = (E_300 - E_piston - 0.3 G) / (v^2/2)      (out cases: developed helix flow -> elbows -> port -> chamber)
Averages are taken over the last SNAPSHOTS plane samples; the spread shows any residual unsteadiness.

Writes cfd/results/port3d_losses.csv, port3d_summary.json, port3d_losses.png, port3d_flow.png.
Usage: python post_port3d.py      (after cfd/openfoam/run_in_wsl.sh port3d_coarse port3d)
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

here = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(here, '..', '..'))
OF = os.path.join(ROOT, 'cfd', 'openfoam')
RES = os.path.join(ROOT, 'cfd', 'results')
sys.path.insert(0, os.path.join(ROOT, 'python'))
import inerter_model as im   # noqa: E402

SNAPSHOTS = 6
OIL, ACC, GREY = '#c0392b', '#2471a3', '#7f8c8d'


# ------------------------------------------------------------------ readers
def read_vtk(path):
    """Legacy ASCII VTK polydata: points, polygons and cell data (p, U)."""
    tok = open(path).read().split()
    i, pts, polys, data = 0, None, [], {}
    while i < len(tok):
        t = tok[i]
        if t == 'POINTS':
            n = int(tok[i + 1])
            pts = np.array(tok[i + 3:i + 3 + 3 * n], float).reshape(n, 3)
            i += 3 + 3 * n
        elif t == 'POLYGONS':
            n, size = int(tok[i + 1]), int(tok[i + 2])
            i += 3
            if tok[i] == 'OFFSETS':                       # VTK 5.1 layout
                off = np.array(tok[i + 2:i + 2 + n], int)
                i += 2 + n
                assert tok[i] == 'CONNECTIVITY'
                conn = np.array(tok[i + 2:i + 2 + size], int)
                i += 2 + size
                polys = [conn[off[k]:off[k + 1]] for k in range(n - 1)]
            else:
                for _ in range(n):
                    k = int(tok[i])
                    polys.append(np.array(tok[i + 1:i + 1 + k], int))
                    i += 1 + k
        elif t == 'FIELD':
            m = int(tok[i + 2])
            i += 3
            for _ in range(m):
                name, nc, nt = tok[i], int(tok[i + 1]), int(tok[i + 2])
                data[name] = np.array(tok[i + 4:i + 4 + nc * nt], float).reshape(nt, nc).squeeze()
                i += 4 + nc * nt
        elif t in ('SCALARS', 'VECTORS'):
            name = tok[i + 1]
            i += 3
            if tok[i] == '1':
                i += 1
            if tok[i] == 'LOOKUP_TABLE':
                i += 2
            nc = 3 if t == 'VECTORS' else 1
            n = len(polys)
            data[name] = np.array(tok[i:i + nc * n], float).reshape(n, nc).squeeze()
            i += nc * n
        else:
            i += 1
    return pts, polys, data


def area_vectors(pts, polys):
    A = np.zeros((len(polys), 3))
    for k, f in enumerate(polys):
        q = pts[f]
        A[k] = 0.5 * np.cross(q - q[0], np.roll(q, -1, axis=0) - q[0]).sum(axis=0)
    return A


def plane_energy(path, normal):
    pts, polys, d = read_vtk(path)
    A = area_vectors(pts, polys)
    A *= np.sign(A @ normal)[:, None]                      # orient all faces along the plane normal
    un = d['U'] @ normal
    flux = un * np.linalg.norm(A, axis=1)
    e = d['p'] + 0.5 * np.sum(d['U'] ** 2, axis=1)
    return float(np.sum(e * flux) / np.sum(flux)), float(np.sum(flux)), float(np.linalg.norm(A, axis=1).sum())


def read_dat(path):
    rows = [ln.split() for ln in open(path) if ln.strip() and not ln.startswith('#')]
    return np.array(rows, float)


def fo_file(case, name):
    f = sorted(glob.glob(os.path.join(case, 'postProcessing', name, '*', '*.dat')))
    return f[-1] if f else None


# ------------------------------------------------------------------ one case
def analyse(case, info):
    ci = json.load(open(os.path.join(case, 'case_info.json')))
    sys.path.insert(0, here)
    import make_port3d_openfoam as g
    out = dict(ci)
    log = os.path.join(case, 'log.simpleFoam')
    out['finished'] = os.path.exists(log) and any(ln.startswith('End') for ln in open(log))
    snaps = sorted((d for d in glob.glob(os.path.join(case, 'postProcessing', 'planes', '*')) if os.path.isdir(d)),
                   key=lambda d: float(os.path.basename(d)))
    if not snaps:
        return None
    use = snaps[-SNAPSHOTS:]
    E = {}
    for s in info['planes']:
        name = f'plane{int(round(s * 1e3))}'
        n = g.helix_tangent(g.theta_of_s(s))
        vals = [plane_energy(glob.glob(os.path.join(d, f'{name}*.vtk'))[0], n) for d in use]
        E[name] = np.array([v[0] for v in vals])
        out[f'area_{name}'] = vals[-1][2]
        out[f'Q_{name}'] = vals[-1][1]
    it = [float(os.path.basename(d)) for d in use]
    ep = read_dat(fo_file(case, 'e_piston'))
    Ep = np.array([np.interp(t, ep[:, 0], ep[:, 1] + 0.5 * ep[:, 2]) for t in it])
    qp = read_dat(fo_file(case, 'q_piston'))
    out.update(iters=it, E_piston=Ep.tolist(), E300=E['plane300'].tolist(), E450=E['plane450'].tolist(),
               Q_piston=float(qp[-1, 1]), n_iter=float(ep[-1, 0]))
    return out


def main():
    rows, summary = [], {}
    for set_name, mesh in (('port3d', 'fine'), ('port3d_coarse', 'coarse')):
        root = os.path.join(OF, set_name)
        if not os.path.isdir(root):
            continue
        info = json.load(open(os.path.join(root, 'mesh', 'mesh_info.json')))
        cells = None
        lg = os.path.join(root, 'log.Allrun')                   # Allrun echoes the checkMesh cell count
        if os.path.exists(lg):
            for ln in open(lg):
                if ln.strip().startswith('cells:'):
                    cells = int(ln.split()[1])
        res = {}
        for case in sorted(glob.glob(os.path.join(root, '*_re*'))):
            r = analyse(case, info)
            if r:
                res[(r['direction'], r['Re'])] = r
        for (direction, Re), r in sorted(res.items()):
            v = r['v_tube']
            hv = 0.5 * v * v
            o = res.get(('out', Re))
            if o is None:
                continue
            G = (np.mean(o['E450']) - np.mean(o['E300'])) / 0.15
            if direction == 'in':
                Kraw = (np.array(r['E_piston']) - np.array(r['E300'])) / hv
                G_here = (np.mean(r['E300']) - np.mean(r['E450'])) / 0.15
            else:
                Kraw = (np.array(r['E300']) - np.array(r['E_piston'])) / hv
                G_here = G
            K = Kraw - 0.3 * G / hv
            f_dev = G * info['d'] / hv
            f_ito = float(im.friction_factor_helical(Re, info['r_t'] / info['R_h'])[0])
            rows.append(dict(mesh=mesh, cells=cells, direction=direction, Re=Re, K=float(np.mean(K)),
                             K_spread=float(np.ptp(K)), f_developed=f_dev, f_ito=f_ito,
                             G_ratio_here=G_here / G, iterations=r['n_iter'], finished=r['finished'],
                             Q_ratio=abs(r['Q_piston']) / (v * info['A_c'])))
    if not rows:
        print('no results yet')
        return
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, 'port3d_losses.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{"mesh":<7}{"dir":<5}{"Re":>6}{"K":>8}{"spread":>8}{"f_dev/f_Ito":>12}{"G/G_dev":>9}{"iters":>7}')
    for r in rows:
        print(f'{r["mesh"]:<7}{r["direction"]:<5}{r["Re"]:>6}{r["K"]:8.3f}{r["K_spread"]:8.3f}'
              f'{r["f_developed"] / r["f_ito"]:12.3f}{r["G_ratio_here"]:9.3f}{r["iterations"]:7.0f}')

    # comparison with the axisymmetric chamber CFD
    ch = json.load(open(os.path.join(RES, 'chamber_summary.json')))
    fine = [r for r in rows if r['mesh'] == 'fine']
    summary = dict(
        K_in_3d={str(r['Re']): r['K'] for r in fine if r['direction'] == 'in'},
        K_out_3d={str(r['Re']): r['K'] for r in fine if r['direction'] == 'out'},
        K_in_2d=ch['K_in'], K_out_2d=ch['K_out'],
        mesh_check=[dict(direction=r['direction'], Re=r['Re'], K_coarse=r['K'],
                         K_fine=next((q['K'] for q in fine if q['direction'] == r['direction'] and q['Re'] == r['Re']), None))
                    for r in rows if r['mesh'] == 'coarse'],
        f_developed_over_ito={str(r['Re']): r['f_developed'] / r['f_ito'] for r in fine if r['direction'] == 'out'},
        cells={r['mesh']: r['cells'] for r in rows})
    for key in ('in', 'out'):
        k3 = [summary[f'K_{key}_3d'][k] for k in ('250', '500') if k in summary[f'K_{key}_3d']]
        summary[f'K_{key}_3d_operating'] = float(np.mean(k3)) if k3 else None
    if summary['K_in_3d_operating'] is not None and summary['K_out_3d_operating'] is not None:
        summary['K_tot_3d_operating'] = summary['K_in_3d_operating'] + summary['K_out_3d_operating']
    json.dump(summary, open(os.path.join(RES, 'port3d_summary.json'), 'w'), indent=2)

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for key, col, lab in (('in', ACC, 'Entry (chamber → channel)'), ('out', OIL, 'Exit (channel → chamber)')):
        r2 = ch[f'K_{key}']
        ax.semilogx([float(k) for k in r2], list(r2.values()), 'o--', color=col, mfc='white', label=f'{lab}, 2D axisymmetric')
        r3 = summary[f'K_{key}_3d']
        if r3:
            ax.semilogx([float(k) for k in r3], list(r3.values()), 's-', color=col, label=f'{lab}, 3D radial port + elbows')
        rc = [r for r in rows if r['mesh'] == 'coarse' and r['direction'] == key]
        ax.semilogx([r['Re'] for r in rc], [r['K'] for r in rc], 'x', color=col, ms=8)
    ax.axhline(1.0, color=GREY, lw=0.8, ls=':')
    ax.axhline(0.5, color=GREY, lw=0.8, ls=':')
    ax.set(xlabel='Channel Reynolds number', ylabel='Loss coefficient K (velocity heads)',
           title='Port losses: 3D drilled port vs 2D axisymmetric (× = coarse 3D mesh)')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(fontsize=7.5)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'port3d_losses.png'), dpi=160)
    plt.close(fig)

    # flow pictures: velocity magnitude on the z = 0 mid-plane, in and out, Re 500
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, key in zip(axs, ('in', 'out')):
        case = os.path.join(OF, 'port3d', f'{key}_re00500')
        f = sorted(glob.glob(os.path.join(case, 'postProcessing', 'views', '*', 'midplane*.vtk')))
        if not f:
            ax.set_visible(False)
            continue
        pts, polys, d = read_vtk(f[-1])
        cen = np.array([pts[p].mean(axis=0) for p in polys])
        v = json.load(open(os.path.join(case, 'case_info.json')))['v_tube']
        U = np.linalg.norm(d['U'], axis=1) / v
        tri = mtri.Triangulation(cen[:, 0] * 1e3, cen[:, 1] * 1e3)
        h = np.array([math.sqrt(max(np.linalg.norm(area_vectors(pts, [p])[0]), 1e-30)) for p in polys]) * 1e3
        q = np.c_[tri.x, tri.y][tri.triangles]                    # (n, 3, 2)
        edge = np.max(np.linalg.norm(q - np.roll(q, 1, axis=1), axis=2), axis=1)
        bad = edge > 2.2 * h[tri.triangles].max(axis=1)             # bridges across walls / between coil sections
        tri.set_mask(bad)
        cs = ax.tricontourf(tri, U, levels=np.linspace(0, 1.6, 33), cmap='inferno', extend='max')
        ax.set_aspect('equal')
        ax.set(xlabel='x along the bore [mm]', ylabel='y [mm]',
               title=('Piston pushes oil into the port' if key == 'in' else 'Oil from the coil jets into the chamber') + ', Re 500')
        fig.colorbar(cs, ax=ax, shrink=0.8, label='|U| / channel bulk speed')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'port3d_flow.png'), dpi=160)
    plt.close(fig)
    print('wrote port3d_losses.csv, port3d_summary.json, port3d_losses.png, port3d_flow.png')


if __name__ == '__main__':
    main()
