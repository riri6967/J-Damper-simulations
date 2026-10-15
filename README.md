# CFD Characterisation of a Helical-Channel Fluid Inerter for Race-Car Suspension

**Tools:** OpenFOAM v2406 (CFD, run under WSL) + Python (meshing, post-processing, vehicle models). All free and open source.
The `matlab/` folder holds equivalent MATLAB versions of the vehicle scripts (for MATLAB Online or a university licence).
**Type:** Simulation-only (CFD acts as the "virtual test rig")

## 1. Background

An *inerter* is a two-terminal suspension element whose force is proportional to the
**relative acceleration** between its ends: `F = b (a1 - a2)`, where `b` is the
*inertance* in kg (Smith, 2002). McLaren raced one in F1 (2005-2007) under the codename
"J-damper". A **fluid inerter** produces inertance hydraulically: a piston forces oil through a
long, narrow helical channel, and the fast-moving oil column acts as a large effective mass.

The ideal model `F = b·ẍ` ignores the real fluid dynamics:

- **Viscous and curvature losses.** Dean vortices in the curved channel raise the pressure drop above
  straight-pipe values. This adds *parasitic damping*.
- **Unsteady (oscillatory) flow effects.** When the Womersley number is above about 1, the velocity profile
  changes with frequency, so the effective `b` and `c` depend on frequency.
- **Entry and exit losses** at the piston chamber and channel junctions.
- **Cavitation.** Large inertial pressures can push the chamber pressure below the oil's vapour pressure.

**Research question:** *How far does a real fluid inerter depart from the ideal model, and how much
of the theoretical grip benefit to a race car survives once those effects are included?*

**How to run everything:** see [HOW_TO_RUN.md](HOW_TO_RUN.md). In short, `powershell -ExecutionPolicy Bypass -File run_all.ps1`.

## 2. Key results

Baseline inerter: 40 mm piston, 6 mm × 1.89 m helical channel (R = 30 mm), ISO VG 32 oil, so the ideal inertance is b = 91.7 kg.

1. **Validation (steady, full helix, 0.38M-cell structured mesh).** The CFD friction factor is within **0.3–3.6 %** of the
   Ito (1959) correlation for Re = 100–4000 (De = 32–1265). A 3-mesh GCI study (0.16M / 0.38M / 0.90M cells,
   `cfd/results/gci_s01.*`) gives a discretisation uncertainty of **0.1–0.3 % up to De ≈ 300**. At De ≈ 1265 only the
   fine mesh reaches a steady solution (within 0.8 % of Ito); the coarser meshes keep oscillating, so high Dean numbers
   need more resolution near the wall.
2. **Helix pitch is negligible.** A periodic torus sector with no pitch reproduces the full-helix friction to within **0.1 %**
   (De = 77–622). This justifies modelling the oscillating flow on a 2,560-cell periodic sector.
3. **CFD inertance and damping (oscillatory flow, 1–20 Hz, 2 and 5 mm stroke).**
   - Effective inertance is **1.02–1.26 × the ideal formula** ρlA_p²/A_c. It falls with Dean number, because the Dean vortices
     flatten the velocity profile. A straight laminar pipe (Womersley's exact solution) would be 1.22–1.33 ×.
   - Parasitic damping is **1.1–3.2 × the straight-pipe value**, rising with frequency and stroke. A quasi-steady
     curved-pipe correlation predicts it to within about 4 %, but the frequency-dependent inertance is only captured by the CFD.
4. **Race-car grip (quarter car, J-damper layout, ISO 8608 class A road, 180 km/h):**

   | Inerter model | Reduction in dynamic tyre load |
   |---|---|
   | Ideal inerter | 8.7 % |
   | Quasi-steady correlation model | 4.4 % |
   | Womersley (straight pipe) | 5.4 % |
   | **CFD curved channel, 2 mm stroke** | **5.0 %** |
   | CFD curved channel, 5 mm stroke | 4.5 % |

   **Real fluid behaviour removes about 40–50 % of the ideal inerter's grip benefit.**
5. **Full-car track simulation** (`sim/track_simulator.html`: Toyota GR Supra road and GT4, Ford F-150 on Monza, Spa,
   Daytona and a straight test road). On the straight rough test road the full car reproduces the tuned gains
   (Supra, J-damper replacing the main damper: about 6–7 % steadier tyre load). On a real circuit most of that gain
   disappears. Braking and cornering transients excite body pitch and roll, which the J-damper controls worse than
   the normal damper, and kerb strikes push the suspension onto its bump stops. **The J-damper's benefit is a
   trade-off between bump grip and body control.** The best compromise keeps part of the main damper. A parallel inerter gives no benefit at all.
   Because `c_par/b = 32ν/d²·(f_c/f_s)` depends only on the channel diameter, **packaging vs fluid losses** is the
   core design trade-off (`python/results/diameter_design_chart.png`).
6. **Piston chamber, ports and cavitation (axisymmetric CFD, `cfd/openfoam/chamber*`).** The helix CFD drives the oil
   in the channel only, so the piston, its chambers and the sharp-edged ports were simulated separately.
   - **Port losses (steady, Re 100–2000):** entry K_in = 0.32–0.54 and exit **K_out = 1.89–1.95**, not the textbook
     0.5 and 1.0. Laminar oil leaves the channel with a peaked profile carrying twice the kinetic energy (α ≈ 2), and all of it is
     lost in the chamber. Total port loss ≈ 2.3 velocity heads vs 1.5 assumed. Two meshes agree within 0–6 %.
   - **Oscillating piston (10 Hz, ±5.6 mm),** with the tube end coupled to the rest of the coil through the torus-CFD
     inertance and damping: the chambers and ports add **+7.4 % damping** to the channel's damping, with negligible effect on
     inertance (−2.7 %). That is 84 % of the quasi-steady estimate from the steady K values. The port jet forms a ring vortex in the chamber.
   - **3D drilled port (`cfd/openfoam/port3d*`, `make_port3d_openfoam.py`, `post_port3d.py`).** In the device the port is a
     radial hole in the bore wall. It meets an axial drilling at a sharp 90° corner and turns sharply again into the helix.
     A 3D snappyHexMesh model of that path (0.6–1.6M cells, 2 wall layers) uses a recycled inlet, so the oil leaving the
     coil arrives with its developed Dean-flow profile. Result at Re 250–500: **K_in ≈ 2.6, K_out ≈ 3.8**, so the total is
     ≈ 6.4 velocity heads against 2.3 for the axisymmetric port alone. The two sharp elbows add about one velocity head
     each. Two meshes agree within 1–4 %, and the developed helix friction matches Ito within 4–5 %.
     **Design lesson: radius the drilled passages.**
   - **Effect on the vehicle results: small.** The python model now uses K_in = 2.6 and K_out = 3.8. At a 2 mm stroke
     the port damping is ≈ 630 N s/m at 10 Hz, rising in proportion to frequency. In the quarter car the CFD grip benefit
     stays at **5.0 %** (`run_cfd_vehicle_study.py`, "CFD channel + piston chambers"), because the optimiser takes a
     slightly smaller inertance. With the J-dampers retuned, the track results move by up to ±1 percentage point
     (table in `PRESENTATION_GUIDE.md`).
   - **Cavitation (interPhaseChangeFoam, Schnerr–Sauer, 20 Hz, ±2.4 mm):** vapour forms at 0.5, 1.0 and 1.5 MPa
     pre-charge (up to 28 % of the chamber volume), in the ring-vortex core next to the port and at the piston corner. None forms at
     2.0 or 3.0 MPa. The CFD onset (≈ 1.75 MPa) matches the hand calculation p_charge = Δp/2 = **1.73 MPa**.

## 3. Workflow

```
 make_helix_mesh.py (structured O-grid hex, OpenFOAM polyMesh)
   ├─ full helix, steady (simpleFoam)        -> friction validation vs Ito/White + GCI mesh study
   └─ periodic torus sector
        ├─ steady                            -> pitch (torsion) effect: torus vs helix
        └─ oscillatory (pimpleFoam, 1-20 Hz) -> b_eq(w), c_eq(w), nonlinear ROM F = b ẍ + c1 ẋ + c2 ẋ|ẋ|
                                                   |
 python/: quarter car, layouts L1-L4, ideal vs correlation vs Womersley vs CFD inerter -> grip benefit
```

## 4. Folder structure

| Path | Contents |
|---|---|
| `HOW_TO_RUN.md`, `run_all.ps1` | How to run, and the one-command pipeline |
| `docs/theory.md` | Governing equations, dimensionless groups, correlations |
| `docs/cfd_setup_openfoam.md` | OpenFOAM install and case details |
| `docs/cfd_setup_ansys.md` | Physics choices, case matrix, and an optional Ansys Student cross-check |
| `cfd/scripts/` | Mesh generator, case generators (`make_s01_openfoam.py`, `make_torus_openfoam.py`), post-processing |
| `cfd/openfoam/` | Generated case sets + `run_in_wsl.sh` |
| `cfd/results/` | CFD plots and CSVs (`v1_inverted_grading/` = archived first run, kept for the report) |
| `python/` | Inerter and vehicle models (primary). Results in `python/results/` |
| `matlab/` | Equivalent MATLAB versions of the vehicle scripts |
| `sim/` | Full-car track simulator (`track_simulator.html`), its data builder, tools and results (`sim/results/`: charts, GIFs, CSV) |
| `PRESENTATION_GUIDE.md` | Slide plan, numbers, demo script and Q&A for the faculty presentation |
| `project_page.html` | Interactive project page with all results (also published online) |

### Python vehicle and inerter models (`python/`, primary)

| File | Purpose |
|---|---|
| `inerter_model.py` | Core models: parameters, curved-pipe friction, inerter force, c_par/b, ISO 8608 road, quarter-car FRF, layouts L1-L4, ROM fit |
| `analyse_inerter.py` | Design numbers, flow regime and cavitation table, friction/loss/force-loop plots |
| `test_fit_rom.py` | Self-test of the ROM fitting routine |
| `run_quarter_car_study.py` | Optimises layouts L1-L4 (ideal vs fluid), diameter design chart, writes `results/layout_opt.json` |
| `run_time_domain.py` | Nonlinear time-domain quarter car (L1 vs L4 ideal vs L4 fluid) |

Run them from inside `python/` in the order above. Plots go to `python/results/`. Requirements: numpy, scipy, matplotlib.

### MATLAB files (equivalent versions; base MATLAB only, no toolboxes needed)

| File | Purpose |
|---|---|
| `inerter_params.m` | Baseline geometry, fluid and vehicle parameters (single source of truth) |
| `friction_factor_helical.m` | Curved-pipe friction factor (Ito laminar and turbulent, transition criterion) |
| `inerter_force.m` | Nonlinear lumped inerter force model |
| `analyse_inerter.m` | **Run first.** Prints b, c, Re, Dean, Womersley numbers and cavitation risk; plots force maps |
| `export_helix_curve.m` | Writes the helix centreline as a coordinate file for DesignModeler (3D Curve) |
| `quarter_car_freq.m` | Linear quarter-car frequency response for any suspension admittance Q(s) |
| `parasitic_ratio.m` | Parasitic damping per kg of inertance, c_par/b, for a channel diameter |
| `iso8608_road.m` | ISO 8608 road profile PSD and time-domain realisation |
| `run_quarter_car_study.m` | Optimises layouts L1-L4 (ideal vs fluid inerter), produces the diameter design chart, saves `layout_opt.mat` |
| `run_time_domain.m` | Nonlinear time-domain quarter-car: L1 vs L4 ideal vs L4 fluid inerter (run after the study) |

**Run order:** `analyse_inerter` → `test_fit_rom` → `run_quarter_car_study` → `run_time_domain` →
`export_helix_curve` (for the CFD geometry). Run them from inside the `matlab/` folder.
| `fit_rom_from_cfd.m` | Fits the reduced-order model to Fluent force/pressure exports |
| `test_fit_rom.m` | Self-test of the fitting routine on synthetic data |

## 5. Status

| Item | Status |
|---|---|
| Theory, correlations, design analysis | Done |
| Structured helix mesh generator (verified with `checkMesh`) | Done |
| Steady validation vs Ito/White (S01) | Done (0.3-3.6 % agreement) |
| Mesh independence (GCI, 3 meshes) | Done |
| Pitch (torsion) check: torus sector vs helix | Done (< 0.1 %) |
| Oscillatory CFD T01-T10 + Womersley comparison + ROM fits | Done |
| Vehicle studies with the CFD-based inerter | Done |
| Piston chamber + port losses (S2), oscillating piston, cavitation (S3) | Done (`cfd/openfoam/chamber*`, `post_chamber.py`) |
| 3D drilled port + elbows (radial port, 2 sharp elbows, helix inlet) | Done (`cfd/openfoam/port3d*`, `post_port3d.py`) |
| Full-car track simulator (3 cars, 4 tracks, 36-run comparison, GIFs, charts) | Done |
| Presentation package (`PRESENTATION_GUIDE.md`, project page) | Done |
| Still open (optional) | Finer study of the high-Dean regime (De > 1000); comparison with the published fluid-inerter experiments (Swift et al. 2013; Liu et al. 2018); write-up |

## 6. Validation strategy (no hardware)

1. **Code verification:** mesh independence (GCI, Celik et al. 2008), time-step control (Courant ≤ 0.8,
   ≥ 400 steps per cycle) and cycle-to-cycle periodicity (< 0.02 %).
2. **Steady validation:** CFD pressure drop vs the Ito (1959) and White (1929) curved-pipe correlations.
3. **Unsteady validation:** the oscillatory results tend to Womersley's exact straight-pipe solution
   as the Dean number goes to 0 (inertance → 4/3 × ideal at low frequency).
4. **Device-level comparison (to do):** trends of the fitted inertance and damping vs published fluid-inerter
   experiments (Swift et al. 2013; Liu et al. 2018).

## 7. Key references

- Smith, M.C. (2002). Synthesis of mechanical networks: the inerter. *IEEE Trans. Automatic Control*, 47(10), 1648-1662.
- Smith, M.C. & Wang, F.-C. (2004). Performance benefits in passive vehicle suspensions employing inerters. *Vehicle System Dynamics*, 42(4), 235-257.
- Swift, S.J., Smith, M.C., Glover, A.R., Papageorgiou, C., Gartner, B. & Houghton, N.E. (2013). Design and modelling of a fluid inerter. *Int. J. Control*, 86(11), 2035-2051.
- Liu, X., Jiang, J.Z., Titurus, B. & Harrison, A. (2018). Model identification methodology for fluid-based inerters. *Mech. Systems and Signal Processing*, 106, 479-494.
- Dean, W.R. (1927/1928). Note on the motion of fluid in a curved pipe / The stream-line motion of fluid in a curved pipe. *Phil. Mag.*
- White, C.M. (1929). Streamline flow through curved pipes. *Proc. R. Soc. Lond. A*, 123, 645-663.
- Ito, H. (1959). Friction factors for turbulent flow in curved pipes. *J. Basic Engineering*, 81, 123-134.
- Womersley, J.R. (1955). Method for the calculation of velocity, rate of flow and viscous drag in arteries when the pressure gradient is known. *J. Physiology*, 127, 553-563.
- Celik, I.B. et al. (2008). Procedure for estimation and reporting of uncertainty due to discretization in CFD applications. *J. Fluids Eng.*, 130(7), 078001.
- Schnerr, G.H. & Sauer, J. (2001). Physical and numerical modeling of unsteady cavitation dynamics. *ICMF 2001*.
- ISO 8608:2016. Mechanical vibration - Road surface profiles - Reporting of measured data.

> Check every citation and correlation constant against the original source before you put it in the report.
