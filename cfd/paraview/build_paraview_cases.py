"""Build ParaView-ready OpenFOAM cases from the project's CFD results.

    cfd/paraview/helix_steady_re1000/   full 5-turn helix, steady flow at Re = 1000 (U, p from S01)
    cfd/paraview/oscillating_helix/     2-turn helix, 24 time steps of one 10 Hz cycle (5 mm stroke)
    cfd/paraview/residuals_re1000.csv   solver residuals vs iteration (S01, Re = 1000)
    cfd/paraview/oscillation.csv        piston velocity, oil velocity and piston force vs time

The oscillating case uses the fully developed flow from the periodic torus sector (cfd/openfoam/
torus_demo/osc_X5): the cross-section velocity of each snapshot is placed on every slice of a helix
mesh with the same cross-section, rotated into the local helix frame. This is valid because the flow
is the same at every turn (torus vs full helix agree within 0.1 %); the small pitch is ignored.

Open them with open_in_paraview.py (see HOW_TO_RUN.md). Usage: python build_paraview_cases.py
"""
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import types

import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
proj = os.path.normpath(os.path.join(here, '..', '..'))
sys.path.insert(0, os.path.join(proj, 'cfd', 'scripts'))
import make_helix_mesh as M   # noqa: E402

home = subprocess.run(['wsl.exe', '-e', 'bash', '-c', 'wslpath -w ~'], capture_output=True, text=True).stdout
WSL = os.path.join(home.replace('\x00', '').strip(), 'inerter')
HDR = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    location    "{loc}";
    object      {obj};
}}
"""
CONTROL = """FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application simpleFoam; startFrom latestTime; startTime 0; stopAt endTime; endTime 1; deltaT 1;
writeControl timeStep; writeInterval 1; writeFormat ascii; writePrecision 6; timeFormat general; timePrecision 6;
"""


def latest_time(case):
    ts = [d for d in os.listdir(case) if d.replace('.', '', 1).isdigit() and d != '0']
    return max(ts, key=float)


def steady_helix():
    out = os.path.join(here, 'helix_steady_re1000')
    src = os.path.join(WSL, 's01', 're01000')
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(proj, 'cfd', 'openfoam', 's01', 'mesh', 'constant'), os.path.join(out, 'constant'))
    t = latest_time(src)
    os.makedirs(os.path.join(out, t))
    for f in ('U', 'p'):
        shutil.copy(os.path.join(src, t, f), os.path.join(out, t, f))
    os.makedirs(os.path.join(out, 'system'))
    open(os.path.join(out, 'system', 'controlDict'), 'w').write(CONTROL)
    open(os.path.join(out, 'case.foam'), 'w').close()
    # residuals -> clean CSV
    dat = glob.glob(os.path.join(src, 'postProcessing', 'solverInfo', '*', 'solverInfo.dat'))[0]
    lines = open(dat).read().splitlines()
    head = [ln for ln in lines if ln.startswith('#')][-1].lstrip('#').split('\t')
    head = [h.strip() for h in head if h.strip()]
    rows = [ln.split() for ln in lines if ln.strip() and not ln.startswith('#')]
    want = {'Ux_initial': 'Ux', 'Uy_initial': 'Uy', 'Uz_initial': 'Uz', 'p_initial': 'p'}
    idx = {v: head.index(k) for k, v in want.items() if k in head}
    with open(os.path.join(here, 'residuals_re1000.csv'), 'w') as fh:
        fh.write('iteration,' + ','.join(idx) + '\n')
        for r in rows:
            fh.write(r[0] + ',' + ','.join(r[i] for i in idx.values()) + '\n')
    print(f'steady helix: time {t}, residual columns {list(idx)} -> {out}')


def oscillating_helix(case_name='osc_X5', turns=2, per_turn=40, every=2):
    out = os.path.join(here, 'oscillating_helix')
    if os.path.isdir(out):
        shutil.rmtree(out)
    args = types.SimpleNamespace(d=6e-3, R=30e-3, pitch=10e-3, turns=turns, n=16, m=16, per_turn=per_turn,
                                 leg=0.01, leg_cells=1, torus=0.0, torus_cells=2, format='foam', out=out, flip=False)
    nodes, cells, cent, zones = M.build(args)
    M.write_foam(out, nodes, cent, zones)
    C, T, N, B, _ = M.centreline(args.R, args.pitch, turns, per_turn, args.leg * args.d, args.leg_cells)
    pts2d, quads, _ = M.cross_section(args.d / 2, args.n, args.m)
    q2, K = len(quads), len(C)
    # frame of each cell layer (mid between its two node slices)
    Tm, Nm = 0.5 * (T[:-1] + T[1:]), 0.5 * (N[:-1] + N[1:])
    Tm /= np.linalg.norm(Tm, axis=1)[:, None]
    Nm -= (Nm * Tm).sum(1)[:, None] * Tm
    Nm /= np.linalg.norm(Nm, axis=1)[:, None]
    Bm = np.cross(Tm, Nm)
    # torus-sector frame at the sampled patch cyc1 (theta = 10 deg)
    info = json.load(open(os.path.join(proj, 'cfd', 'openfoam', 'torus_demo', 'mesh', 'mesh_info.json')))
    th = math.radians(info['torus_deg'])
    Tt, Nt, Bt = np.array([-math.sin(th), math.cos(th), 0]), np.array([-math.cos(th), -math.sin(th), 0]), np.array([0, 0, 1.0])
    case = os.path.join(proj, 'cfd', 'openfoam', 'torus_demo', case_name)
    meta = json.load(open(os.path.join(case, 'case_info.json')))
    snaps = sorted(glob.glob(os.path.join(case, 'postProcessing', 'section', '*', 'U_cyc1.raw')),
                   key=lambda s: float(os.path.basename(os.path.dirname(s))))[-meta['frames']:][::every]
    t0 = float(os.path.basename(os.path.dirname(snaps[0])))
    # check: row i of the sampled patch must be the face of cross-section quad i
    xyz = np.loadtxt(snaps[0], comments='#')[:, :3]
    Ct = info['R_h'] * np.array([math.cos(th), math.sin(th), 0.0])
    qc = pts2d[quads].mean(axis=1)
    expect = Ct[None, :] + qc[:, 0, None] * Nt[None, :] + qc[:, 1, None] * Bt[None, :]
    err = np.linalg.norm(xyz - expect, axis=1).max()
    if err > 3e-5:
        raise SystemExit(f'sampled faces do not match the cross-section ordering (max offset {err:.2e} m)')
    print(f'face ordering check passed (max offset {err * 1e6:.1f} micrometres)')
    patch_cells = {'inlet': np.arange(q2), 'outlet': (K - 2) * q2 + np.arange(q2)}
    for s in snaps:
        U = np.loadtxt(s, comments='#')[:, 3:6]
        if len(U) != q2:
            raise SystemExit(f'{s}: {len(U)} faces, expected {q2} (cross-section mismatch)')
        a, b, c = U @ Tt, U @ Nt, U @ Bt                   # tangential / normal / binormal components
        Ucell = (a[None, :, None] * Tm[:, None, :] + b[None, :, None] * Nm[:, None, :]
                 + c[None, :, None] * Bm[:, None, :]).reshape(-1, 3)
        tname = f'{float(os.path.basename(os.path.dirname(s))) - t0:.6f}'
        d = os.path.join(out, tname)
        os.makedirs(d)
        with open(os.path.join(d, 'U'), 'w', newline='\n') as fh:
            fh.write(HDR.format(cls='volVectorField', loc=tname, obj='U'))
            fh.write(f'dimensions [0 1 -1 0 0 0 0];\ninternalField nonuniform List<vector>\n{len(Ucell)}\n(\n')
            np.savetxt(fh, Ucell, fmt='(%.5g %.5g %.5g)')
            fh.write(')\n;\nboundaryField\n{\n    wall { type noSlip; }\n')
            for pname, ids in patch_cells.items():
                fh.write(f'    {pname}\n    {{\n        type calculated;\n        value nonuniform List<vector>\n{len(ids)}\n(\n')
                np.savetxt(fh, Ucell[ids], fmt='(%.5g %.5g %.5g)')
                fh.write(')\n;\n    }\n')
            fh.write('}\n')
    os.makedirs(os.path.join(out, 'system'))
    open(os.path.join(out, 'system', 'controlDict'), 'w').write(CONTROL.replace('simpleFoam', 'pimpleFoam'))
    open(os.path.join(out, 'case.foam'), 'w').close()
    # kinematics CSV for a line chart
    rows = np.array([[float(v) for v in ln.split()[:2]] for ln in
                     open(glob.glob(os.path.join(case, 'postProcessing', 'flux', '*', 'surfaceFieldValue.dat'))[0])
                     if ln.strip() and not ln.startswith('#')])
    sel = rows[:, 0] >= t0 - 1e-9
    t, flux = rows[sel, 0] - t0, rows[sel, 1]
    A_mesh, A_c, A_p = info['inlet_area'], math.pi * 0.006 ** 2 / 4, math.pi * 0.04 ** 2 / 4
    u = -flux / A_mesh
    l = 10 * math.hypot(2 * math.pi * 0.03, 0.01)
    F = A_p * 870 * l * meta['G_amp'] * np.sin(2 * math.pi * meta['freq'] * (t + t0))
    with open(os.path.join(here, 'oscillation.csv'), 'w') as fh:
        fh.write('time,piston_velocity_mm_s,oil_velocity_m_s,piston_force_kN\n')
        for row in zip(t, u * A_c / A_p * 1e3, u, F / 1e3):
            fh.write(','.join(f'{v:.6g}' for v in row) + '\n')
    print(f'oscillating helix: {len(cent)} cells, {len(snaps)} time steps -> {out}')


if __name__ == '__main__':
    steady_helix()
    oscillating_helix()
