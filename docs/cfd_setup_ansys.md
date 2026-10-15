# ANSYS CFD Setup Guide

> **The project now runs on OpenFOAM. See `cfd_setup_openfoam.md`.** This guide is kept as the
> reference for the physics choices and for an optional cross-check with *Ansys Student* (free).
> `make_helix_mesh.py --format fluent --out FILE.msh` writes the same mesh for Fluent.

Assumes **Ansys Student**, which limits fluids models to roughly 1M cells/nodes (check the exact limit
for your version). With a university licence you can model more turns and refine the mesh further.

## 0. Modelling strategy (staying within the cell limit)

You do **not** need to model all 10 turns. The flow becomes *fully developed* after about 1 turn, so:

- **Domain:** a 3-turn helix with short straight legs at each end (about 5d long). Take the pressure
  gradient `dp/ds` from the **middle turn** and scale it up to the full channel length `l` in MATLAB.
- **Piston chambers** are *not* meshed in the baseline cases. Incompressible continuity fixes
  `Q = A_p·ẋ`, so you impose the channel velocity directly. The entry and exit losses (K_in, K_out) come
  from a separate small case: a chamber attached to a short straight tube (Stretch Case S2).
- **Periodic boundaries:** Fluent supports translational or rotational periodicity, but not the screw
  symmetry of a helix. To get a cheap steady check, you can use a **zero-pitch torus sector**
  with rotational periodicity (Case S1). This is valid because torsion is small (τ ≈ 0.05).

## 0b. Scripted route (used in this project)

Sections 1-2 describe the manual GUI route. The project instead uses a scripted, fully reproducible route:

| Step | Command | Output |
|---|---|---|
| Mesh | `python cfd/scripts/make_helix_mesh.py --out cfd/mesh/helix_medium.msh` | 381,600-cell structured O-grid hex mesh (5 turns + legs). Internal planes `turn0`-`turn5` sit at each turn |
| GCI meshes | Same command with `--n 9 --m 9 --per-turn 75` (coarse) and `--n 16 --m 16 --per-turn 133` (fine) | Refinement ratio about 1.33 (check the fine mesh against your cell limit) |
| S01 journals | `python cfd/scripts/make_s01_journals.py` | `cfd/runs/s01/re*.jou` + `run_s01.ps1` |
| Run | `powershell -File cfd/runs/s01/run_s01.ps1 -Cores 4` | `.srp` pressure reports and `.cas.h5` files |
| Post | `python cfd/scripts/post_s01.py` | `cfd/results/s01_friction_ratio.png`, `s01_development.png`, `s01_friction.csv` |

The mesh was checked independently: every cell is closed, all cell volumes are positive, and the volume
error from the polygonal cross-section is under 0.5 %. S01 uses Fluent's default air with Re-matched velocities.
For steady, laminar, constant-property flow, f_D depends only on Re and the geometry, so the results apply directly to the oil.

## 1. Geometry (DesignModeler or SpaceClaim)

1. Run `matlab/export_helix_curve.m`. It writes `cfd/helix_centerline.txt`, a 3-turn helix plus legs,
   in the DesignModeler *3D Curve* format.
2. In DesignModeler: **Concept → 3D Curve →** choose the file, then **Generate**.
3. Sketch a circle of diameter `d = 6 mm` on a plane normal to the curve at its start.
4. **Sweep** the circle along the 3D curve to create a solid body. This is the *fluid* domain.
5. **Named Selections:** `inlet`, `outlet`, `wall`. In the Fluent post-processing step, also create
   **planes** at the start and end of the middle turn.

SpaceClaim alternative: insert the curve from the same file, then use **Pull → Sweep**.

## 2. Mesh

| Setting | Value | Reason |
|---|---|---|
| Method | **Sweep** (body is sweepable), with a structured O-grid cross-section via *Multizone* if possible | Gives a hex mesh, which keeps the cell count low |
| Inflation | 12-15 layers, first layer about 0.02 mm, growth 1.15 | Resolves the Stokes layer: `δ_s = sqrt(2ν/ω)` ≈ 1 mm at 10 Hz, so put ≥ 8 cells inside it at the highest frequency |
| Cross-section | About 600-1000 cells | |
| Axial | About 200-300 divisions per turn | |
| Target total | About 0.6-0.8M cells for 3 turns | Stays under the Student limit |

**Mesh independence (GCI):** build 3 meshes with refinement ratio r ≥ 1.3 (coarse, medium, fine). Monitor
`dp/ds` in the middle turn and the maximum secondary velocity. Report the GCI following Celik et al. (2008).

## 3. Fluent: common setup

- Solver: **Pressure-based**, double precision (3ddp).
- Material: hydraulic oil, ρ = 870 kg/m³ and μ = 0.028 Pa·s (constant; isothermal).
- Viscous model: **Laminar.** `analyse_inerter.m` checks that Re < Re_crit (curved pipe). For any case
  above Re_crit, switch to **k-ω SST** with *curvature correction* enabled.
- Pressure-velocity coupling: **Coupled** (steady) or **PISO/Coupled** (transient). Discretisation: second-order
  pressure and second-order upwind momentum. Use **bounded second-order implicit** time stepping for transient runs.
- Report definitions: area-weighted average static pressure on the two middle-turn planes. Also record the mass
  flow rate at the inlet. **Write them to file every time step.**

## 4. Steady cases (validation)

- Inlet: velocity inlet with `v` swept so that Re covers 100 to 8000 (8-10 points).
- Outlet: pressure outlet at 0 Pa gauge.
- Converge each case to residuals below 1e-5 *and* a flat Δp monitor.
- Output: `f_D = (dp/ds)·d / (½ρv²)` vs Re. Overlay the Ito (1959) and White (1929) curves using
  `friction_factor_helical.m`. Expect agreement within about 5-10% in the laminar range.
- Post-processing: plot velocity-magnitude contours and in-plane vectors on a cross-section
  plane to show the **Dean vortices**. This makes a good figure for the report.

## 5. Transient (oscillatory) cases

Inlet velocity as a Fluent **named expression**:

    vamp  = 1.0 [m/s]                       (= (A_p/A_c)·X·ω)
    freq  = 10 [Hz]
    vin   = vamp * sin(2*PI*freq*t)

Apply `vin` to the velocity inlet. When it goes negative the inlet becomes an outlet. Also set the
outlet's **backflow** direction to normal-to-boundary. (Check the units in the expression editor. Fluent
may need the sine argument to be dimensionless, which `freq*t` already is.)

- Time step: ≥ **200 steps per cycle** (Δt = 1/(200·f)), max 20-30 iterations per step.
- Run **4-5 cycles**. Discard the first 2-3, which are the start-up transient, and analyse the last cycle.
- Export each run as a CSV with columns `t, p_up, p_down, mdot`. Name the files `cfd/results/case_<id>.csv`.

### Case matrix (piston amplitude X, frequency f)

See `cfd/case_matrix.csv`. The design covers 1-20 Hz, which spans body and wheel-hop modes, at 2 amplitudes.
This gives 10 transient runs. Each run takes several hours on a laptop, so prioritise the IDs marked
`priority = 1`.

## 6. Stretch cases

| Case | Purpose |
|---|---|
| S1: torus sector, rotational periodic, steady | Cheap, fully developed `f_c` to cross-check the 3-turn model |
| S2: chamber + short tube, axisymmetric 2D | Find the entry/exit coefficients K_in and K_out (this case is cheap in 2D) |
| S3: cavitation | Multiphase **Mixture** model with **Schnerr-Sauer** cavitation and p_vap ≈ 2 kPa. Use a 2D-axisymmetric chamber + tube and vary the charge pressure to map cavitation onset |

## 7. From CFD to MATLAB

1. The force is `F = A_p·Δp_channel_total`. Here `Δp_channel_total = (dp/ds)_middle·l + Δp_minor`.
2. Run `fit_rom_from_cfd('cfd/results/case_T03.csv', X, f)`. It returns `b_eq`, `c_eq`, and the
   time-domain ROM coefficients for that case.
3. Collect `b_eq(ω)` and `c_eq(ω)` across the cases. Use them (or the ROM) in
   `run_quarter_car_study.m` and `run_time_domain.m`.
