"""ParaView script: builds the project's CFD views automatically.

Run (from PowerShell in the project folder):   powershell -ExecutionPolicy Bypass -File open_paraview.ps1
or inside ParaView:  View > Python Shell > Run Script... > choose this file.

Layout "Oscillating inerter" (press Play):
    3D view    : 2 turns of the helical channel, streamlines coloured by oil speed, translucent wall
    Slice view : one channel cross-section, colour = speed, arrows = secondary (Dean) flow
    CFD Residuals chart (steady S01 run, Re = 1000)
    Oscillation monitor chart: oil velocity and piston force over the cycle
Layout "Steady helix Re 1000": full 5-turn channel, streamlines, and wall coloured by pressure.
Data: built by build_paraview_cases.py (cfd/paraview/).
"""
import math
import os

from paraview.simple import *  # noqa: F401,F403

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:   # run from the Python shell without __file__: start ParaView from the project folder
    HERE = os.path.join(os.getcwd(), 'cfd', 'paraview')
    if not os.path.isdir(HERE):
        HERE = os.getcwd()

R, PITCH = 0.03, 0.01
CMAP = 'Turbo'
OSC_RANGE = (0.0, 16.0)          # peak oil speed over the 10 Hz cycle is about 15.4 m/s


def try_set(obj, **kw):
    """Set properties that differ between ParaView versions without stopping the script."""
    for k, v in kw.items():
        try:
            setattr(obj, k, v)
        except Exception:
            pass


def foam(case):
    r = OpenFOAMReader(registrationName=case, FileName=os.path.join(HERE, case, 'case.foam'))
    try_set(r, MeshRegions=['internalMesh'], CellArrays=['U', 'p'])
    r.UpdatePipelineInformation()
    return r


def solid(disp):
    """Plain (non-data) colouring; ColorBy(disp, None) is rejected by ParaView 6."""
    try:
        disp.ColorArrayName = ['POINTS', '']
    except Exception:
        ColorBy(disp, None)


def speed_colour(disp, view, title='Oil speed [m/s]', separate=False, rng=None):
    """Colour by speed. separate=True gives this display its own colour map (steady case);
    rng fixes the range so the oscillating flow keeps one scale over the whole cycle."""
    try:
        ColorBy(disp, ('POINTS', 'U', 'Magnitude'), separate)
        lut = GetColorTransferFunction('U', disp, separate=separate)
    except TypeError:                                   # older ParaView: no separate maps
        ColorBy(disp, ('POINTS', 'U', 'Magnitude'))
        lut = GetColorTransferFunction('U')
    try:
        lut.ApplyPreset(CMAP, True)
    except Exception:
        lut.ApplyPreset('Jet', True)
    if rng:
        lut.RescaleTransferFunction(*rng)
        try_set(lut, AutomaticRescaleRangeMode='Never')
    disp.SetScalarBarVisibility(view, True)
    bar = GetScalarBar(lut, view)
    try_set(bar, Title=title, ComponentTitle='', TitleFontSize=14, LabelFontSize=12)
    return lut


def streamlines(src, centre, radius, n=180):
    st = StreamTracer(registrationName='Streamlines', Input=src, SeedType='Point Cloud')
    try_set(st, Vectors=['POINTS', 'U'], IntegrationDirection='BOTH', MaximumStreamlineLength=2.0)
    try_set(st.SeedType, Center=list(centre), Radius=radius, NumberOfPoints=n)
    tubes = Tube(registrationName='StreamTubes', Input=st)
    try_set(tubes, Radius=0.00012)
    return tubes


# ------------------------------------------------------------------ layout 1: oscillating flow
osc = foam('oscillating_helix')
v3d = GetActiveViewOrCreate('RenderView')
layout1 = GetLayout(v3d)
if layout1 is None:                         # batch mode (pvbatch) has no layout yet
    layout1 = CreateLayout('Oscillating inerter')
    AssignViewToLayout(view=v3d, layout=layout1, hint=0)
try:
    RenameLayout('Oscillating inerter', layout1)
except Exception:
    pass
try_set(v3d, Background=[0.13, 0.15, 0.18], OrientationAxesVisibility=1)
try_set(v3d, UseColorPaletteForBackground=0)

wall = Show(osc, v3d)
wall.SetRepresentationType('Surface')
solid(wall)
try_set(wall, Opacity=0.18, DiffuseColor=[0.8, 0.83, 0.86], AmbientColor=[0.8, 0.83, 0.86])

centre1 = (R * math.cos(2 * math.pi * 0.25), R * math.sin(2 * math.pi * 0.25), PITCH * 0.25)   # quarter turn in
tubes = streamlines(osc, centre1, 0.0026)
td = Show(tubes, v3d)
speed_colour(td, v3d, rng=OSC_RANGE)

cut = Slice(registrationName='MidPlane', Input=osc)
try_set(cut, SliceType='Plane')
try_set(cut.SliceType, Origin=[0, 0, PITCH], Normal=[0, 1, 0])
cd = Show(cut, v3d)
speed_colour(cd, v3d, rng=OSC_RANGE)
text = Text(registrationName='Title1')
try_set(text, Text='Oscillating oil flow, 10 Hz, ±5.6 mm stroke')
tdisp = Show(text, v3d)
try_set(tdisp, WindowLocation='Upper Center', FontSize=14)
v3d.CameraPosition = [0.11, -0.13, 0.08]
v3d.CameraFocalPoint = [0.0, 0.0, PITCH]
v3d.CameraViewUp = [0, 0, 1]
v3d.ResetCamera()

# --- slice view: one cross-section with Dean-vortex arrows
# layout cells: 1 = left column (3 = 3D view, 4 = section), 2 = right column (5 = residuals, 6 = monitor)
layout1.SplitHorizontal(0, 0.62)
layout1.SplitVertical(1, 0.6)
layout1.SplitVertical(2, 0.5)
vsec = CreateView('RenderView')
AssignViewToLayout(view=vsec, layout=layout1, hint=4)
try_set(vsec, Background=[0.13, 0.15, 0.18], UseColorPaletteForBackground=0)
th = math.pi                                                     # half a turn in: normal = local tangent
tang = [-R * math.sin(th), R * math.cos(th), PITCH / (2 * math.pi)]
tn = math.sqrt(sum(t * t for t in tang))
nrm = [t / tn for t in tang]
org = [R * math.cos(th), R * math.sin(th), PITCH * th / (2 * math.pi)]
sec = Slice(registrationName='CrossSection', Input=osc)
try_set(sec, SliceType='Plane')
try_set(sec.SliceType, Origin=org, Normal=nrm)
clip = Clip(registrationName='OneSection', Input=sec)            # keep only the section near the origin
try_set(clip, ClipType='Sphere', Invert=1)
try_set(clip.ClipType, Center=org, Radius=0.006)
sd = Show(clip, vsec)
speed_colour(sd, vsec, rng=OSC_RANGE)
calc = Calculator(registrationName='SecondaryFlow', Input=clip)
try_set(calc, ResultArrayName='Usec', AttributeType='Point Data',
        Function='U-(U_X*{0}+U_Y*{1}+U_Z*{2})*({0}*iHat+{1}*jHat+{2}*kHat)'.format(*nrm))
gly = Glyph(registrationName='DeanArrows', Input=calc, GlyphType='Arrow')
try_set(gly, OrientationArray=['POINTS', 'Usec'], ScaleArray=['POINTS', 'Usec'], ScaleFactor=0.0009,
        GlyphMode='Every Nth Point', Stride=6)
gd = Show(gly, vsec)
solid(gd)
try_set(gd, DiffuseColor=[1, 1, 1], AmbientColor=[1, 1, 1])
t2 = Text(registrationName='Title2')
try_set(t2, Text='Cross-section: speed + Dean vortices')
t2d = Show(t2, vsec)
try_set(t2d, WindowLocation='Upper Center', FontSize=12)
vsec.CameraFocalPoint = org
vsec.CameraPosition = [org[i] - 0.03 * nrm[i] for i in range(3)]
vsec.CameraViewUp = [0, 0, 1]
vsec.ResetCamera()

# --- charts
res = CSVReader(registrationName='Residuals', FileName=[os.path.join(HERE, 'residuals_re1000.csv')])
vres = CreateView('XYChartView')
AssignViewToLayout(view=vres, layout=layout1, hint=5)
rd = Show(res, vres)
try_set(rd, UseIndexForXAxis=0, XArrayName='iteration', SeriesVisibility=['Ux', 'Uy', 'Uz', 'p'])
try_set(vres, ChartTitle='Residuals (Re 1000)', LeftAxisLogScale=1,
        LeftAxisTitle='initial residual', BottomAxisTitle='iteration')
osc_csv = CSVReader(registrationName='Oscillation', FileName=[os.path.join(HERE, 'oscillation.csv')])
vmon = CreateView('XYChartView')
AssignViewToLayout(view=vmon, layout=layout1, hint=6)
md = Show(osc_csv, vmon)
try_set(md, UseIndexForXAxis=0, XArrayName='time', SeriesVisibility=['oil_velocity_m_s', 'piston_force_kN'])
try_set(vmon, ChartTitle='One 10 Hz cycle', BottomAxisTitle='time [s]',
        LeftAxisTitle='m/s | kN')

# ------------------------------------------------------------------ layout 2: steady full helix
layout2 = CreateLayout('Steady helix Re 1000')
vst = CreateView('RenderView')
AssignViewToLayout(view=vst, layout=layout2, hint=0)
try_set(vst, Background=[0.13, 0.15, 0.18], UseColorPaletteForBackground=0)
st = foam('helix_steady_re1000')
surf = ExtractSurface(registrationName='HelixWall', Input=st)
sw = Show(surf, vst)
ColorBy(sw, ('POINTS', 'p'))
plut = GetColorTransferFunction('p')
try:
    plut.ApplyPreset('Cool to Warm', True)
except Exception:
    pass
sw.SetScalarBarVisibility(vst, True)
try_set(GetScalarBar(plut, vst), Title='Wall pressure p/rho [m2/s2]', ComponentTitle='', WindowLocation='Lower Left Corner',
        TitleFontSize=14, LabelFontSize=12)
try_set(sw, Opacity=0.35)
inlet_seed = (R, -0.024, -0.0013)                                # in the straight inlet leg
stubes = streamlines(st, inlet_seed, 0.0026, n=150)
sd2 = Show(stubes, vst)
bar2 = GetScalarBar(speed_colour(sd2, vst, separate=True), vst)
try_set(bar2, WindowLocation='Upper Right Corner')
t3 = Text(registrationName='Title3')
try_set(t3, Text='Steady flow, full 5-turn channel, Re 1000')
t3d = Show(t3, vst)
try_set(t3d, WindowLocation='Upper Center', FontSize=14)
vst.CameraPosition = [0.16, -0.16, 0.12]
vst.CameraFocalPoint = [0, 0, 0.025]
vst.CameraViewUp = [0, 0, 1]
vst.ResetCamera()

# ------------------------------------------------------------------ layout 3: the whole device
DEV = os.path.join(HERE, 'device')
def cutaway(src, name):
    """Remove the half facing the camera (y < 0) so the piston inside is visible."""
    c = Clip(registrationName=name, Input=src)
    try_set(c, ClipType='Plane', Invert=1)
    try_set(c.ClipType, Origin=[0, 0, 0], Normal=[0, -1, 0])
    return c


if os.path.isfile(os.path.join(DEV, 'piston.pvd')):
    layout3 = CreateLayout('Whole device')
    vdev = CreateView('RenderView')
    AssignViewToLayout(view=vdev, layout=layout3, hint=0)
    try_set(vdev, Background=[0.13, 0.15, 0.18], UseColorPaletteForBackground=0, OrientationAxesVisibility=1)
    for name, fname, colour, opacity in [('Barrel', 'housing.vtp', [0.75, 0.78, 0.82], 0.35),
                                         ('EndCaps', 'caps.vtp', [0.55, 0.58, 0.62], 0.8)]:
        src = XMLPolyDataReader(registrationName=name, FileName=[os.path.join(DEV, fname)])
        disp = Show(cutaway(src, name + 'Cut'), vdev)
        solid(disp)
        try_set(disp, Opacity=opacity, DiffuseColor=colour, AmbientColor=colour)
    pist = PVDReader(registrationName='PistonAndRod', FileName=os.path.join(DEV, 'piston.pvd'))
    pdisp = Show(pist, vdev)
    solid(pdisp)
    try_set(pdisp, DiffuseColor=[0.86, 0.88, 0.91], AmbientColor=[0.86, 0.88, 0.91], Specular=0.6)
    for name, fname, array, preset, rng, title, where in [
            ('ChamberOil', 'chambers.pvd', 'pressure_MPa', 'Cool to Warm', (-1.5, 1.5),
             'Chamber pressure [MPa]', 'Lower Left Corner'),
            ('CoilOil', 'coil.pvd', 'oil_velocity_m_s', 'Blue Orange (divergent)', (-16, 16),
             'Oil velocity in coil [m/s]', 'Lower Right Corner')]:
        src = PVDReader(registrationName=name, FileName=os.path.join(DEV, fname))
        disp = Show(cutaway(src, name + 'Cut'), vdev)
        ColorBy(disp, ('POINTS', array))
        lut = GetColorTransferFunction(array)
        try:
            lut.ApplyPreset(preset, True)
        except Exception:
            pass
        lut.RescaleTransferFunction(*rng)
        try_set(lut, AutomaticRescaleRangeMode='Never')
        disp.SetScalarBarVisibility(vdev, True)
        try_set(GetScalarBar(lut, vdev), Title=title, ComponentTitle='', WindowLocation=where,
                TitleFontSize=14, LabelFontSize=12)
    t4 = Text(registrationName='Title4')
    try_set(t4, Text='Whole inerter (cutaway): piston, chambers, coil')
    t4d = Show(t4, vdev)
    try_set(t4d, WindowLocation='Upper Center', FontSize=14)
    vdev.CameraPosition = [0.10, -0.22, 0.13]
    vdev.CameraFocalPoint = [0.0, 0.0, 0.0]
    vdev.CameraViewUp = [0, 0, 1]
    vdev.ResetCamera()

# ------------------------------------------------------------------ layout 4: piston chamber CFD
def chamber_view(case, layout, hint, colour_array, preset, rng, title, label, time_scale=1.0):
    """One axisymmetric chamber case, mirrored across the axis to show the full section."""
    view = CreateView('RenderView')
    AssignViewToLayout(view=view, layout=layout, hint=hint)
    try_set(view, Background=[0.13, 0.15, 0.18], UseColorPaletteForBackground=0, OrientationAxesVisibility=0)
    r = OpenFOAMReader(registrationName=case, FileName=os.path.join(HERE, case, 'case.foam'))
    try_set(r, MeshRegions=['internalMesh'])
    r.UpdatePipelineInformation()
    src = r
    if time_scale != 1.0:                       # stretch so one cycle spans the same Play range
        src = TemporalShiftScale(registrationName=case + 'Time', Input=r)
        try_set(src, Scale=time_scale)
    if colour_array == 'vapour':
        src = Calculator(registrationName=case + 'Vapour', Input=src)
        try_set(src, AttributeType='Cell Data', ResultArrayName='vapour', Function='1-"alpha.water"')
    try:                                        # ParaView 6: AxisAlignedReflect; older: Reflect
        mirror = AxisAlignedReflect(registrationName=case + 'Mirror', Input=src)
        try_set(mirror, PlaneMode='Y Min')      # the axis is at y = 0, the lowest y of the wedge
    except NameError:
        mirror = Reflect(registrationName=case + 'Mirror', Input=src)
        try_set(mirror, Plane='Y Min')
    d = Show(mirror, view)
    ColorBy(d, ('CELLS', colour_array, 'Magnitude') if colour_array == 'U' else ('CELLS', colour_array))
    lut = GetColorTransferFunction(colour_array)
    try:
        lut.ApplyPreset(preset, True)
    except Exception:
        pass
    lut.RescaleTransferFunction(*rng)
    try_set(lut, AutomaticRescaleRangeMode='Never')
    d.SetScalarBarVisibility(view, True)
    try_set(GetScalarBar(lut, view), Title=label, ComponentTitle='', WindowLocation='Lower Right Corner',
            TitleFontSize=13, LabelFontSize=11)
    if colour_array == 'U':                     # flow direction arrows on the mid-plane
        cut = Slice(registrationName=case + 'MidPlane', Input=mirror)
        try_set(cut, SliceType='Plane')
        try_set(cut.SliceType, Origin=[0, 0, 0], Normal=[0, 0, 1])
        pts = CellCenters(registrationName=case + 'Centres', Input=cut)
        g = Glyph(registrationName=case + 'Arrows', Input=pts, GlyphType='Arrow')
        try_set(g, OrientationArray=['POINTS', 'U'], ScaleArray=['POINTS', 'No scale array'], ScaleFactor=0.0016,
                GlyphMode='Every Nth Point', Stride=9)
        gd = Show(g, view)
        solid(gd)
        try_set(gd, DiffuseColor=[1, 1, 1], AmbientColor=[1, 1, 1], Opacity=0.7)
    t = Text(registrationName=case + 'Title')
    try_set(t, Text=title)
    td = Show(t, view)
    try_set(td, WindowLocation='Upper Center', FontSize=13)
    view.CameraFocalPoint = [0.0, 0, 0]
    view.CameraPosition = [0.0, 0, 0.12]
    view.CameraViewUp = [0, 1, 0]
    try_set(view, CameraParallelProjection=1, CameraParallelScale=0.0225)
    return view


if os.path.isfile(os.path.join(HERE, 'piston_chamber', 'case.foam')):
    layout4 = CreateLayout('Piston chamber CFD')
    layout4.SplitHorizontal(0, 0.5)
    chamber_view('piston_chamber', layout4, 1, 'U', 'Turbo', (0, 20),
                 'Piston chamber + port: oil speed (10 Hz)', 'Oil speed [m/s]')
    if os.path.isfile(os.path.join(HERE, 'cavitation_1MPa', 'case.foam')):
        chamber_view('cavitation_1MPa', layout4, 2, 'vapour', 'Inferno (matplotlib)', (0, 1),
                     'Cavitation at 1 MPa charge (20 Hz)', 'Vapour fraction', time_scale=2.0)

# ------------------------------------------------------------------ animation
scene = GetAnimationScene()
scene.UpdateAnimationUsingDataTimeSteps()
try_set(scene, PlayMode='Snap To TimeSteps')
SetActiveView(v3d)
Render(v3d)
print('Views ready. Press Play (green triangle) to animate the oscillating flow.')
