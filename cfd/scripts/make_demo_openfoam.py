"""Generate the flow-visualisation ('demo') case set from the validated torus cases.

Copies cases from cfd/openfoam/torus_oscillatory and cfd/openfoam/torus_steady and adds a
`surfaces` function object that writes the velocity on the channel cross-section (the cyclic
patch cyc1, at theta = 10 deg) as raw x y z Ux Uy Uz:
    oscillatory cases: 48 snapshots over the last cycle (writeControl adjustableRunTime)
    steady cases:      one snapshot at the end
render_demo.py turns these into the animation and the Dean-vortex figure.

Writes cfd/openfoam/torus_demo/{mesh, osc_X2, osc_X5, st_re00100, st_re00500, st_re02000, Allrun}.
Usage: python make_demo_openfoam.py
"""
import json
import os
import re
import shutil

here = os.path.dirname(os.path.abspath(__file__))
base = os.path.normpath(os.path.join(here, '..', 'openfoam'))
out = os.path.join(base, 'torus_demo')
FRAMES = 48
OSC = {'osc_X2': 'T09', 'osc_X5': 'T04'}            # 10 Hz, nominal stroke 2 mm and 5 mm
STEADY = ['re00100', 're00500', 're02000']


def surfaces_fo(control):
    return f"""    section
    {{
        type            surfaces;
        libs            (sampling);
        log             false;
        {control}
        surfaceFormat   raw;
        fields          (U);
        interpolationScheme cell;
        surfaces
        {{
            cyc1
            {{
                type        patch;
                patches     (cyc1);
                interpolate false;
            }}
        }}
    }}
"""


def add_fo(case, block):
    cd = os.path.join(case, 'system', 'controlDict')
    t = open(cd).read()
    i = t.rindex('}')                     # closing brace of the functions dictionary
    open(cd, 'w', newline='\n').write(t[:i] + block + t[i:])


def copy_case(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('postProcessing', 'log.*', 'processor*', '[1-9]*', '0.*'))


def main():
    os.makedirs(out, exist_ok=True)
    mesh = os.path.join(out, 'mesh')
    if os.path.isdir(mesh):
        shutil.rmtree(mesh)
    shutil.copytree(os.path.join(base, 'torus_oscillatory', 'mesh'), mesh)
    for name, src in OSC.items():
        dst = os.path.join(out, name)
        copy_case(os.path.join(base, 'torus_oscillatory', src), dst)
        m = json.load(open(os.path.join(dst, 'case_info.json')))
        T = 1 / m['freq']
        start = m['end_time'] - T
        add_fo(dst, surfaces_fo(f'writeControl    adjustableRunTime;\n        writeInterval   {T / FRAMES:.10g};\n'
                                f'        timeStart       {start - 1e-9:.10g};'))
        # coarser snapshots over the WHOLE run, for the live viewer (watch_live.py)
        add_fo(dst, surfaces_fo(f'writeControl    adjustableRunTime;\n        writeInterval   {T / 16:.10g};')
               .replace('    section\n', '    live\n', 1))
        m['frames'] = FRAMES
        json.dump(m, open(os.path.join(dst, 'case_info.json'), 'w'), indent=2)
    for name in STEADY:
        dst = os.path.join(out, 'st_' + name)
        copy_case(os.path.join(base, 'torus_steady', name), dst)
        add_fo(dst, surfaces_fo('writeControl    writeTime;'))
    shutil.copy(os.path.join(base, 'torus_oscillatory', 'Allrun'), os.path.join(out, 'Allrun'))
    # Allrun picks cases by name pattern: make it run every case folder here
    t = open(os.path.join(out, 'Allrun')).read().replace('ls -d re0* T* 2>/dev/null', 'ls -d osc_* st_* 2>/dev/null')
    open(os.path.join(out, 'Allrun'), 'w', newline='\n').write(t)
    print(f'wrote {out}: {", ".join(list(OSC) + ["st_" + s for s in STEADY])}')


if __name__ == '__main__':
    main()
