"""Generate the 3D PORT cases: piston chamber + radial drilled port + sharp elbows + start of the coil.

The axisymmetric chamber cases (make_chamber_openfoam.py) put the port on the chamber axis and stand a
straight tube in for the coil. In the device (cfd/paraview/build_device.py) the port is a RADIAL hole
in the bore wall near the end cap. It meets an axial drilling at a sharp 90 deg corner, which turns
sharply again into the helix. These cases model that geometry in 3D, so oil leaving the coil
arrives at the port with the skewed Dean-flow profile of the helix, not a parabolic one.

Geometry (x = cylinder axis, mm):
    chamber      bore radius 20, from the end cap (x = 0) to the piston face (x = 54, mid-stroke)
    radial port  d = 6, axis along +y at x = 4 (4 mm from the cap), from the bore wall to y = 30
    elbow 1      sharp mitre, +y -> +x, axial drilling at (y = 30, z = 0) from x = 4 to x = 10
    elbow 2      sharp mitre, +x -> helix tangent
    helix        radius 30, pitch 10, from x = 10, 2.62 turns (path length 510 mm from the bore wall)
Monitor planes at 300 and 450 mm path length from the bore wall (as the 2D cases: x = 0.30, 0.45 m).

Cases (steady simpleFoam, laminar, same oil as everywhere else):
    in_reNNNNN   piston pushes oil INTO the port (piston = uniform inlet, coil end = p outlet)
    out_reNNNNN  oil flows OUT of the coil into the chamber. Coil end = mapped (recycled) inlet:
                 the helix repeats itself after one turn shifted by one pitch in x, so the inlet copies
                 the velocity one turn downstream (offset (-p, 0, 0)) -> fully developed helix
                 flow arrives at the planes. Piston = pressure outlet.
Two meshes (snappyHexMesh, hex-dominant, 2 wall layers): fine 1.1 mm base / 0.275 mm in the
channel and near the port (Re 250-1000), coarse 1.4 / 0.35 mm (Re 250-2000, mesh check at 250 and 1000).

Writes cfd/openfoam/port3d/ (fine) and cfd/openfoam/port3d_coarse/ (mesh check).
Usage:  python make_port3d_openfoam.py
Run:    bash cfd/openfoam/run_in_wsl.sh port3d_coarse port3d       (inside Ubuntu)
Post:   python post_port3d.py
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_s01_openfoam import write, NU, RHO   # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
OF = os.path.normpath(os.path.join(here, '..', 'openfoam'))
mm = 1e-3

# ---------------------------------------------------------------- geometry (SI)
R_P, L_CH = 20 * mm, 54 * mm        # bore radius, chamber length (end cap -> piston face at mid-stroke)
R_T = 3 * mm                        # channel / port radius
D_T = 2 * R_T
X_PORT = 4 * mm                     # port axis, distance from the end cap
R_H, PITCH = 30 * mm, 10 * mm       # helix radius and pitch
X_HELIX = 10 * mm                   # helix start (end of the axial drilling)
S_LEAD = (R_H - R_P) + (X_HELIX - X_PORT)        # path length bore wall -> helix start = 16 mm
L_TURN = math.hypot(2 * math.pi * R_H, PITCH)    # helix path length per turn
S_END = 510 * mm                    # path length bore wall -> coil end
PLANES = (300 * mm, 450 * mm)       # monitor planes (path length from the bore wall)
A_P, A_C = math.pi * R_P ** 2, math.pi * R_T ** 2

MESHES = {
    'fine':   dict(base=1.1 * mm, set='port3d', re=[250, 500, 1000]),
    'coarse': dict(base=1.4 * mm, set='port3d_coarse', re=[250, 1000, 2000]),
}
N_ITER = 2000
SAMPLE_EVERY = 50


# ---------------------------------------------------------------- helix
def theta_of_s(s):
    return 2 * math.pi * (s - S_LEAD) / L_TURN


def helix(th):
    return np.array([X_HELIX + PITCH * th / (2 * math.pi), R_H * math.cos(th), R_H * math.sin(th)])


def helix_tangent(th):
    t = np.array([PITCH / (2 * math.pi), -R_H * math.sin(th), R_H * math.cos(th)])
    return t / np.linalg.norm(t)


def rot(a, b):
    """Rotation matrix taking unit vector a onto unit vector b (Rodrigues)."""
    v, c = np.cross(a, b), float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-14:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


# ---------------------------------------------------------------- surface (STL)
def quads(A, B):
    """Triangles joining two closed rings of equal length."""
    n = len(A)
    out = []
    for k in range(n):
        a0, a1, b0, b1 = A[k], A[(k + 1) % n], B[k], B[(k + 1) % n]
        out += [(a0, a1, b1), (a0, b1, b0)]
    return out


def build_surface(nphi=64, M=16, h=3.6 * mm):
    """Fluid boundary as named triangle lists. nphi = points around the channel, M = points per side of
    the square patch around the port hole (nphi = 4 M)."""
    assert nphi == 4 * M
    S = {k: [] for k in ('chamberWall', 'cap', 'piston', 'portWall', 'coilEnd')}

    # --- port hole patch on the bore wall: circle (radius R_T) -> square (half width h) in (x, z)
    phi = 2 * np.pi * np.arange(nphi) / nphi
    sq = []                                                      # square perimeter, CCW from (h, 0)
    per = np.arange(nphi) / nphi * 8 * h                         # perimeter position, start at (h, 0) = mid side
    for u in per:
        u = (u + h) % (8 * h)                                    # shift: start at corner (h, -h)
        side, w = int(u // (2 * h)), u % (2 * h) - h
        sq.append([(h, w), (-w, h), (-h, -w), (w, -h)][side])
    sq = np.array(sq)
    circ = np.c_[R_T * np.cos(phi), R_T * np.sin(phi)]
    wall = lambda xz: np.array([X_PORT + xz[0], math.sqrt(R_P ** 2 - xz[1] ** 2), xz[1]])
    rings = [[wall(circ[k] + f * (sq[k] - circ[k])) for k in range(nphi)] for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    for A, B in zip(rings[:-1], rings[1:]):
        S['chamberWall'] += quads(A, B)
    port_ring = rings[0]

    # --- rest of the bore wall: structured (x, theta) grid sharing the square's nodes
    xs_sq = X_PORT - h + 2 * h * np.arange(M + 1) / M
    zs_sq = -h + 2 * h * np.arange(M + 1) / M
    th_sq = np.arcsin(zs_sq / R_P)
    x_lo = list(np.linspace(0, xs_sq[0], 2)[:-1])
    x_hi, x = [], xs_sq[-1]
    dx = 2 * h / M
    while x < L_CH - 1e-9:
        dx = min(dx * 1.12, 2 * mm)
        x = min(x + dx, L_CH)
        x_hi.append(x)
    xs = np.array(x_lo + list(xs_sq) + x_hi)
    n_th = int(round((2 * math.pi - 2 * th_sq[-1]) / math.radians(2)))
    th_rest = np.linspace(th_sq[-1], 2 * math.pi + th_sq[0], n_th + 1)[1:-1]
    ths = np.concatenate([th_sq, th_rest])                       # closed: wraps from th_rest[-1] to th_sq[0]
    ix0 = len(x_lo)
    P = lambda i, j: (wall((xs[i] - X_PORT, zs_sq[j])) if j <= M else
                      np.array([xs[i], R_P * math.cos(ths[j]), R_P * math.sin(ths[j])]))
    nt = len(ths)
    for i in range(len(xs) - 1):
        for j in range(nt):
            jn = (j + 1) % nt
            if ix0 <= i < ix0 + M and j < M:
                continue                                         # inside the hole patch
            a, b, c, d = P(i, j), P(i + 1, j), P(i + 1, jn), P(i, jn)
            S['chamberWall'] += [(a, b, c), (a, c, d)]

    # --- end cap (x = 0) and piston (x = L_CH): polar discs on the wall's theta nodes
    for name, xc, i in (('cap', 0.0, 0), ('piston', L_CH, len(xs) - 1)):
        rim = [P(i, j) for j in range(nt)]
        K = 12
        prev = rim
        for k in range(K - 1, 0, -1):
            f = k / K
            cur = [np.array([xc, f * q[1], f * q[2]]) for q in rim]
            S[name] += quads(prev, cur)
            prev = cur
        c = np.array([xc, 0, 0])
        S[name] += [(prev[k], prev[(k + 1) % nt], c) for k in range(nt)]

    # --- channel: radial port -> mitre -> axial drilling -> mitre -> helix
    e1 = np.c_[R_T * np.cos(phi), np.zeros(nphi), R_T * np.sin(phi)]     # offsets around +y (matches port_ring)
    d1, d2 = np.array([0, 1.0, 0]), np.array([1.0, 0, 0])
    C1, C2 = np.array([X_PORT, R_H, 0]), np.array([X_HELIX, R_H, 0])

    n1 = (d1 + d2) / np.linalg.norm(d1 + d2)
    ring_m1 = [C1 + e + d1 * (-(np.dot(e, n1)) / np.dot(d1, n1)) for e in e1]
    chain = [port_ring]
    for f in np.linspace(0, 1, 21)[1:-1]:                         # radial tube, 0.5 mm rings
        chain.append([port_ring[k] + f * (ring_m1[k] - port_ring[k]) for k in range(nphi)])
    chain.append(ring_m1)
    e2 = [rot(d1, d2) @ e for e in e1]
    d3 = helix_tangent(0.0)
    n2 = (d2 + d3) / np.linalg.norm(d2 + d3)
    ring_m2 = [C2 + e + d2 * (-(np.dot(e, n2)) / np.dot(d2, n2)) for e in e2]
    for f in np.linspace(0, 1, 13)[1:-1]:
        chain.append([ring_m1[k] + f * (ring_m2[k] - ring_m1[k]) for k in range(nphi)])
    chain.append(ring_m2)
    e3 = [rot(d2, d3) @ e for e in e2]
    th0 = 1.15 * R_T / R_H                                      # first helix ring clear of the mitre plane
    th_end = theta_of_s(S_END)
    n_h = int(math.ceil((th_end - th0) * R_H / (1.0 * mm)))
    th_list = np.linspace(th0, th_end, n_h + 1)
    # parallel transport of the offsets along the helix (rotation-minimising frame), starting from the
    # mitre direction d3 = tangent at th = 0; the first ring (th0) is joined straight to the mitre ring
    t_prev, offs = d3, e3
    for th in th_list:
        t = helix_tangent(th)
        Rm = rot(t_prev, t)
        offs = [Rm @ e for e in offs]
        t_prev = t
        chain.append([helix(th) + e for e in offs])
    for A, B in zip(chain[:-1], chain[1:]):
        S['portWall'] += quads(A, B)
    end = chain[-1]
    c = helix(th_end)
    S['coilEnd'] += [(end[(k + 1) % nphi], end[k], c) for k in range(nphi)]
    c0 = np.mean(port_ring, axis=0) - np.array([0, 0.5 * mm, 0])
    S['portOpening'] = [(port_ring[k], port_ring[(k + 1) % nphi], c0) for k in range(nphi)]
    return S, dict(th_end=th_end, t_end=helix_tangent(th_end).tolist(), c_end=c.tolist())


def write_stl(path, S):
    with open(path, 'w', newline='\n') as fh:
        for name, tris in S.items():
            fh.write(f'solid {name}\n')
            for a, b, c in tris:
                n = np.cross(b - a, c - a)
                ln = np.linalg.norm(n)
                if ln < 1e-30:
                    continue
                n /= ln
                fh.write(f' facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}\n  outer loop\n')
                for q in (a, b, c):
                    fh.write(f'   vertex {q[0]:.9e} {q[1]:.9e} {q[2]:.9e}\n')
                fh.write('  endloop\n endfacet\n')
            fh.write(f'endsolid {name}\n')


# ---------------------------------------------------------------- meshing dictionaries
def block_mesh(base):
    lo = np.array([-1.0 * mm, -34 * mm, -34 * mm])
    hi = np.array([L_CH + 1.0 * mm, 34 * mm, 34 * mm])
    n = np.maximum(1, np.round((hi - lo) / base)).astype(int)
    hi = lo + n * base
    v = [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
         (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]
    vt = '\n'.join(f'    ({a:.9g} {b:.9g} {c:.9g})' for a, b, c in v)
    return f"""scale 1;
vertices
(
{vt}
);
blocks ( hex (0 1 2 3 4 5 6 7) ({n[0]} {n[1]} {n[2]}) simpleGrading (1 1 1) );
boundary ( background {{ type patch; faces ( (0 3 2 1) (4 5 6 7) (0 4 7 3) (1 2 6 5) (0 1 5 4) (3 7 6 2) ); }} );
"""


def snappy_dict(info):
    off = f'({-PITCH:.9g} 0 0)'
    loc = f'({L_CH / 2:.6g} 0.0013 0.0017)'
    port_c = f'({X_PORT:.6g} {R_P:.6g} 0)'
    return f"""castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    device.stl
    {{
        type triSurfaceMesh; name device;
        regions {{ chamberWall {{ name chamberWall; }} cap {{ name cap; }} piston {{ name piston; }}
                  portWall {{ name portWall; }} coilEnd {{ name coilEnd; }} }}
    }}
    channel.stl {{ type triSurfaceMesh; name channel; }}
    portZone   {{ type searchableSphere; centre {port_c}; radius 0.009; }}
}}

castellatedMeshControls
{{
    maxLocalCells       3000000;
    maxGlobalCells      8000000;
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 3;
    features            ( {{ file "device.eMesh"; level 2; }} );
    refinementSurfaces
    {{
        device
        {{
            level (1 1);
            regions
            {{
                portWall    {{ level (2 2); patchInfo {{ type wall; }} }}
                chamberWall {{ level (1 1); patchInfo {{ type wall; }} }}
                cap         {{ level (1 1); patchInfo {{ type wall; }} }}
                piston      {{ level (1 1); patchInfo {{ type patch; }} }}
                coilEnd
                {{
                    level (2 2);
                    patchInfo
                    {{
                        type            mappedPatch;
                        sampleMode      nearestCell;
                        sampleRegion    region0;
                        samplePatch     none;
                        offsetMode      uniform;
                        offset          {off};
                    }}
                }}
            }}
        }}
    }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
        channel  {{ mode inside; levels ((1 2)); }}
        portZone {{ mode inside; levels ((1 2)); }}
    }}
    locationInMesh {loc};
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch    3;
    tolerance       2.0;
    nSolveIter      100;
    nRelaxIter      5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap true;
}}

addLayersControls
{{
    relativeSizes       true;
    layers {{ portWall {{ nSurfaceLayers 2; }} chamberWall {{ nSurfaceLayers 1; }} cap {{ nSurfaceLayers 1; }} }}
    expansionRatio      1.3;
    finalLayerThickness 0.45;
    minThickness        0.1;
    nGrow               0;
    featureAngle        100;
    slipFeatureAngle    30;
    nRelaxIter          5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals      3;
    nSmoothThickness    10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle  90;
    nBufferCellsNoExtrude 0;
    nLayerIter          50;
}}

meshQualityControls
{{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80; minVol 1e-16;
    minTetQuality 1e-15; minArea -1; minTwist 0.02; minDeterminant 0.001; minFaceWeight 0.05;
    minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
    relaxed {{ maxNonOrtho 75; }}
}}

mergeTolerance 1e-6;
"""


FEATURES = """device.stl
{
    extractionMethod    extractFromSurface;
    includedAngle       150;
    subsetFeatures { nonManifoldEdges no; openEdges yes; }
    writeObj            no;
}
"""


# ---------------------------------------------------------------- case dictionaries
def plane_dict(s):
    th = theta_of_s(s)
    p, t = helix(th), helix_tangent(th)
    lo, hi = p - 4.5 * mm, p + 4.5 * mm
    v = lambda a: f'({a[0]:.9g} {a[1]:.9g} {a[2]:.9g})'
    return (f'type cuttingPlane; planeType pointAndNormal; '
            f'pointAndNormalDict {{ point {v(p)}; normal {v(t)}; }} bounds ({v(lo)[1:-1]}) ({v(hi)[1:-1]}); '
            f'interpolate false;')


def functions():
    planes = {f'plane{int(round(s * 1e3))}': plane_dict(s) for s in PLANES}
    mid = (f'type cuttingPlane; planeType pointAndNormal; pointAndNormalDict {{ point (0 0 0); normal (0 0 1); }} '
           f'bounds (-0.001 -0.021 -0.001) ({L_CH + 0.001:.6g} 0.034 0.001); interpolate false;')
    cross = (f'type cuttingPlane; planeType pointAndNormal; pointAndNormalDict {{ point ({X_PORT:.6g} 0 0); normal (1 0 0); }} '
             f'bounds ({X_PORT - 0.001:.6g} -0.021 -0.021) ({X_PORT + 0.001:.6g} 0.034 0.021); interpolate false;')
    out = """    magSqrU { type magSqr; libs (fieldFunctionObjects); field U; writeControl timeStep; writeInterval 1; log false; }
"""
    for patch in ('piston', 'coilEnd'):
        out += f"""    q_{patch} {{ type surfaceFieldValue; libs (fieldFunctionObjects); log false; writeControl timeStep; writeInterval 1;
        writeFields false; regionType patch; name {patch}; operation sum; fields (phi); }}
    e_{patch} {{ type surfaceFieldValue; libs (fieldFunctionObjects); log false; writeControl timeStep; writeInterval 1;
        writeFields false; regionType patch; name {patch}; operation weightedAverage; weightField phi; fields (p magSqr(U)); }}
"""
    for name, d in planes.items():
        out += f"""    p_{name} {{ type surfaceFieldValue; libs (fieldFunctionObjects); log false; writeControl timeStep; writeInterval 1;
        writeFields false; regionType sampledSurface; name {name}; sampledSurfaceDict {{ {d} }} operation areaAverage; fields (p); }}
"""
    surf = '\n'.join(f'            {n} {{ {d} }}' for n, d in planes.items())
    out += f"""    planes
    {{
        type            surfaces;
        libs            (sampling);
        writeControl    timeStep;
        writeInterval   {SAMPLE_EVERY};
        surfaceFormat   vtk;
        formatOptions   {{ vtk {{ legacy true; format ascii; }} }}
        fields          (p U);
        surfaces
        {{
{surf}
        }}
    }}
    views
    {{
        type            surfaces;
        libs            (sampling);
        writeControl    writeTime;
        surfaceFormat   vtk;
        formatOptions   {{ vtk {{ legacy true; format ascii; }} }}
        fields          (p U);
        surfaces
        {{
            midplane {{ {mid} }}
            portCross {{ {cross} }}
        }}
    }}
"""
    return out


def make_case(root, direction, Re, info):
    v = Re * NU / D_T
    up = v * A_C / A_P
    case = os.path.join(root, f'{direction}_re{Re:05d}')
    t_end = np.array(info['t_end'])
    if direction == 'in':
        u_pis = f'type fixedValue; value uniform ({-up:.10e} 0 0);'
        p_pis = 'type zeroGradient;'
        u_end = 'type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);'
        p_end = 'type fixedValue; value uniform 0;'
    else:
        a = -v * t_end                                   # into the domain, against the helix direction
        u_pis = 'type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);'
        p_pis = 'type fixedValue; value uniform 0;'
        u_end = (f'type mapped; field U; setAverage true; average ({a[0]:.10e} {a[1]:.10e} {a[2]:.10e}); '
                 f'interpolationScheme cell; value uniform ({a[0]:.10e} {a[1]:.10e} {a[2]:.10e});')
        p_end = 'type zeroGradient;'
    walls_u = '\n'.join(f'    {w:<12}{{ type noSlip; }}' for w in ('portWall', 'chamberWall', 'cap'))
    walls_p = '\n'.join(f'    {w:<12}{{ type zeroGradient; }}' for w in ('portWall', 'chamberWall', 'cap'))
    write(os.path.join(case, '0', 'U'), 'volVectorField', 'U', f"""dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    piston      {{ {u_pis} }}   // channel bulk {v:.5f} m/s, Re {Re}
    coilEnd     {{ {u_end} }}
{walls_u}
}}
""")
    write(os.path.join(case, '0', 'p'), 'volScalarField', 'p', f"""dimensions      [0 2 -2 0 0 0 0];   // kinematic p/rho
internalField   uniform 0;
boundaryField
{{
    piston      {{ {p_pis} }}
    coilEnd     {{ {p_end} }}
{walls_p}
}}
""")
    write(os.path.join(case, 'constant', 'transportProperties'), 'dictionary', 'transportProperties',
          f'transportModel  Newtonian;\nnu              {NU:.8e};   // ISO VG 32 oil, mu = 0.028 Pa s, rho = 870\n')
    write(os.path.join(case, 'constant', 'turbulenceProperties'), 'dictionary', 'turbulenceProperties',
          'simulationType  laminar;\n')
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict', f"""application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {N_ITER};
deltaT          1;
writeControl    timeStep;
writeInterval   {N_ITER};
purgeWrite      1;
writeFormat     binary;
writePrecision  8;
timeFormat      general;
runTimeModifiable false;

functions
{{
{functions()}}}
""")
    write(os.path.join(case, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes', """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; limited cellLimited Gauss linear 1; grad(U) $limited; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes        { default Gauss linear limited corrected 0.5; }
interpolationSchemes    { default linear; }
snGradSchemes           { default limited corrected 0.5; }
wallDist                { method meshWave; }
""")
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', f"""solvers
{{
    p   {{ solver GAMG; smoother GaussSeidel; tolerance 1e-9; relTol 0.05; }}
    U   {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0.1; }}
}}
SIMPLE
{{
    nNonOrthogonalCorrectors 1;
    consistent      true;
    residualControl {{ p 1e-6; U 1e-7; }}
}}
relaxationFactors
{{
    fields      {{ p 0.5; }}
    equations   {{ U 0.8; }}
}}
""")
    json.dump(dict(case=os.path.basename(case), direction=direction, Re=Re, v_tube=v, u_piston=up),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


ALLRUN = r"""#!/bin/bash
# 3D port set: snappyHexMesh once, then run every case in parallel (NP cores), one after another.
#   ./Allrun [NP]      (default 8)
cd "${0%/*}" || exit 1
NP=${1:-8}
command -v simpleFoam >/dev/null || { echo "OpenFOAM environment not loaded"; exit 1; }
sed -i "s/numberOfSubdomains .*/numberOfSubdomains $NP;/" mesh/system/decomposeParDict
for c in in_* out_*; do cp mesh/system/decomposeParDict "$c/system/"; done
if [ ! -f mesh/constant/polyMesh/owner ]; then
  ( cd mesh && blockMesh > log.blockMesh 2>&1 && surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1 \
      && decomposePar -force > log.decomposePar 2>&1 \
      && mpirun -np $NP snappyHexMesh -overwrite -parallel > log.snappyHexMesh 2>&1 \
      && reconstructParMesh -constant > log.reconstructParMesh 2>&1 && rm -rf processor* \
      && checkMesh > log.checkMesh 2>&1 ) || { echo "meshing failed, see mesh/log.*"; exit 1; }
fi
grep -E "^ *cells:|Mesh OK|Failed|\*\*\*|Max skewness" mesh/log.checkMesh
for c in out_* in_*; do
    rm -rf "$c/constant/polyMesh" "$c/postProcessing" "$c"/processor* "$c"/[1-9]*
    cp -r mesh/constant/polyMesh "$c/constant/"
    ( cd "$c" && decomposePar -force > log.decomposePar 2>&1 \
        && mpirun -np $NP simpleFoam -parallel > log.simpleFoam 2>&1 \
        && reconstructPar -latestTime > log.reconstructPar 2>&1 && rm -rf processor* )
    if grep -q "^End" "$c/log.simpleFoam"; then echo "$c: finished $(date +%H:%M)"; else echo "$c: FAILED, see $c/log.simpleFoam"; fi
done
echo "Done."
"""


def write_set(mesh_name):
    m = MESHES[mesh_name]
    root = os.path.join(OF, m['set'])
    mesh = os.path.join(root, 'mesh')
    S, info = build_surface()
    os.makedirs(os.path.join(mesh, 'constant', 'triSurface'), exist_ok=True)
    opening = S.pop('portOpening')
    write_stl(os.path.join(mesh, 'constant', 'triSurface', 'device.stl'), S)
    write_stl(os.path.join(mesh, 'constant', 'triSurface', 'channel.stl'),
              dict(channel=S['portWall'] + S['coilEnd'] + opening))
    write(os.path.join(mesh, 'system', 'blockMeshDict'), 'dictionary', 'blockMeshDict', block_mesh(m['base']))
    write(os.path.join(mesh, 'system', 'surfaceFeatureExtractDict'), 'dictionary', 'surfaceFeatureExtractDict', FEATURES)
    write(os.path.join(mesh, 'system', 'snappyHexMeshDict'), 'dictionary', 'snappyHexMeshDict', snappy_dict(info))
    write(os.path.join(mesh, 'system', 'decomposeParDict'), 'dictionary', 'decomposeParDict',
          'numberOfSubdomains 8;\nmethod scotch;\n')
    write(os.path.join(mesh, 'system', 'controlDict'), 'dictionary', 'controlDict',
          'application snappyHexMesh;\nstartFrom startTime;\nstartTime 0;\nstopAt endTime;\nendTime 1;\ndeltaT 1;\n'
          'writeControl timeStep;\nwriteInterval 1;\nwriteFormat binary;\n')
    write(os.path.join(mesh, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes',
          'ddtSchemes { default steadyState; }\ngradSchemes { default Gauss linear; }\ndivSchemes { default none; }\n'
          'laplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\n'
          'snGradSchemes { default corrected; }\nwallDist { method meshWave; }\n')
    write(os.path.join(mesh, 'system', 'fvSolution'), 'dictionary', 'fvSolution', '')
    info.update(mesh=mesh_name, base=m['base'], R_p=R_P, L_ch=L_CH, r_t=R_T, d=D_T, x_port=X_PORT, R_h=R_H,
                pitch=PITCH, x_helix=X_HELIX, s_lead=S_LEAD, s_end=S_END, planes=PLANES, A_p=A_P, A_c=A_C,
                rho=RHO, nu=NU, n_tri=sum(len(t) for t in S.values()))
    json.dump(info, open(os.path.join(mesh, 'mesh_info.json'), 'w'), indent=2)
    for Re in m['re']:
        for direction in ('in', 'out'):
            make_case(root, direction, Re, info)
    with open(os.path.join(root, 'Allrun'), 'w', newline='\n') as fh:
        fh.write(ALLRUN)
    print(f'wrote {root}: {mesh_name} mesh (base {m["base"] * 1e3:.1f} mm), {info["n_tri"]} STL triangles, '
          f'{2 * len(m["re"])} cases')


def main():
    for name in MESHES:
        write_set(name)


if __name__ == '__main__':
    main()
