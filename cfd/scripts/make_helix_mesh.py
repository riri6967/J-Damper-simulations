"""Structured O-grid hex mesh of the helical inerter channel, written as an OpenFOAM
polyMesh (default) or a Fluent ASCII .msh.

The cross-section (an O-grid: central square block + 4 graded outer blocks) is swept
along the helix centreline using its Frenet frame. Straight tangent legs are added at
both ends. Internal face zones `turn0` ... `turnN` mark the start of every helix turn,
so Fluent can report section-averaged pressure there (fully developed dp/ds).

Usage:
    python make_helix_mesh.py --out CASE_DIR                 (OpenFOAM: CASE_DIR/constant/polyMesh)
    python make_helix_mesh.py --format fluent --out FILE.msh
    options: [--n 12] [--m 12] [--per-turn 100] [--turns 5]
A mesh_info.json (discrete inlet area, turn arc length) is written next to the output.

Refinement for the GCI study: scale n, m and per-turn together by r = 1.3-1.5.
Geometry defaults match matlab/inerter_params.m (d = 6 mm, R_h = 30 mm, pitch = 10 mm).
Units: metres.
"""
import argparse
import json
import os

import numpy as np


def cross_section(r, n, m, a_frac=0.45, beta=1.6):
    """O-grid of a circle of radius r. n = cells per square side, m = radial cells in
    the outer ring (graded toward the wall). Returns (pts2d [N,2], quads [Q,4], wall_edges)."""
    a = a_frac * r
    # square block nodes (i, j) -> id i*(n+1)+j
    g = np.linspace(-a, a, n + 1)
    sq = np.array([(x, y) for x in g for y in g])
    sid = lambda i, j: i * (n + 1) + j
    quads = [(sid(i, j), sid(i + 1, j), sid(i + 1, j + 1), sid(i, j + 1))
             for i in range(n) for j in range(n)]

    # square perimeter, CCW starting at (a, -a)
    perim = []
    perim += [sid(n, j) for j in range(n)]            # right side, upward
    perim += [sid(i, n) for i in range(n, 0, -1)]     # top, leftward
    perim += [sid(0, j) for j in range(n, 0, -1)]     # left, downward
    perim += [sid(i, 0) for i in range(n)]            # bottom, rightward
    P = 4 * n
    theta = -np.pi / 4 + np.arange(P) * (np.pi / 2) / n
    circ = r * np.column_stack([np.cos(theta), np.sin(theta)])
    inner = sq[perim]

    # graded blend from square perimeter (s=0) to circle (s=1), clustered at the wall
    jj = np.arange(m + 1) / m
    # tanh is steepest at 0, so cells are largest at the square (s = 0) and smallest at
    # the wall (s = 1). beta = 1.6 matches the square-block cell size at the interface.
    s = np.tanh(beta * jj) / np.tanh(beta)
    pts = [sq]
    layer_ids = [np.array(perim)]
    nid = len(sq)
    for k in range(1, m + 1):
        layer = (1 - s[k]) * inner + s[k] * circ
        pts.append(layer)
        layer_ids.append(np.arange(nid, nid + P))
        nid += P
    for k in range(m):
        L0, L1 = layer_ids[k], layer_ids[k + 1]
        for p in range(P):
            q = (p + 1) % P
            quads.append((L0[p], L1[p], L1[q], L0[q]))
    pts2d = np.vstack(pts)
    quads = np.array(quads)

    # enforce counter-clockwise quads (positive signed area)
    xy = pts2d[quads]
    area = 0.5 * np.sum(xy[:, :, 0] * np.roll(xy[:, :, 1], -1, axis=1)
                        - np.roll(xy[:, :, 0], -1, axis=1) * xy[:, :, 1], axis=1)
    quads[area < 0] = quads[area < 0][:, ::-1]
    Lw = layer_ids[m]
    wall_edges = [(Lw[p], Lw[(p + 1) % P]) for p in range(P)]
    return pts2d, quads, wall_edges


def centreline(R, pitch, turns, per_turn, leg_len, leg_cells):
    """Points C, tangent T, normal N, binormal B along inlet leg + helix + outlet leg.
    Returns arrays and the slice index of the start of each helix turn."""
    c = pitch / (2 * np.pi)
    th = np.linspace(0, 2 * np.pi * turns, turns * per_turn + 1)
    C = np.column_stack([R * np.cos(th), R * np.sin(th), c * th])
    T = np.column_stack([-R * np.sin(th), R * np.cos(th), np.full_like(th, c)])
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.column_stack([-np.cos(th), -np.sin(th), np.zeros_like(th)])  # principal normal
    s = np.linspace(0, leg_len, leg_cells + 1)[1:]
    Cin = C[0] - s[::-1, None] * T[0]
    Cout = C[-1] + s[:, None] * T[-1]
    rep = lambda v, k: np.repeat(v[None, :], k, axis=0)
    C = np.vstack([Cin, C, Cout])
    T = np.vstack([rep(T[0], leg_cells), T, rep(T[-1], leg_cells)])
    N = np.vstack([rep(N[0], leg_cells), N, rep(N[-1], leg_cells)])
    B = np.cross(T, N)
    turn_slices = [leg_cells + t * per_turn for t in range(turns + 1)]
    return C, T, N, B, turn_slices


def centreline_torus(R, deg, cells):
    """Zero-pitch arc (torus sector) of `deg` degrees with `cells` cells along the axis.
    Used with cyclic (rotationally periodic) end patches for fully developed flow."""
    th = np.linspace(0, np.radians(deg), cells + 1)
    C = np.column_stack([R * np.cos(th), R * np.sin(th), np.zeros_like(th)])
    T = np.column_stack([-np.sin(th), np.cos(th), np.zeros_like(th)])
    N = np.column_stack([-np.cos(th), -np.sin(th), np.zeros_like(th)])
    return C, T, N, np.cross(T, N), []


def build(args):
    r = args.d / 2
    pts2d, quads, wall_edges = cross_section(r, args.n, args.m)
    if args.torus > 0:
        C, T, N, B, turn_slices = centreline_torus(args.R, args.torus, args.torus_cells)
    else:
        C, T, N, B, turn_slices = centreline(args.R, args.pitch, args.turns, args.per_turn,
                                             args.leg * args.d, args.leg_cells)
    K = len(C)                       # node slices
    n2 = len(pts2d)
    q2 = len(quads)
    nodes = (C[:, None, :] + pts2d[None, :, 0, None] * N[:, None, :]
             + pts2d[None, :, 1, None] * B[:, None, :]).reshape(-1, 3)
    nid = lambda k, i: k * n2 + i                  # 0-based node id
    cid = lambda k, q: k * q2 + q                  # 0-based cell id, cell layer k in [0, K-2]
    ncell = (K - 1) * q2

    # 2D interior edges -> the two quads sharing them
    edge_quads = {}
    for qi, q in enumerate(quads):
        for e in range(4):
            a, b = q[e], q[(e + 1) % 4]
            edge_quads.setdefault((min(a, b), max(a, b)), []).append(qi)
    int_edges = [(e, qs) for e, qs in edge_quads.items() if len(qs) == 2]
    wall_set = {(min(a, b), max(a, b)) for a, b in wall_edges}
    wall_list = [(e, edge_quads[e][0]) for e in wall_set]

    zones = {}  # name -> list of (nodes[4], c0, c1)  (0-based, c1 = -1 for boundary)

    # cross-section faces at node slice k; quad normal (CCW) points along +T: from layer k-1 to k
    def section_faces(k):
        out = []
        for qi, q in enumerate(quads):
            f = [nid(k, v) for v in q]
            below = cid(k - 1, qi) if k > 0 else -1
            above = cid(k, qi) if k < K - 1 else -1
            out.append((f, below, above))
        return out

    zones['inlet'] = section_faces(0)
    zones['outlet'] = section_faces(K - 1)
    for t, k in enumerate(turn_slices):
        zones[f'turn{t}'] = section_faces(k)
    interior = []
    marked = set(turn_slices)
    for k in range(1, K - 1):
        if k not in marked:
            interior += section_faces(k)
    # lateral faces in cell layer k
    wall = []
    for k in range(K - 1):
        for (a, b), (q0, q1) in int_edges:
            interior.append(([nid(k, a), nid(k, b), nid(k + 1, b), nid(k + 1, a)],
                             cid(k, q0), cid(k, q1)))
        for (a, b), q0 in wall_list:
            wall.append(([nid(k, a), nid(k, b), nid(k + 1, b), nid(k + 1, a)], cid(k, q0), -1))
    zones['interior-fluid'] = interior
    zones['wall'] = wall

    # cell centroids for orientation
    cell_nodes = np.empty((ncell, 8), dtype=np.int64)
    for k in range(K - 1):
        cell_nodes[k * q2:(k + 1) * q2, :4] = k * n2 + quads
        cell_nodes[k * q2:(k + 1) * q2, 4:] = (k + 1) * n2 + quads
    cent = nodes[cell_nodes].mean(axis=1)
    return nodes, cell_nodes, cent, zones


def orient(nodes, cent, faces, normal_to_c0):
    """Return arrays (F[nf,4], c0, c1) oriented with Fluent's convention:
    right-hand normal of (n0..n3) points toward c0 if normal_to_c0 else away from it.
    For boundary faces c0 is the interior cell and c1 = 0."""
    F = np.array([f[0] for f in faces], dtype=np.int64)
    a = np.array([f[1] for f in faces], dtype=np.int64)
    b = np.array([f[2] for f in faces], dtype=np.int64)
    # boundary: interior cell must be c0
    swap = a < 0
    a[swap], b[swap] = b[swap], a[swap]
    p = nodes[F]
    nrm = np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1])
    fc = p.mean(axis=1)
    to_c0 = np.einsum('ij,ij->i', nrm, cent[a] - fc) > 0
    flip = to_c0 != normal_to_c0
    F[flip] = F[flip][:, ::-1]
    return F, a, b


def write_msh(path, nodes, cell_nodes, cent, zones, normal_to_c0=True):
    ids = {'fluid': 2, 'interior-fluid': 3, 'wall': 4, 'inlet': 5, 'outlet': 6}
    bc = {'interior-fluid': 0x2, 'wall': 0x3, 'inlet': 0xa, 'outlet': 0x5}
    ztype = {'interior-fluid': 'interior', 'wall': 'wall', 'inlet': 'velocity-inlet',
             'outlet': 'pressure-outlet'}
    order = ['interior-fluid'] + sorted(z for z in zones if z.startswith('turn')) + \
            ['wall', 'inlet', 'outlet']
    nxt = 7
    for z in order:
        if z.startswith('turn'):
            ids[z], bc[z], ztype[z] = nxt, 0x2, 'interior'
            nxt += 1
    nn, nc = len(nodes), len(cell_nodes)
    nf = sum(len(zones[z]) for z in order)
    with open(path, 'w') as fh:
        fh.write('(0 "Helical fluid-inerter channel: structured O-grid hex mesh")\n(2 3)\n')
        fh.write(f'(10 (0 1 {nn:x} 0 3))\n(10 (1 1 {nn:x} 1 3)(\n')
        np.savetxt(fh, nodes, fmt='%.10e')
        fh.write('))\n')
        fh.write(f'(12 (0 1 {nc:x} 0))\n(12 ({ids["fluid"]:x} 1 {nc:x} 1 4))\n')
        fh.write(f'(13 (0 1 {nf:x} 0))\n')
        first = 1
        for z in order:
            F, c0, c1 = orient(nodes, cent, zones[z], normal_to_c0)
            last = first + len(F) - 1
            fh.write(f'(13 ({ids[z]:x} {first:x} {last:x} {bc[z]:x} 4)(\n')
            data = np.column_stack([F + 1, c0 + 1, np.where(c1 < 0, 0, c1 + 1)])
            np.savetxt(fh, data, fmt='%x')
            fh.write('))\n')
            first = last + 1
        fh.write(f'(45 ({ids["fluid"]} fluid fluid)())\n')
        for z in order:
            fh.write(f'(45 ({ids[z]} {ztype[z]} {z})())\n')
    return nn, nc, nf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--d', type=float, default=6e-3, help='channel diameter [m]')
    ap.add_argument('--R', type=float, default=30e-3, help='helix radius [m]')
    ap.add_argument('--pitch', type=float, default=10e-3, help='helix pitch [m]')
    ap.add_argument('--turns', type=int, default=5)
    ap.add_argument('--n', type=int, default=12, help='cells per side of the central square')
    ap.add_argument('--m', type=int, default=12, help='radial cells in the outer O-ring')
    ap.add_argument('--per-turn', type=int, default=100, help='axial cells per helix turn')
    ap.add_argument('--leg', type=float, default=5.0, help='straight leg length [diameters]')
    ap.add_argument('--leg-cells', type=int, default=15)
    ap.add_argument('--flip', action='store_true', help='reverse the face orientation convention')
    ap.add_argument('--torus', type=float, default=0.0,
                    help='if > 0: write a zero-pitch torus SECTOR of this many degrees with '
                         'rotationally periodic (cyclic) ends instead of the helix (foam only)')
    ap.add_argument('--torus-cells', type=int, default=2, help='cells along the torus sector')
    ap.add_argument('--format', choices=['foam', 'fluent'], default='foam',
                    help='foam: OpenFOAM polyMesh written into the case directory --out; '
                         'fluent: ASCII .msh file --out')
    ap.add_argument('--out', default='helix_case',
                    help='OpenFOAM case directory (foam) or .msh file (fluent)')
    args = ap.parse_args()
    nodes, cells, cent, zones = build(args)
    if args.format == 'foam':
        nn, nc, nf = write_foam(args.out, nodes, cent, zones, torus=args.torus > 0)
    else:
        nn, nc, nf = write_msh(args.out, nodes, cells, cent, zones, normal_to_c0=not args.flip)
    write_info(args, nodes, zones)
    print(f'wrote {args.out} ({args.format}): {nn} nodes, {nc} hex cells, {nf} faces, '
          f'turn planes: {sorted(z for z in zones if z.startswith("turn"))}')


def write_info(args, nodes, zones):
    """mesh_info.json next to the output: discrete inlet area and turn arc length,
    needed to set the exact flow rate and to compute the friction factor."""
    F, _, _ = orient(nodes, np.zeros((1, 3)), [(f[0], 0, -1) for f in zones['inlet']], True)
    p = nodes[F]
    area = 0.5 * np.linalg.norm(np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 1]), axis=1).sum()
    info = dict(d=args.d, R_h=args.R, pitch=args.pitch, turns=args.turns,
                n=args.n, m=args.m, per_turn=args.per_turn,
                inlet_area=area, s_turn=float(np.hypot(2 * np.pi * args.R, args.pitch)))
    if args.torus > 0:
        info.update(torus_deg=args.torus, torus_cells=args.torus_cells, pitch=0.0, turns=0,
                    s_sector=float(args.R * np.radians(args.torus)))
    base = args.out if os.path.isdir(args.out) else os.path.dirname(os.path.abspath(args.out))
    with open(os.path.join(base, 'mesh_info.json'), 'w') as fh:
        json.dump(info, fh, indent=2)


FOAM_HDR = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    location    "constant/polyMesh";
    object      {obj};{note}
}}

"""


def write_foam(case_dir, nodes, cent, zones, torus=False):
    """Write an OpenFOAM polyMesh into <case_dir>/constant/polyMesh.
    OpenFOAM convention: face normal (right-hand rule) points from owner to neighbour,
    owner < neighbour, internal faces in upper-triangular order, boundary normals outward.
    The turn planes are written as faceZones.
    torus=True: the end patches become a rotational cyclic pair cyc0/cyc1 (axis z)."""
    pm = os.path.join(case_dir, 'constant', 'polyMesh')
    os.makedirs(pm, exist_ok=True)
    internal = ['interior-fluid'] + sorted(z for z in zones if z.startswith('turn'))
    if torus:
        zones = dict(zones, cyc0=zones['inlet'], cyc1=zones['outlet'])
        patches = [('wall', 'wall'), ('cyc0', 'cyclic'), ('cyc1', 'cyclic')]
    else:
        patches = [('wall', 'wall'), ('inlet', 'patch'), ('outlet', 'patch')]

    F_int, own, nbr, tag = [], [], [], []
    for zi, z in enumerate(internal):
        f = [(fc[0], min(fc[1], fc[2]), max(fc[1], fc[2])) for fc in zones[z]]
        F, a, b = orient(nodes, cent, f, normal_to_c0=False)     # normal away from owner
        F_int.append(F); own.append(a); nbr.append(b); tag.append(np.full(len(F), zi))
    F_int, own, nbr, tag = map(np.concatenate, (F_int, own, nbr, tag))
    order = np.lexsort((nbr, own))
    F_int, own, nbr, tag = F_int[order], own[order], nbr[order], tag[order]
    n_int = len(F_int)

    F_all, own_all, bnd = [F_int], [own], []
    start = n_int
    for name, ptype in patches:
        F, a, _ = orient(nodes, cent, zones[name], normal_to_c0=False)  # outward
        if name == 'cyc0':
            # cyc0 faces were reversed to point outward: rotate so they start at the same
            # cross-section node as their cyc1 partner (coupled faces: same point 0, opposite order)
            F = np.roll(F, 1, axis=1)
        F_all.append(F); own_all.append(a)
        bnd.append((name, ptype, len(F), start))
        start += len(F)
    F_all, own_all = np.concatenate(F_all), np.concatenate(own_all)
    nn, nf, nc = len(nodes), len(F_all), len(cent)
    note = (f'\n    note        "nPoints:{nn}  nCells:{nc}  nFaces:{nf}  '
            f'nInternalFaces:{n_int}";')

    def write_list(name, cls, data, fmt, with_note=False):
        with open(os.path.join(pm, name), 'w') as fh:
            fh.write(FOAM_HDR.format(cls=cls, obj=name, note=note if with_note else ''))
            fh.write(f'{len(data)}\n(\n')
            np.savetxt(fh, data, fmt=fmt)
            fh.write(')\n')

    write_list('points', 'vectorField', nodes, '(%.10e %.10e %.10e)')
    write_list('faces', 'faceList', F_all, '4(%d %d %d %d)')
    write_list('owner', 'labelList', own_all, '%d', with_note=True)
    write_list('neighbour', 'labelList', nbr, '%d', with_note=True)

    with open(os.path.join(pm, 'boundary'), 'w') as fh:
        fh.write(FOAM_HDR.format(cls='polyBoundaryMesh', obj='boundary', note=''))
        fh.write(f'{len(bnd)}\n(\n')
        for name, ptype, n, s in bnd:
            grp = '\n        inGroups        1(wall);' if ptype == 'wall' else ''
            if ptype == 'cyclic':
                grp = ('\n        inGroups        1(cyclic);\n        matchTolerance  0.0001;'
                       '\n        transform       rotational;\n        rotationAxis    (0 0 1);'
                       '\n        rotationCentre  (0 0 0);'
                       f'\n        neighbourPatch  {"cyc1" if name == "cyc0" else "cyc0"};')
            fh.write(f'    {name}\n    {{\n        type            {ptype};{grp}\n'
                     f'        nFaces          {n};\n        startFace       {s};\n    }}\n')
        fh.write(')\n')

    with open(os.path.join(pm, 'faceZones'), 'w') as fh:
        fh.write(FOAM_HDR.format(cls='regIOobject', obj='faceZones', note=''))
        fz = internal[1:]
        fh.write(f'{len(fz)}\n(\n')
        for zi, z in enumerate(fz, start=1):
            ids = np.nonzero(tag == zi)[0]
            fh.write(f'{z}\n{{\n    type faceZone;\n    faceLabels List<label> {len(ids)}('
                     + ' '.join(map(str, ids)) + f');\n    flipMap List<bool> {len(ids)}('
                     + ' '.join('0' * len(ids)) + ');\n}\n')
        fh.write(')\n')
    return nn, nc, nf


if __name__ == '__main__':
    main()
