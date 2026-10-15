"""Generate OpenFOAM cases for the PISTON CHAMBER + PORT (cases S2 and S3 of docs/cfd_setup_*.md).

The helix CFD (s01, torus_*) drives the oil directly in the channel, using continuity Q = A_p * xdot.
These cases add the part of the device that is missing there: the piston, its oil chamber and the
sharp-edged port where the oil enters and leaves the coil.

Geometry (2D axisymmetric wedge, axis = x, 5 degrees):
    piston face (x = -L_c, radius R_p = 20 mm, moves with the prescribed piston velocity)
    chamber, length L_c = 20 mm
    sharp-edged port into a straight tube of radius r_t = 3 mm and length L_t = 0.6 m (100 d),
    which stands for the first part of the coil. Face zones at x = 0.30 and 0.45 m monitor the
    developed flow.

Two case sets (same geometry, two meshes):
  cfd/openfoam/chamber/            FINE mesh (0.06-0.08 mm at the port edge), steady cases only
  cfd/openfoam/chamber_transient/  COARSER mesh (0.15-0.2 mm) for the time-dependent cases, which a
                                   fine mesh would make ~10x slower; it also repeats two steady cases
                                   so the two meshes can be compared.
Cases:
    in_reNNNNN    steady simpleFoam, piston pushes oil INTO the tube   -> entry loss K_in(Re)
    out_reNNNNN   steady simpleFoam, oil flows OUT of the tube into the chamber -> exit loss K_out(Re)
    osc_T04       pimpleFoam, piston oscillating as CFD case T04 (10 Hz, 5.6 mm). The tube end is
                  coupled to the rest of the coil: p_end(t) = phi*(b_eq*xddot + c_eq*xdot)/A_p with
                  b_eq, c_eq from the torus CFD (T04) and phi = (l/2 - L_t)/l (the device is
                  antisymmetric, so the pressure at mid-coil stays at the charge pressure).
    cav_pNNNNk    interPhaseChangeFoam (Schnerr-Sauer cavitation), case T05 (20 Hz, 2.43 mm),
                  same coupled outlet, absolute pressure; one case per charge pressure.

Usage:  python make_chamber_openfoam.py
Run:    bash cfd/openfoam/run_in_wsl.sh chamber chamber_transient     (inside Ubuntu)
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
root = os.path.join(OF, 'chamber')          # set by main() for each case set
# cell sizes [m]: tube centre, wall, port edge (radial / axial), chamber far end, tube far end
MESHES = {
    'fine':   dict(r_axis=0.22e-3, r_wall=0.06e-3, edge_r=0.06e-3, edge_x=0.08e-3, far=1.0e-3, tube=2.0e-3),
    'coarse': dict(r_axis=0.40e-3, r_wall=0.15e-3, edge_r=0.15e-3, edge_x=0.20e-3, far=1.5e-3, tube=2.0e-3),
}

# ---------------------------------------------------------------- geometry (SI)
R_P, L_C = 20e-3, 20e-3            # piston (bore) radius, chamber length
R_T, L_T = 3e-3, 0.6               # port / tube radius, modelled tube length
D_T = 2 * R_T
L_COIL = 1.888                     # full channel length
A_P = math.pi * R_P ** 2
A_C = math.pi * R_T ** 2
ZONES = (0.30, 0.45)               # monitor planes in the tube [m]
WEDGE = 5.0                        # wedge angle [deg]
P_SAT = 2000.0                     # oil vapour / air-release pressure [Pa] (docs/theory.md)

STEADY_RE = [100, 250, 500, 1000, 2000]
# oscillatory cases: (name, f [Hz], X [m], b_eq [kg], c_eq [N s/m]) from cfd/results/transient_summary.csv
T04 = ('T04', 10.0, 5.60453e-3, 93.8298, 8492.53)
T05 = ('T05', 20.0, 2.43322e-3, 94.7135, 7771.91)
CHARGE_MPA = [0.5, 1.0, 1.5, 2.0, 3.0]
N_CYCLES = 3
TABLE_PTS = 200                    # table points per cycle for the boundary time series


def graded(L, d_first, d_last):
    """Cells and blockMesh expansion ratio (last/first) for a geometric spacing over L."""
    if abs(d_last / d_first - 1) < 1e-6:
        return max(1, round(L / d_first)), 1.0
    best = None
    for n in range(2, 2000):
        r = (d_last / d_first) ** (1 / (n - 1))
        length = d_first * (r ** n - 1) / (r - 1)
        if best is None or abs(length - L) < abs(best[1] - L):
            best = (n, length)
    return best[0], d_last / d_first


def block_mesh_dict(m):
    th = math.radians(WEDGE / 2)
    xs = [-L_C, 0.0, ZONES[0], ZONES[1], L_T]
    rs = [0.0, R_T, R_P]
    verts, idx = [], {}

    def v(i, j, side):
        key = (i, 0, 0) if j == 0 else (i, j, side)
        if key not in idx:
            r = rs[j]
            idx[key] = len(verts)
            verts.append((xs[i], r * math.cos(th), (-1 if side == 0 else 1) * r * math.sin(th)))
        return idx[key]

    def hexv(i0, i1, j0, j1):
        return [v(i0, j0, 0), v(i1, j0, 0), v(i1, j1, 0), v(i0, j1, 0),
                v(i0, j0, 1), v(i1, j0, 1), v(i1, j1, 1), v(i0, j1, 1)]

    # spacing: fine at the port edge (x = 0, r = R_T), coarse away from it
    n_r, g_r = graded(R_T, m['r_axis'], m['r_wall'])          # tube radius: axis -> wall
    n_a, g_a = graded(R_P - R_T, m['edge_r'], m['far'])       # chamber annulus: port edge -> bore
    n_c, g_c = graded(L_C, m['far'], m['edge_x'])             # chamber length: piston -> port wall
    n_1, g_1 = graded(ZONES[0], m['edge_x'], m['tube'])       # tube: port -> first zone
    n_2 = round((ZONES[1] - ZONES[0]) / m['tube'])
    n_3 = round((L_T - ZONES[1]) / m['tube'])
    blocks = [
        (hexv(0, 1, 0, 1), (n_c, n_r), (g_c, g_r)),      # chamber core
        (hexv(0, 1, 1, 2), (n_c, n_a), (g_c, g_a)),      # chamber annulus
        (hexv(1, 2, 0, 1), (n_1, n_r), (g_1, g_r)),      # tube to zone 1
        (hexv(2, 3, 0, 1), (n_2, n_r), (1, g_r)),        # zone 1 -> zone 2
        (hexv(3, 4, 0, 1), (n_3, n_r), (1, g_r)),        # zone 2 -> outlet
    ]
    n_cells = sum(a * b for _, (a, b), _ in blocks)

    def face_x(i, j0, j1):                           # x = const face between radii j0..j1
        return f'({v(i, j0, 0)} {v(i, j1, 0)} {v(i, j1, 1)} {v(i, j0, 1)})'

    def face_r(j, i0, i1):                           # r = const face between i0..i1
        return f'({v(i0, j, 0)} {v(i1, j, 0)} {v(i1, j, 1)} {v(i0, j, 1)})'

    def wedge_faces(side):
        out = []
        for (i0, i1, j0, j1) in [(0, 1, 0, 1), (0, 1, 1, 2), (1, 2, 0, 1), (2, 3, 0, 1), (3, 4, 0, 1)]:
            out.append(f'({v(i0, j0, side)} {v(i1, j0, side)} {v(i1, j1, side)} {v(i0, j1, side)})')
        return ' '.join(out)

    vtxt = '\n'.join(f'    ({x:.9g} {y:.9g} {z:.9g})  // {k}' for k, (x, y, z) in enumerate(verts))
    btxt = '\n'.join(f'    hex ({" ".join(map(str, h))}) ({a} {b} 1) simpleGrading ({ga:.6g} {gb:.6g} 1)'
                     for h, (a, b), (ga, gb) in blocks)
    body = f"""scale 1;

vertices
(
{vtxt}
);

blocks
(
{btxt}
);

boundary
(
    piston      {{ type wall;  faces ( {face_x(0, 0, 1)} {face_x(0, 1, 2)} ); }}
    portWall    {{ type wall;  faces ( {face_x(1, 1, 2)} ); }}
    chamberWall {{ type wall;  faces ( {face_r(2, 0, 1)} ); }}
    tubeWall    {{ type wall;  faces ( {face_r(1, 1, 2)} {face_r(1, 2, 3)} {face_r(1, 3, 4)} ); }}
    outlet      {{ type patch; faces ( {face_x(4, 0, 1)} ); }}
    front       {{ type wedge; faces ( {wedge_faces(0)} ); }}
    back        {{ type wedge; faces ( {wedge_faces(1)} ); }}
);
"""
    info = dict(R_p=R_P, L_c=L_C, r_t=R_T, L_t=L_T, d=D_T, zones=ZONES, wedge_deg=WEDGE, cells=n_cells,
                A_p=A_P, A_c=A_C, wedge_A_p=0.5 * R_P ** 2 * math.sin(math.radians(WEDGE)),
                wedge_A_t=0.5 * R_T ** 2 * math.sin(math.radians(WEDGE)), l_coil=L_COIL, rho=RHO, nu=NU)
    return body, info


TOPOSET = """actions
(
    { name z300s; type faceSet;     action new; source boxToFace; box (0.2999 -1 -1) (0.3001 1 1); }
    { name z300;  type faceZoneSet; action new; source setToFaceZone; faceSet z300s; }
    { name z450s; type faceSet;     action new; source boxToFace; box (0.4499 -1 -1) (0.4501 1 1); }
    { name z450;  type faceZoneSet; action new; source setToFaceZone; faceSet z450s; }
);
"""


def monitor(name, region_type, region, operation, fields, weight=None):
    w = f'\n        weightField     {weight};' if weight else ''
    return f"""    {name}
    {{
        type            surfaceFieldValue;
        libs            (fieldFunctionObjects);
        log             false;
        writeControl    timeStep;
        writeInterval   1;
        writeFields     false;
        regionType      {region_type};
        name            {region};
        operation       {operation};{w}
        fields          ({fields});
    }}
"""


def monitors(p='p'):
    return (monitor('pPiston', 'patch', 'piston', 'areaAverage', p) +
            monitor('qPiston', 'patch', 'piston', 'sum', 'phi') +
            monitor('qOutlet', 'patch', 'outlet', 'sum', 'phi') +
            monitor('pOutlet', 'patch', 'outlet', 'areaAverage', p) +
            ''.join(monitor(f'z{z}', 'faceZone', f'z{z}', 'areaAverage', p) +
                    monitor(f'ke{z}', 'faceZone', f'z{z}', 'weightedAverage', 'magSqr(U)', 'phi')
                    for z in ('300', '450')))


MAGSQR = """    magSqrU
    {
        type            magSqr;
        libs            (fieldFunctionObjects);
        field           U;
        writeControl    timeStep;
        writeInterval   1;
        log             false;
    }
"""

WALLS = """    portWall    { type noSlip; }
    chamberWall { type noSlip; }
    tubeWall    { type noSlip; }
    front       { type wedge; }
    back        { type wedge; }"""


def schemes(transient, multiphase=False):
    if multiphase:
        return """ddtSchemes      { default Euler; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(phi,alpha)  Gauss vanLeer;
    div(phirb,alpha) Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes        { default Gauss linear corrected; }
interpolationSchemes    { default linear; }
snGradSchemes           { default corrected; }
"""
    ddt = 'Euler' if transient else 'steadyState'
    div = 'Gauss linearUpwind grad(U)' if transient else 'bounded Gauss linearUpwind grad(U)'
    return f"""ddtSchemes      {{ default {ddt}; }}
gradSchemes     {{ default Gauss linear; }}
divSchemes
{{
    default         none;
    div(phi,U)      {div};
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}
laplacianSchemes        {{ default Gauss linear corrected; }}
interpolationSchemes    {{ default linear; }}
snGradSchemes           {{ default corrected; }}
"""


def single_phase_constant(case):
    write(os.path.join(case, 'constant', 'transportProperties'), 'dictionary', 'transportProperties',
          f'transportModel  Newtonian;\nnu              {NU:.8e};   // ISO VG 32 oil, mu = 0.028 Pa s, rho = 870\n')
    write(os.path.join(case, 'constant', 'turbulenceProperties'), 'dictionary', 'turbulenceProperties',
          'simulationType  laminar;\n')


def make_steady(direction, Re):
    v = Re * NU / D_T
    up = v * (R_T / R_P) ** 2                       # piston speed giving tube bulk speed v
    case = os.path.join(root, f'{direction}_re{Re:05d}')
    if direction == 'in':
        u_piston, u_out, p_out = up, """type inletOutlet; inletValue uniform (0 0 0); value uniform (0 0 0);""", 'fixedValue'
    else:
        u_piston, u_out, p_out = -up, """type pressureInletOutletVelocity; value uniform (0 0 0);""", 'fixedValue'
    write(os.path.join(case, '0', 'U'), 'volVectorField', 'U', f"""dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    piston      {{ type fixedValue; value uniform ({u_piston:.10e} 0 0); }}   // tube bulk {v:.5f} m/s, Re {Re}
    outlet      {{ {u_out} }}
{WALLS}
}}
""")
    write(os.path.join(case, '0', 'p'), 'volScalarField', 'p', f"""dimensions      [0 2 -2 0 0 0 0];   // kinematic p/rho
internalField   uniform 0;
boundaryField
{{
    piston      {{ type zeroGradient; }}
    outlet      {{ type {p_out}; value uniform 0; }}
    portWall    {{ type zeroGradient; }}
    chamberWall {{ type zeroGradient; }}
    tubeWall    {{ type zeroGradient; }}
    front       {{ type wedge; }}
    back        {{ type wedge; }}
}}
""")
    single_phase_constant(case)
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict', f"""application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         4000;
deltaT          1;
writeControl    timeStep;
writeInterval   4000;
purgeWrite      1;
writeFormat     binary;
writePrecision  8;
timeFormat      general;
runTimeModifiable false;

functions
{{
{MAGSQR}{monitors()}}}
""")
    write(os.path.join(case, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes', schemes(False))
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', """solvers
{
    p   { solver GAMG; smoother DICGaussSeidel; tolerance 1e-9; relTol 0.05; }
    U   { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol 0.1; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
    residualControl { p 1e-7; U 1e-8; }
}
relaxationFactors
{
    fields      { p 0.3; }
    equations   { U 0.7; }
}
""")
    json.dump(dict(case=os.path.basename(case), direction=direction, Re=Re, v_tube=v, u_piston=up),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


def kinematics(f, X):
    """Piston motion x = -X cos(wt) (starts at rest at the end of its stroke): time, velocity,
    acceleration tables over N_CYCLES."""
    w = 2 * math.pi * f
    t = np.linspace(0, N_CYCLES / f, N_CYCLES * TABLE_PTS + 1)
    return t, X * w * np.sin(w * t), X * w ** 2 * np.cos(w * t)


def coupled_outlet_pressure(spec):
    """Pressure at the modelled tube end [Pa, gauge]: the rest of the half-coil, from the torus CFD."""
    _, f, X, b, c = spec
    t, xd, xdd = kinematics(f, X)
    phi = (L_COIL / 2 - L_T) / L_COIL
    return t, xd, phi * (b * xdd + c * xd) / A_P, phi


def table(t, vals, vector=False):
    rows = [f'({ti:.8e} ({vi:.8e} 0 0))' if vector else f'({ti:.8e} {vi:.8e})' for ti, vi in zip(t, vals)]
    return 'table\n        (\n            ' + '\n            '.join(rows) + '\n        )'


def transient_control(app, f, extra_monitors, max_co):
    return f"""application     {app};
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {N_CYCLES / f:.8g};
deltaT          1e-7;
adjustTimeStep  yes;
maxCo           {max_co};
maxAlphaCo      {max_co};
maxDeltaT       {1 / f / 400:.6g};
writeControl    adjustableRunTime;
writeInterval   {1 / f / 24:.8g};     // 24 frames per cycle (ParaView animation)
purgeWrite      0;
writeFormat     binary;
writePrecision  8;
timeFormat      general;
runTimeModifiable false;

functions
{{
{extra_monitors}}}
"""


def make_osc(spec):
    name, f, X, b, c = spec
    case = os.path.join(root, f'osc_{name}')
    t, xd, p_end, phi = coupled_outlet_pressure(spec)
    write(os.path.join(case, '0', 'U'), 'volVectorField', 'U', f"""dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    piston                                   // x = -{X * 1e3:.3f} mm * cos(2 pi {f:g} t)
    {{
        type            uniformFixedValue;
        uniformValue    {table(t, xd, vector=True)};
    }}
    outlet      {{ type pressureInletOutletVelocity; value uniform (0 0 0); }}
{WALLS}
}}
""")
    write(os.path.join(case, '0', 'p'), 'volScalarField', 'p', f"""dimensions      [0 2 -2 0 0 0 0];   // kinematic p/rho
internalField   uniform 0;
boundaryField
{{
    piston      {{ type zeroGradient; }}
    outlet                                   // rest of the half-coil: phi*(b*xddot + c*xdot)/(A_p*rho), phi = {phi:.4f}
    {{
        type            uniformFixedValue;
        uniformValue    {table(t, p_end / RHO)};
    }}
    portWall    {{ type zeroGradient; }}
    chamberWall {{ type zeroGradient; }}
    tubeWall    {{ type zeroGradient; }}
    front       {{ type wedge; }}
    back        {{ type wedge; }}
}}
""")
    single_phase_constant(case)
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict',
          transient_control('pimpleFoam', f, MAGSQR + monitors(), 0.8))
    write(os.path.join(case, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes', schemes(True))
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', """solvers
{
    p       { solver GAMG; smoother DICGaussSeidel; tolerance 1e-8; relTol 0.01; }
    pFinal  { $p; relTol 0; }
    "U.*"   { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0; }
}
PIMPLE
{
    momentumPredictor   yes;
    nOuterCorrectors    1;
    nCorrectors         2;
    nNonOrthogonalCorrectors 0;
}
""")
    json.dump(dict(case=os.path.basename(case), cfd_case=name, f=f, X=X, b_eq=b, c_eq=c, phi=phi, n_cycles=N_CYCLES),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


CAV_MONITORS = """    vapour
    {
        type            volFieldValue;
        libs            (fieldFunctionObjects);
        log             false;
        writeControl    timeStep;
        writeInterval   1;
        writeFields     false;
        regionType      all;
        operation       volIntegrate;
        fields          (alpha.water);
    }
    pMin
    {
        type            volFieldValue;
        libs            (fieldFunctionObjects);
        log             false;
        writeControl    timeStep;
        writeInterval   1;
        writeFields     false;
        regionType      all;
        operation       min;
        fields          (p);
    }
"""


def make_cav(spec, p_charge):
    name, f, X, b, c = spec
    case = os.path.join(root, f'cav_p{round(p_charge / 1e3):05d}k')
    t, xd, p_end, phi = coupled_outlet_pressure(spec)
    write(os.path.join(case, '0', 'U'), 'volVectorField', 'U', f"""dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{{
    piston
    {{
        type            uniformFixedValue;
        uniformValue    {table(t, xd, vector=True)};
    }}
    outlet      {{ type pressureInletOutletVelocity; value uniform (0 0 0); }}
{WALLS}
}}
""")
    write(os.path.join(case, '0', 'p_rgh'), 'volScalarField', 'p_rgh', f"""dimensions      [1 -1 -2 0 0 0 0];   // absolute pressure [Pa] (g = 0)
internalField   uniform {p_charge:.6g};
boundaryField
{{
    piston      {{ type fixedFluxPressure; value uniform {p_charge:.6g}; }}
    outlet                                   // charge pressure + rest of the half-coil (torus CFD, {name})
    {{
        type            uniformFixedValue;
        uniformValue    {table(t, p_charge + p_end)};
    }}
    portWall    {{ type fixedFluxPressure; value uniform {p_charge:.6g}; }}
    chamberWall {{ type fixedFluxPressure; value uniform {p_charge:.6g}; }}
    tubeWall    {{ type fixedFluxPressure; value uniform {p_charge:.6g}; }}
    front       {{ type wedge; }}
    back        {{ type wedge; }}
}}
""")
    write(os.path.join(case, '0', 'alpha.water'), 'volScalarField', 'alpha.water', f"""dimensions      [0 0 0 0 0 0 0];   // liquid oil volume fraction
internalField   uniform 1;
boundaryField
{{
    piston      {{ type zeroGradient; }}
    outlet      {{ type inletOutlet; inletValue uniform 1; value uniform 1; }}
    portWall    {{ type zeroGradient; }}
    chamberWall {{ type zeroGradient; }}
    tubeWall    {{ type zeroGradient; }}
    front       {{ type wedge; }}
    back        {{ type wedge; }}
}}
""")
    write(os.path.join(case, 'constant', 'transportProperties'), 'dictionary', 'transportProperties', f"""phases          (water vapour);    // "water" = liquid oil (solver naming)
phaseChangeTwoPhaseMixture SchnerrSauer;
pSat            {P_SAT:g};       // oil vapour / air-release pressure [Pa]
sigma           0.03;
water           {{ transportModel Newtonian; nu {NU:.8e}; rho {RHO:g}; }}
vapour          {{ transportModel Newtonian; nu 4.273e-04; rho 0.02308; }}
SchnerrSauerCoeffs
{{
    n       1.6e+13;
    dNuc    2.0e-06;
    Cc      1;
    Cv      1;
}}
""")
    write(os.path.join(case, 'constant', 'turbulenceProperties'), 'dictionary', 'turbulenceProperties',
          'simulationType  laminar;\n')
    write(os.path.join(case, 'constant', 'g'), 'uniformDimensionedVectorField', 'g',
          'dimensions      [0 1 -2 0 0 0 0];\nvalue           (0 0 0);\n')
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict',
          transient_control('interPhaseChangeFoam', f, MAGSQR + CAV_MONITORS + monitors('p'), 0.5))
    write(os.path.join(case, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes', schemes(True, multiphase=True))
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', """solvers
{
    "alpha.water.*"
    {
        cAlpha 0; nAlphaCorr 2; nAlphaSubCycles 1; MULESCorr yes; nLimiterIter 5;
        solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0; maxIter 10;
    }
    "U.*"       { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0; }
    p_rgh       { solver GAMG; tolerance 1e-8; relTol 0.05; smoother DICGaussSeidel; maxIter 20; }
    p_rghFinal  { $p_rgh; tolerance 1e-7; relTol 0; maxIter 30; }
    "pcorr.*"   { $p_rgh; relTol 0; }
}
PIMPLE
{
    momentumPredictor   no;
    nOuterCorrectors    1;
    nCorrectors         3;
    nNonOrthogonalCorrectors 0;
}
""")
    json.dump(dict(case=os.path.basename(case), cfd_case=name, f=f, X=X, b_eq=b, c_eq=c, phi=phi,
                   p_charge=p_charge, p_sat=P_SAT, n_cycles=N_CYCLES),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


ALLRUN = r"""#!/bin/bash
# Piston chamber + port set: mesh once, then run every case serially, several at once.
#   ./Allrun [nParallelCases]      (default 8)
cd "${0%/*}" || exit 1
NJ=${1:-8}
command -v simpleFoam >/dev/null || { echo "OpenFOAM environment not loaded"; exit 1; }
( cd mesh && blockMesh > log.blockMesh 2>&1 && topoSet > log.topoSet 2>&1 && checkMesh > log.checkMesh 2>&1 ) \
    || { echo "meshing failed, see mesh/log.*"; exit 1; }
grep -E "cells:|Mesh OK|Failed" mesh/log.checkMesh
run_case() {
    c=$1
    rm -rf "$c/constant/polyMesh" "$c/postProcessing"
    cp -r mesh/constant/polyMesh "$c/constant/"
    cd "$c" || return
    app=$(foamDictionary -entry application -value system/controlDict)
    $app > log.$app 2>&1
    if grep -q "^End" log.$app; then echo "$c: finished"; else echo "$c: FAILED, see $c/log.$app"; fi
}
export -f run_case
# longest cases first
ls -d cav_* osc_* in_* out_* 2>/dev/null | xargs -P "$NJ" -I{} bash -c 'run_case {}'
echo "Done."
"""


def write_set(name, mesh_name, steady_re, transient):
    global root
    root = os.path.join(OF, name)
    body, info = block_mesh_dict(MESHES[mesh_name])
    info['mesh'] = mesh_name
    mesh = os.path.join(root, 'mesh')
    write(os.path.join(mesh, 'system', 'blockMeshDict'), 'dictionary', 'blockMeshDict', body)
    write(os.path.join(mesh, 'system', 'topoSetDict'), 'dictionary', 'topoSetDict', TOPOSET)
    write(os.path.join(mesh, 'system', 'controlDict'), 'dictionary', 'controlDict',
          'application blockMesh;\nstartFrom startTime;\nstartTime 0;\nstopAt endTime;\nendTime 1;\ndeltaT 1;\n'
          'writeControl timeStep;\nwriteInterval 1;\n')
    for fname in ('fvSchemes', 'fvSolution'):               # topoSet/checkMesh need them to exist
        write(os.path.join(mesh, 'system', fname), 'dictionary', fname, schemes(False) if fname == 'fvSchemes' else '')
    json.dump(info, open(os.path.join(mesh, 'mesh_info.json'), 'w'), indent=2)
    for Re in steady_re:
        make_steady('in', Re)
        make_steady('out', Re)
    if transient:
        make_osc(T04)
        for pc in CHARGE_MPA:
            make_cav(T05, pc * 1e6)
    with open(os.path.join(root, 'Allrun'), 'w', newline='\n') as fh:
        fh.write(ALLRUN)
    print(f'wrote {root}: {mesh_name} mesh, {info["cells"]} cells')


def main():
    write_set('chamber', 'fine', STEADY_RE, transient=False)
    write_set('chamber_transient', 'coarse', [250, 1000], transient=True)


if __name__ == '__main__':
    main()
