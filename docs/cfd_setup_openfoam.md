# CFD Setup Guide: OpenFOAM

The project's CFD runs on **OpenFOAM v2406** (openfoam.com, free and open source, no cell limit) under
WSL on Windows. The physics, case matrix and validation plan are the same as in
`cfd_setup_ansys.md`. Only the tooling differs.

## 1. One-time install (you do this; it needs admin rights and a restart)

1. In an **admin** PowerShell, run `wsl --install -d Ubuntu-22.04`. Restart when asked, then create your Linux username.
2. In the Ubuntu terminal:
   ```bash
   curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
   sudo apt-get install -y openfoam2406-default python3-numpy python3-matplotlib
   echo 'source /usr/lib/openfoam/openfoam2406/etc/bashrc' >> ~/.bashrc && source ~/.bashrc
   simpleFoam -help | head -3        # check the install
   ```
3. (Optional) Install ParaView on Windows from paraview.org to view the results (Dean vortices, velocity contours).

## 2. Pipeline

| Step | Command | Output |
|---|---|---|
| Mesh + cases | `python cfd/scripts/make_s01_openfoam.py` | `cfd/openfoam/s01/mesh` (381,600 hex cells), 6 cases `re00100`-`re04000`, `Allrun` |
| Run | In WSL: `cd .../cfd/openfoam/s01 && ./Allrun 4` | Logs, `postProcessing/pTurn*/` pressure histories |
| Post | `python cfd/scripts/post_s01.py` | `cfd/results/s01_friction_ratio.png`, `s01_development.png`, `s01_friction.csv` |

**Speed tip:** WSL is slow when it reads and writes files on `C:` (`/mnt/c/...`). Copy the case folder to your Linux home first,
e.g. `cp -r "/mnt/c/Users/<you>/Downloads/Pneumatics and Hydraulics/cfd/openfoam/s01" ~/`, run it there,
and copy `postProcessing/` back afterwards.

## 3. Case S01 details

| Item | Setting |
|---|---|
| Solver | `simpleFoam` (steady, incompressible, SIMPLEC), laminar |
| Fluid | ISO VG 32 oil, ν = 0.028/870 = 3.22e-5 m²/s |
| Inlet | `flowRateInletVelocity` with Q = v_bulk × discrete inlet area, so Re is exact |
| Outlet | p = 0, `inletOutlet` velocity |
| Wall | `noSlip` |
| Schemes | `bounded Gauss linearUpwind` (2nd order) for convection, linear gradients |
| Convergence | residualControl p 1e-7, U 1e-9, or 4000 iterations |
| Monitors | area-averaged p on faceZones `turn0`-`turn5`, and outlet flux (a mass-conservation check) |

## 4. Mesh

`cfd/scripts/make_helix_mesh.py` writes the OpenFOAM `polyMesh` directly. It's a structured O-grid swept along
the helix with Frenet frames, with 5 turns plus 5d straight legs, and the turn planes are stored as `faceZones`.
An independent Python check confirmed closed cells, positive volumes, owner < neighbour,
upper-triangular face order and outward boundary normals. `checkMesh` runs automatically in `Allrun`.

**GCI study:** generate coarse and fine versions with
`--n 9 --m 9 --per-turn 75` and `--n 16 --m 16 --per-turn 133` (refinement ratio about 1.33).

## 5. Oscillatory cases: periodic torus sector (`make_torus_openfoam.py`)

**Why not the full helix?** A transient full-helix run (3 turns, 0.24M cells) took about 55 s per time step, because
the pressure equation is hard to solve on a long, thin domain. 10 cases × ~800 steps would have taken days.
Fully developed flow repeats every turn, so a **10° torus sector with rotationally periodic ends**
(2 cells along the axis × 1,280-cell fine cross-section = 2,560 cells) gives the same physics at about 1/100 of the cost.

| Item | Setting |
|---|---|
| Mesh | `make_helix_mesh.py --torus 10 --torus-cells 2 --n 16 --m 16`. Cyclic patches `cyc0`/`cyc1`, rotational about z |
| Driving | Kinematic pressure jump across the cyclic pair (`uniformJump`): constant (steady) or `sine` (oscillatory) |
| Steady | `simpleFoam`, plain SIMPLE with under-relaxation (p 0.3, U 0.7). SIMPLEC drifted on this mesh |
| Oscillatory | `pimpleFoam`, 2 outer and 2 pressure correctors, adaptive Δt with **Co ≤ 0.8** and ≥ 400 steps per cycle, max(4 cycles, 0.4 s) |
| Output | Flow rate on `cyc1` every step. `post_transient.py` takes first-harmonic Fourier coefficients of force and piston velocity over the last cycle, giving Z = c_eq + iω·b_eq |

**Checks:**
- Torus vs full helix, steady, same mesh: < 0.1 % difference for De = 77–622, so the helix pitch (torsion ≈ 0.05) is negligible.
- Medium vs fine torus cross-section: about 0.1 % difference.
- Cycle-to-cycle change of b_eq and c_eq: ≤ 0.02 %.
- A fixed time step with Co ≈ 4.5 diverged in the low-frequency cases. That is why the time step is now adaptive.

## 6. Still open (optional)

- **High-Dean regime (De > 1000):** at De ≈ 1265 only the fine helix mesh (0.9M cells) converged to a steady solution;
  the coarse and medium meshes, and the torus sector, keep oscillating. Use wall-refined meshes for De > 1000.
- Entry/exit losses and cavitation: **done**, see section 7.

## 7. Piston chamber, ports and cavitation (`make_chamber_openfoam.py`, `post_chamber.py`)

| Item | Setting |
|---|---|
| Geometry | 2D axisymmetric 5° wedge: piston face (Ø40 mm), 20 mm chamber, sharp-edged Ø6 mm port, 0.6 m straight tube |
| Meshes | `chamber`: 19,644 cells, 0.06–0.08 mm at the port edge (steady). `chamber_transient`: 7,667 cells, 0.15–0.2 mm (time-dependent) |
| Steady (simpleFoam) | Piston face = uniform velocity (in) or suction (out); tube end p = 0. Re = 100–2000 |
| Loss coefficient | Mechanical-energy balance, piston face to developed flow at x = 0.30 m, minus Poiseuille friction over 0.30 m |
| Oscillating (pimpleFoam) | Piston velocity X ω sin ωt (T04: 10 Hz, 5.6 mm). Tube end = rest of the half-coil: p = φ (b_eq ẍ + c_eq ẋ)/A_p, φ = (l/2 − L_t)/l, b_eq and c_eq from the torus CFD. The device is antisymmetric, so mid-coil stays at the charge pressure |
| Cavitation (interPhaseChangeFoam) | Schnerr–Sauer, p_sat = 2 kPa, absolute pressure; T05 (20 Hz, 2.43 mm); charge pressure 0.5–3 MPa |

Results: `cfd/results/chamber_losses.png`, `chamber_oscillation.png`, `cavitation.png`, `chamber_summary.json`.

