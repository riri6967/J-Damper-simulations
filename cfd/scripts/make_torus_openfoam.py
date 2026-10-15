"""Generate OpenFOAM cases on a rotationally periodic TORUS SECTOR (fully developed flow).

Why: in the developed part of the helix the flow is the same at every turn (S01 showed
turns 2-4 identical), so a short periodic sector reproduces it at ~1/100 of the cost of the
full helix. The helix pitch (torsion ~0.05) is neglected; its effect is measured by the steady
set (torus vs helix S01 at the same Re).

The flow is driven by a kinematic pressure jump across the cyclic pair cyc0/cyc1
(uniformJump):  constant -> steady sets, sine -> oscillatory sets. The resulting flow rate
is monitored on cyc1 every step, so the case is fully characterised by (jump(t), Q(t)).

Sets written to cfd/openfoam/<name>/:
    torus_steady[_<mesh>]  steady simpleFoam, Re ~ 100..4000 (compare with the helix S01)
    torus_oscillatory[_<mesh>]  oscillatory pimpleFoam, cases T01..T10 of case_matrix.csv

Usage:  python make_torus_openfoam.py [--mesh medium|fine|xfine] [--sets steady osc]
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_s01_openfoam import write, NU, RHO, MU   # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
D_P = 40e-3
A_P = math.pi * D_P ** 2 / 4
SECTOR_DEG, SECTOR_CELLS = 10.0, 2
MESHES = {'medium': (12, 12), 'fine': (16, 16), 'xfine': (21, 21)}   # (n, m), ratio ~1.33
STEADY_RE = [100, 250, 500, 1000, 2000, 4000]
STEPS_PER_CYCLE = 400


def ito_ratio(De):
    return max(1.0, 21.5 * De / (1.56 + math.log10(De)) ** 5.73) if De > 13.5 else 1.0


def jump_estimate(v, d, R):
    """Kinematic pressure gradient [m/s^2] for steady bulk velocity v (Ito correlation)."""
    Re = v * d / NU
    f = 64 / Re * ito_ratio(Re * math.sqrt(d / 2 / R))
    return f / d * 0.5 * v ** 2


def osc_gradient_amplitude(v_amp, f, d, R):
    """Kinematic pressure-gradient amplitude giving bulk-velocity amplitude ~v_amp:
    Womersley impedance with its viscous part scaled by the curved-pipe (Ito) factor."""
    from scipy.special import jv
    w = 2 * math.pi * f
    alpha = d / 2 * math.sqrt(w / NU)
    L = alpha * np.exp(1j * 3 * np.pi / 4)
    Z = 1j * w / (1 - 2 * jv(1, L) / (L * jv(0, L)))          # G = Z * u  (straight pipe)
    De_rms = v_amp / math.sqrt(2) * d / NU * math.sqrt(d / 2 / R)
    Zc = 1j * Z.imag + Z.real * ito_ratio(De_rms)
    return abs(Zc) * v_amp


def common_files(case, info, p_jump_entry, transient):
    s = info['s_sector']
    write(os.path.join(case, '0', 'U'), 'volVectorField', 'U', """dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);

boundaryField
{
    wall    { type noSlip; }
    cyc0    { type cyclic; }
    cyc1    { type cyclic; }
}
""")
    write(os.path.join(case, '0', 'p'), 'volScalarField', 'p', f"""dimensions      [0 2 -2 0 0 0 0];   // kinematic pressure p/rho
internalField   uniform 0;

boundaryField
{{
    wall    {{ type zeroGradient; }}
    cyc0                                    // drives the flow: p jump over the {SECTOR_DEG:g} deg sector (s = {s:.6e} m)
    {{
        type            uniformJump;
        patchType       cyclic;
        jumpTable       {p_jump_entry};
        value           uniform 0;
    }}
    cyc1
    {{
        type            uniformJump;
        patchType       cyclic;
        value           uniform 0;
    }}
}}
""")
    write(os.path.join(case, 'constant', 'transportProperties'), 'dictionary', 'transportProperties',
          f'transportModel  Newtonian;\nnu              {NU:.8e};   // ISO VG 32 oil: mu = {MU}, rho = {RHO}\n')
    write(os.path.join(case, 'constant', 'turbulenceProperties'), 'dictionary', 'turbulenceProperties',
          'simulationType  laminar;\n')
    ddt = 'backward' if transient else 'steadyState'
    div = 'Gauss linearUpwind grad(U)' if transient else 'bounded Gauss linearUpwind grad(U)'
    write(os.path.join(case, 'system', 'fvSchemes'), 'dictionary', 'fvSchemes', f"""ddtSchemes      {{ default {ddt}; }}
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
""")


FLUX_MONITOR = """    flux
    {
        type            surfaceFieldValue;
        libs            (fieldFunctionObjects);
        log             false;
        writeControl    timeStep;
        writeInterval   1;
        writeFields     false;
        regionType      patch;
        name            cyc1;
        operation       sum;
        fields          (phi);
    }
"""


def make_steady(root, Re, info):
    v = Re * NU / info['d']
    G = jump_estimate(v, info['d'], info['R_h'])
    case = os.path.join(root, f're{Re:05d}')
    common_files(case, info, f'constant {G * info["s_sector"]:.10e}', transient=False)
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict', f"""application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         5000;
deltaT          1;
writeControl    timeStep;
writeInterval   5000;
writeFormat     binary;
writePrecision  10;
timeFormat      general;
runTimeModifiable true;

functions
{{
{FLUX_MONITOR}}}
""")
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', """solvers
{
    p { solver GAMG; smoother DICGaussSeidel; tolerance 1e-10; relTol 0.01; }
    U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-12; relTol 0.01; }
}
// Plain SIMPLE with under-relaxation: SIMPLEC (consistent yes) drifted ~5% and stalled
// on this periodic sector; these settings converge in ~1000 iterations.
SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      no;
    pRefCell        0;
    pRefValue       0;
    residualControl { p 1e-8; U 1e-10; }
}
relaxationFactors { fields { p 0.3; } equations { U 0.7; } }
""")
    json.dump(dict(case=f're{Re:05d}', Re_target=Re, G_imposed=G, jump=G * info['s_sector']),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


def make_osc(root, cid, f, X, info):
    w = 2 * math.pi * f
    v_amp = A_P * X * w / (math.pi * info['d'] ** 2 / 4)
    G_amp = osc_gradient_amplitude(v_amp, f, info['d'], info['R_h'])
    n_cyc = max(4, math.ceil(0.4 * f))
    dt = 1 / (f * STEPS_PER_CYCLE)
    case = os.path.join(root, cid)
    jump = f"""
        {{
            type        sine;
            frequency   {f:g};
            amplitude   1;
            scale       {G_amp * info['s_sector']:.10e};   // = G_amp * s_sector
            level       0;
        }}"""
    common_files(case, info, jump, transient=True)
    write(os.path.join(case, 'system', 'controlDict'), 'dictionary', 'controlDict', f"""application     pimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {n_cyc / f:.10g};
deltaT          {dt / 20:.10g};
// Adaptive time step: Courant <= 0.8, never more than 1/{STEPS_PER_CYCLE} of a cycle.
// (A fixed step with Co ~ 4.5 at peak flow diverged in the low-frequency cases.)
adjustTimeStep  yes;
maxCo           0.8;
maxDeltaT       {dt:.10g};
writeControl    adjustableRunTime;
writeInterval   {n_cyc / f:.10g};
writeFormat     binary;
writePrecision  10;
timeFormat      general;
timePrecision   10;
runTimeModifiable true;

functions
{{
{FLUX_MONITOR}}}
""")
    write(os.path.join(case, 'system', 'fvSolution'), 'dictionary', 'fvSolution', """solvers
{
    p { solver GAMG; smoother DICGaussSeidel; tolerance 1e-9; relTol 0.01; }
    pFinal { $p; relTol 0; }
    "(U|UFinal)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-11; relTol 0; }
}
PIMPLE
{
    momentumPredictor   yes;
    nOuterCorrectors    2;
    nCorrectors         2;
    nNonOrthogonalCorrectors 0;
    pRefCell            0;
    pRefValue           0;
}
""")
    json.dump(dict(case=cid, freq=f, X=X, A_p=A_P, v_amp_target=v_amp, G_amp=G_amp,
                   jump_amp=G_amp * info['s_sector'], n_cycles=n_cyc, steps_per_cycle=STEPS_PER_CYCLE,
                   dt=dt, end_time=n_cyc / f, womersley=info['d'] / 2 * math.sqrt(w / NU)),
              open(os.path.join(case, 'case_info.json'), 'w'), indent=2)


ALLRUN = r"""#!/bin/bash
# Run every case of this set, each SERIAL, several at once (tiny meshes: no decomposition).
#   ./Allrun [nParallelCases]      (default 8)
cd "${0%/*}" || exit 1
NJ=${1:-8}
command -v simpleFoam >/dev/null || { echo "OpenFOAM environment not loaded"; exit 1; }
run_case() {
    c=$1
    rm -rf "$c/constant/polyMesh" "$c/postProcessing"
    cp -r mesh/constant/polyMesh "$c/constant/"
    cd "$c" || return
    app=$(foamDictionary -entry application -value system/controlDict)
    checkMesh > log.checkMesh 2>&1
    $app > log.$app 2>&1
    if grep -q "^End" log.$app; then echo "$c: finished ($(grep -m1 'converged in' log.$app))"
    else echo "$c: FAILED, see $c/log.$app"; fi
}
export -f run_case
ls -d re0* T* 2>/dev/null | xargs -P "$NJ" -I{} bash -c 'run_case {}'
echo "Done."
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mesh', choices=list(MESHES), default='fine')
    ap.add_argument('--sets', nargs='+', choices=['steady', 'osc'], default=['steady', 'osc'])
    ap.add_argument('--cases', nargs='*', help='subset of oscillatory case ids')
    args = ap.parse_args()
    n, m = MESHES[args.mesh]
    suffix = '' if args.mesh == 'fine' else f'_{args.mesh}'
    with open(os.path.join(here, '..', 'case_matrix.csv')) as fh:
        osc_cases = [r for r in csv.DictReader(fh) if r['type'] == 'transient']
    if args.cases:
        osc_cases = [r for r in osc_cases if r['case_id'] in args.cases]
    for s in args.sets:
        name = 'torus_steady' if s == 'steady' else 'torus_oscillatory'
        root = os.path.normpath(os.path.join(here, '..', 'openfoam', f'{name}{suffix}'))
        mesh = os.path.join(root, 'mesh')
        subprocess.run([sys.executable, '-I', os.path.join(here, 'make_helix_mesh.py'), '--format', 'foam',
                        '--torus', str(SECTOR_DEG), '--torus-cells', str(SECTOR_CELLS),
                        '--n', str(n), '--m', str(m), '--out', mesh], check=True)
        info = json.load(open(os.path.join(mesh, 'mesh_info.json')))
        if s == 'steady':
            for Re in STEADY_RE:
                make_steady(root, Re, info)
        else:
            for r in osc_cases:
                make_osc(root, r['case_id'], float(r['freq_Hz']), float(r['piston_amp_mm']) * 1e-3, info)
        with open(os.path.join(root, 'Allrun'), 'w', newline='\n') as fh:
            fh.write(ALLRUN)
        print(f'wrote {root}')


if __name__ == '__main__':
    main()
