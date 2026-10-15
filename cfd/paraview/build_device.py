"""3D model of the whole fluid inerter (J-damper) for ParaView, animated with the CFD cycle.

Writes cfd/paraview/device/:
    housing.vtp, caps.vtp      static parts (cylinder barrel, end caps)
    piston.pvd   (+ .vtp)      piston and through-rod, moving with the CFD piston motion
    chambers.pvd (+ .vtp)      oil in the two chambers, coloured by pressure [MPa]
    coil.pvd     (+ .vtp)      oil in the helical channel and ports, coloured by oil velocity [m/s]

The time values are the same as cfd/paraview/oscillating_helix (one 10 Hz cycle, 24 steps), so
pressing Play in ParaView moves the piston in step with the CFD flow. Piston motion, oil velocity and
force come from cfd/paraview/oscillation.csv (torus CFD, case osc_X5). Chamber pressures are
+-F/(2 A_p) about the charge pressure (antisymmetric double-acting device).

Dimensions: bore 40 mm, rod 12 mm, piston 12 mm thick, channel 6 mm on a 30 mm radius helix,
10 turns at 10 mm pitch (1.888 m). The barrel and caps are illustrative. Usage: python build_device.py
"""
import glob
import math
import os

import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, 'device')
mm = 1e-3
R_BORE, R_BARREL, R_ROD = 20 * mm, 26 * mm, 6 * mm
L_HALF = 60 * mm                    # chambers span x = -60..60 mm
T_PISTON = 12 * mm
R_HELIX, PITCH, TURNS, R_CH = 30 * mm, 10 * mm, 10, 3 * mm
A_P = math.pi * R_BORE ** 2


# ------------------------------------------------------------------ tiny VTK XML writer
def write_vtp(path, pts, polys, point_data=None):
    pts = np.asarray(pts, float)
    conn = np.concatenate([np.asarray(p, int) for p in polys])
    offs = np.cumsum([len(p) for p in polys])
    pd = ''
    if point_data:
        arrs = ''.join(f'<DataArray type="Float32" Name="{k}" format="ascii">{" ".join(f"{x:.5g}" for x in v)}</DataArray>'
                       for k, v in point_data.items())
        pd = f'<PointData Scalars="{next(iter(point_data))}">{arrs}</PointData>'
    with open(path, 'w') as fh:
        fh.write('<?xml version="1.0"?>\n<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">\n'
                 f'<PolyData><Piece NumberOfPoints="{len(pts)}" NumberOfPolys="{len(polys)}">{pd}'
                 '<Points><DataArray type="Float32" NumberOfComponents="3" format="ascii">'
                 + ' '.join(f'{x:.6g}' for x in pts.ravel()) + '</DataArray></Points>'
                 '<Polys><DataArray type="Int32" Name="connectivity" format="ascii">'
                 + ' '.join(map(str, conn)) + '</DataArray>'
                 '<DataArray type="Int32" Name="offsets" format="ascii">'
                 + ' '.join(map(str, offs)) + '</DataArray></Polys></Piece></PolyData></VTKFile>\n')


def write_pvd(path, entries):
    with open(path, 'w') as fh:
        fh.write('<?xml version="1.0"?>\n<VTKFile type="Collection" version="0.1">\n<Collection>\n')
        for t, f in entries:
            fh.write(f'  <DataSet timestep="{t:.8g}" part="0" file="{f}"/>\n')
        fh.write('</Collection>\n</VTKFile>\n')


class Mesh:
    """Accumulates surface pieces (points, quads/polygons, per-point scalars)."""
    def __init__(self):
        self.pts, self.polys, self.vals = [], [], []

    def add(self, pts, polys, val=0.0):
        n0 = len(self.pts)
        self.pts += list(pts)
        self.polys += [[n0 + i for i in p] for p in polys]
        self.vals += list(val) if np.ndim(val) else [val] * len(pts)

    def write(self, path, name=None):
        write_vtp(path, self.pts, self.polys, {name: self.vals} if name else None)


def ring_x(x, r, n=48):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.c_[np.full(n, x), r * np.cos(a), r * np.sin(a)]


def tube_x(m, x0, x1, r, val=0.0, n=48):
    """Cylinder side surface along x."""
    pts = np.vstack([ring_x(x0, r, n), ring_x(x1, r, n)])
    m.add(pts, [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)], val)


def annulus_x(m, x, r0, r1, val=0.0, n=48):
    pts = np.vstack([ring_x(x, r0, n), ring_x(x, r1, n)])
    m.add(pts, [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)], val)


def sweep(m, path, r, vals, n=12):
    """Tube of radius r swept along a polyline path (N x 3), per-station scalar vals."""
    path = np.asarray(path)
    tang = np.gradient(path, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    ref = np.array([1.0, 0, 0]) if abs(tang[0, 0]) < 0.9 else np.array([0, 0, 1.0])
    pts, pv = [], []
    for k, (p, t) in enumerate(zip(path, tang)):
        u = np.cross(t, ref); u /= np.linalg.norm(u)
        w = np.cross(t, u)
        ref = u                                           # parallel transport (no twisting)
        a = np.linspace(0, 2 * np.pi, n, endpoint=False)
        pts += list(p + r * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * w))
        pv += [vals[k]] * n
    polys = [[k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i]
             for k in range(len(path) - 1) for i in range(n)]
    m.add(pts, polys, pv)


def coil_path():
    """Port A (left chamber) -> helix (10 turns around the barrel) -> port B (right chamber)."""
    x_end = TURNS * PITCH / 2
    s = np.linspace(0, TURNS * 2 * np.pi, TURNS * 64 + 1)
    helix = np.c_[-x_end + PITCH * s / (2 * np.pi), R_HELIX * np.cos(s), R_HELIX * np.sin(s)]
    xa, xb = -L_HALF + 4 * mm, L_HALF - 4 * mm           # ports drilled radially near the end caps
    port_a = [[xa, r, 0] for r in np.linspace(R_BORE - 1 * mm, R_HELIX, 6)] + \
             [[x, R_HELIX, 0] for x in np.linspace(xa, -x_end, 6)[1:-1]]
    c, s_ = math.cos(s[-1]), math.sin(s[-1])
    port_b = [[x, R_HELIX * c, R_HELIX * s_] for x in np.linspace(x_end, xb, 6)[1:-1]] + \
             [[xb, r * c, r * s_] for r in np.linspace(R_HELIX, R_BORE - 1 * mm, 6)]
    return np.vstack([port_a, helix, port_b])


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, '*')):
        os.remove(f)
    # --- kinematics from the CFD cycle
    d = np.genfromtxt(os.path.join(here, 'oscillation.csv'), delimiter=',', names=True)
    t_csv, xd, u_oil, F = d['time'], d['piston_velocity_mm_s'] * 1e-3, d['oil_velocity_m_s'], d['piston_force_kN'] * 1e3
    x = np.concatenate([[0], np.cumsum(0.5 * (xd[1:] + xd[:-1]) * np.diff(t_csv))])
    x -= 0.5 * (x.max() + x.min())                        # centre the stroke
    times = sorted(float(os.path.basename(p)) for p in glob.glob(os.path.join(here, 'oscillating_helix', '0.*')))
    period = t_csv[-1] + (t_csv[1] - t_csv[0])

    def at(arr, t):
        return float(np.interp(t % period, t_csv, arr, period=period))

    # --- static parts
    h = Mesh()
    tube_x(h, -L_HALF, L_HALF, R_BORE)                    # bore surface
    tube_x(h, -L_HALF, L_HALF, R_BARREL)                  # barrel outside
    h.write(os.path.join(OUT, 'housing.vtp'))
    c = Mesh()
    for s in (-1, 1):
        x0, x1 = s * L_HALF, s * (L_HALF + 10 * mm)
        annulus_x(c, x0, R_ROD + 0.5 * mm, R_HELIX + 6 * mm)
        annulus_x(c, x1, R_ROD + 0.5 * mm, R_HELIX + 6 * mm)
        tube_x(c, x0, x1, R_HELIX + 6 * mm)
    c.write(os.path.join(OUT, 'caps.vtp'))

    path = coil_path()
    entries = {'piston': [], 'chambers': [], 'coil': []}
    for k, t in enumerate(times):
        xp, F_t, u_t = at(x, t), at(F, t), at(u_oil, t)
        # piston + through-rod
        p = Mesh()
        x0, x1 = xp - T_PISTON / 2, xp + T_PISTON / 2
        tube_x(p, x0, x1, R_BORE - 0.3 * mm)
        annulus_x(p, x0, R_ROD, R_BORE - 0.3 * mm)
        annulus_x(p, x1, R_ROD, R_BORE - 0.3 * mm)
        tube_x(p, -L_HALF - 45 * mm + xp, L_HALF + 45 * mm + xp, R_ROD)
        for s in (-1, 1):                                  # rod-end eyes
            xe = s * (L_HALF + 45 * mm) + xp
            annulus_x(p, xe, 0, R_ROD)
        fp = f'piston_{k:02d}.vtp'
        p.write(os.path.join(OUT, fp))
        # oil in the chambers: + side (left, pushed by positive piston velocity) and - side
        dp = F_t / (2 * A_P) / 1e6
        ch = Mesh()
        for (xa, xb, val) in [(-L_HALF, x0, +dp), (x1, L_HALF, -dp)]:
            tube_x(ch, xa, xb, R_BORE - 0.6 * mm, val)
            tube_x(ch, xa, xb, R_ROD + 0.4 * mm, val)
            annulus_x(ch, xa, R_ROD + 0.4 * mm, R_BORE - 0.6 * mm, val)
            annulus_x(ch, xb, R_ROD + 0.4 * mm, R_BORE - 0.6 * mm, val)
        fc = f'chambers_{k:02d}.vtp'
        ch.write(os.path.join(OUT, fc), 'pressure_MPa')
        # oil in the coil: bulk velocity (positive = from the left chamber towards the right one)
        co = Mesh()
        sweep(co, path, R_CH, np.full(len(path), u_t))
        fo = f'coil_{k:02d}.vtp'
        co.write(os.path.join(OUT, fo), 'oil_velocity_m_s')
        for name, fn in (('piston', fp), ('chambers', fc), ('coil', fo)):
            entries[name].append((t, fn))
    for name, e in entries.items():
        write_pvd(os.path.join(OUT, f'{name}.pvd'), e)
    print(f'device model: {len(times)} time steps, stroke {1e3 * (x.max() - x.min()):.1f} mm, '
          f'peak chamber pressure {np.abs(F).max() / (2 * A_P) / 1e6:.2f} MPa, peak oil speed {np.abs(u_oil).max():.1f} m/s -> {OUT}')


if __name__ == '__main__':
    main()
