# How to run the project

Everything uses free, open-source tools: **OpenFOAM v2406** (CFD, inside WSL Ubuntu) and
**Python 3** (meshing, post-processing, suspension models).

## 1. One-time setup

**Windows (PowerShell):** install Python 3, then
```powershell
pip install numpy scipy matplotlib
```

**WSL + OpenFOAM** (already done on this laptop). In an *admin* PowerShell run `wsl --install -d Ubuntu-22.04`,
restart, then in the Ubuntu terminal:
```bash
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
sudo apt-get install -y openfoam2406-default
echo 'source /usr/lib/openfoam/openfoam2406/etc/bashrc' >> ~/.bashrc
```

## 2. Run everything with one command

Open PowerShell **in the project folder** and run:

```powershell
powershell -ExecutionPolicy Bypass -File run_all.ps1
```

This takes about **1.5–2 hours** on 8 cores. Keep the laptop plugged in and awake, because WSL stops when Windows sleeps.
It runs four stages:

| Stage | What happens | Time |
|---|---|---|
| 1. Generate | Meshes and OpenFOAM cases (Python) | ~3 min |
| 2. CFD | All OpenFOAM runs inside WSL (see table below) | ~1.5 h |
| 3. Post-process | Friction validation, mesh independence (GCI), CFD inertance/damping | ~1 min |
| 4. Vehicle | Suspension (quarter-car) studies, including the CFD-based inerter | ~1 min |

Useful options:
```powershell
powershell -ExecutionPolicy Bypass -File run_all.ps1 -SkipCFD      # re-do only stages 3-4 (~5 min)
powershell -ExecutionPolicy Bypass -File run_all.ps1 -Cores 4      # use fewer CPU cores
```

## 3. Where the results are

| Folder / file | Contents |
|---|---|
| `cfd/results/s01_friction_ratio.png` | Steady validation: CFD friction vs Ito/White correlations (full helix) |
| `cfd/results/gci_s01.png`, `.csv` | Mesh-independence study (3 meshes, GCI uncertainty) |
| `cfd/results/torus_steady_medium.png` | Periodic torus sector vs full helix (effect of the helix pitch) |
| `cfd/results/transient_coefficients.png` | **Main CFD result:** effective inertance and damping vs frequency |
| `cfd/results/transient_force_loops.png` | Force-displacement loops, CFD vs ideal inerter |
| `cfd/results/transient_summary.csv`, `transient_rom.csv` | All oscillatory-case numbers and fitted inerter models |
| `python/results/cfd_vehicle_study.png` | **Headline result:** grip benefit with ideal / correlation / Womersley / CFD inerter |
| `python/results/layout_comparison.png`, `diameter_design_chart.png` | Suspension layouts and channel-diameter design chart |
| `cfd/results/models/` | **Pictures of every model**: helix geometry, O-grid meshes, mesh close-up, torus sector, quarter-car layouts |
| `cfd/results/demo/*.gif`, `dean_vortices.png` | **Flow animation** (piston, Dean vortices, force loop) and steady vortex figure |
| `cfd/results/v1_inverted_grading/` | Archived first run (mesh grading bug), kept for the report |
| `sim/results/track_comparison.csv` | **Track study:** all 36 runs (3 cars x 4 tracks x 3 damper settings): grip change, bump/body split, wheel lifts, pitch, roll, heave |
| `sim/results/chart_*.png` | Track-study charts: grip by track, bumps vs body, damper trade-off, vehicle dynamics |
| `sim/results/*.gif` | Simulator clips for slides (Eau Rouge, F-150 braking, kerb strike, Daytona banking, test road); `web/` = smaller copies |
| `PRESENTATION_GUIDE.md` | **Faculty presentation:** slide plan, all numbers, demo script, likely questions |
| `cfd/results/chamber_losses.png`, `chamber_oscillation.png`, `cavitation.png` | **Piston chamber CFD:** port loss coefficients, force loop with the piston chambers, cavitation vs charge pressure |
| `cfd/results/port3d_losses.png`, `port3d_flow.png` | **3D drilled port CFD:** K_in / K_out vs the 2D port, velocity on the mid-plane |
| `cfd/results/piston_chamber_flow.gif`, `device_cutaway.gif` | Animations: port jet / ring vortex and vapour; the whole device with the piston moving |

## 4. Running pieces by hand

**Generate cases (PowerShell, project folder):**
```powershell
python cfd\scripts\make_s01_openfoam.py                                   # full helix, Re 100-4000
python cfd\scripts\make_s01_openfoam.py --mesh coarse --re 100 1000 4000  # GCI coarse
python cfd\scripts\make_s01_openfoam.py --mesh fine --re 100 1000 4000    # GCI fine
python cfd\scripts\make_torus_openfoam.py                                 # torus: steady + oscillatory
python cfd\scripts\make_torus_openfoam.py --mesh medium --sets steady
python cfd\scripts\make_chamber_openfoam.py                              # piston chamber + port, cavitation
python cfd\scripts\make_port3d_openfoam.py                               # 3D drilled port + elbows (snappyHexMesh)
```

**Run CFD (Ubuntu terminal).** Pick any of the case sets; results are copied back automatically:
```bash
bash "/mnt/c/Users/Rishi Kumar/Downloads/Pneumatics and Hydraulics/cfd/openfoam/run_in_wsl.sh" torus_oscillatory
```

| Case set | What it is | Approx. time (8 cores) |
|---|---|---|
| `s01` | Full helix, steady, Re = 100-4000 (medium mesh, 0.38M cells) | 45 min |
| `gci_coarse`, `gci_fine` | Same at Re = 100, 1000, 4000 on 0.16M and 0.90M cells | 15 min + 60 min |
| `torus_steady`, `torus_steady_medium` | Periodic 10 degree sector, steady | 2 min each |
| `torus_oscillatory` | Periodic sector, oscillatory flow T01-T10 (1-20 Hz, 2 and 5 mm) | 20 min |
| `chamber` | Piston chamber + port, steady, Re = 100-2000 in and out (fine mesh) | 17 min |
| `chamber_transient` | Oscillating piston (T04) and cavitation at 5 charge pressures (T05) | 45 min |
| `port3d_coarse` | 3D drilled port, 0.6M cells, Re 250 / 1000 / 2000 in and out | 2.2 h |
| `port3d` | 3D drilled port, 1.6M cells, Re 250 / 500 / 1000 in and out | 5 h |

**Post-process and vehicle studies (PowerShell):**
```powershell
python cfd\scripts\post_s01.py
python cfd\scripts\post_gci.py
python cfd\scripts\post_torus_steady.py torus_steady_medium
python cfd\scripts\post_transient.py
python cfd\scripts\post_chamber.py
python cfd\scripts\post_port3d.py
cd python
python run_quarter_car_study.py
python run_time_domain.py
python run_cfd_vehicle_study.py
```

## 5. Live flow demo (animation)

The project page (`project_page.html`, also published online) has a **"Watch the inerter work"** player. It shows the piston,
the oil in the channel cross-section with the Dean vortices, and the force loop, over one 10 Hz cycle from the CFD.
To regenerate it live (about 6 minutes):
```bash
bash "/mnt/c/Users/Rishi Kumar/Downloads/Pneumatics and Hydraulics/cfd/openfoam/run_in_wsl.sh" torus_demo
```
```powershell
python cfd\scripts\render_demo.py
```
Outputs: `cfd/results/demo/osc_X2.gif` and `osc_X5.gif` (good for slides), the frames in `cfd/results/demo/<case>/`,
and `cfd/results/dean_vortices.png`. If you change the cases, regenerate them first with
`python cfd\scripts\make_demo_openfoam.py`.

## 5b. Viewing the flow in 3D (optional)

The full flow fields (for example the Dean vortices) stay in WSL under `~/inerter/<set>/<case>/`. Open them in
**ParaView** (free, paraview.org). In the Ubuntu terminal, run `touch case.foam` inside a case folder, then open
`\\wsl$\Ubuntu-22.04\home\<your-linux-user>\inerter\<set>\<case>\case.foam` from ParaView on Windows.

## 6. Changing the design

The inerter geometry and the car parameters live in `python/inerter_model.py` (`Params`). The channel
geometry for CFD is set by the options of `cfd/scripts/make_helix_mesh.py` (`--d`, `--R`, `--pitch`).
After a change, rerun the relevant stages (`run_all.ps1` for everything).

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `OpenFOAM v2406 not found` | Install OpenFOAM in WSL (section 1) |
| A case says `FAILED` | Read `log.pimpleFoam` / `log.simpleFoam` in that case folder |
| Path errors in OpenFOAM | OpenFOAM can't handle spaces in paths, so `run_in_wsl.sh` copies cases to `~/inerter` |
| Runs stop overnight | Windows went to sleep. Set "Sleep: Never" while plugged in |

## 8. Track simulator (whole car on Monza, Spa, Daytona)

Open `sim/track_simulator.html` in a browser (double-click). It's also published online. A GT coupe or a pickup laps
Monza, Spa-Francorchamps or the Daytona oval with three suspensions at once (conventional, ideal J-damper, CFD
J-damper). It shows body pitch and roll, weight transfer from the centre of gravity, the four wheel loads, kerb strikes
and a live grip comparison. Click the track map to jump to a corner.

Rebuild its data (track geometry, lap simulation, suspension tuning) after changing a car or track:
```powershell
python sim\build_sim_data.py
```
This rewrites `sim/track_simulator.html` with the new data. Track centrelines: TUM FTM racetrack-database (LGPL-3.0), in `sim/track_data_raw/`.

Presentation charts and GIFs (`sim/results/`): `python sim\make_presentation_assets.py` rebuilds them from the recorded
runs in `sim/results/capture/`. Recording new clips is described in `PRESENTATION_GUIDE.md` (section 8).
`python sim\insert_track_section.py <pagedata.json>` refreshes the track section of the project page.

## 9. ParaView (3D CFD views like a commercial CFD package)

Install ParaView for Windows (free, paraview.org), then:
```powershell
powershell -ExecutionPolicy Bypass -File open_paraview.ps1
```
