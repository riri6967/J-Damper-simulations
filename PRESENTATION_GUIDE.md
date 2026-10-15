# Presentation guide: CFD of a helical fluid inerter (J-damper) for race-car suspension

Everything you need for the faculty review: the story, slide-by-slide content with the exact numbers and figures, a
live-demo script, and likely questions. All numbers come from the project's result files (paths given).

---

## 1. The story in one minute

An **inerter** is a suspension element whose force is proportional to *acceleration* (F = b·ẍ). McLaren raced one in
F1 as the "J-damper". A **fluid inerter** makes this by pumping oil through a long helical channel. Theory treats it as
ideal, but real oil has friction, swirling Dean vortices and frequency-dependent behaviour.

**Question:** how far does a real fluid inerter depart from the ideal, and what does that mean for a car's grip?

**Answer, at three levels:**
1. **CFD:** the real inertance is 1.02–1.26 × the ideal formula, and it adds 1.1–3.2 × the parasitic damping of a straight pipe.
2. **Quarter-car:** with these CFD values the grip benefit drops from 8.7 % (ideal) to 5.0 %.
3. **Full car on real tracks:** the outcome depends on the car. On the soft **road Supra** and the **F-150**, the real
   inerter's built-in damping *helps* on circuits (CFD J-damper 4–7 % better than conventional, often better than the
   *ideal* inerter). On the stiff **GT4 race car** the fluid losses cancel most of the benefit (0–2 %).
   In every case it's a **trade-off between bump grip and body control.**

---

## 2. Slide-by-slide

| # | Slide | Show | Say (key numbers) |
|---|---|---|---|
| 1 | Title | Project page header | CFD characterisation of a helical-channel fluid inerter for race-car suspension |
| 2 | The J-damper | `cfd/results/demo/osc_X5.gif` | Inerter F = b·ẍ. A 40 mm piston drives oil through a 6 mm × 1.89 m coil: 46 g of oil acts like **91.7 kg** |
| 3 | Research question and method | Workflow on the project page | Mesh → validate → oscillating CFD → vehicle model → real tracks. Free tools: OpenFOAM + Python |
| 4 | Models built | `cfd/results/models/*.png` | Own structured hex-mesh generator (0.16–0.90M cells), periodic torus sector (2,560 cells), quarter car, full car |
| 5 | CFD validation | `cfd/results/s01_friction_ratio.png`, `gci_s01.png` | Friction within **0.3–3.6 %** of Ito (1959). Mesh uncertainty **0.1–0.3 %**. Pitch effect **< 0.1 %** |
| 6 | Seeing the flow | `cfd/results/dean_vortices.png`, `cfd/results/demo/osc_X5.gif` | Dean vortices push the fast oil to the outer wall. That costs friction but flattens the velocity profile |
| 7 | **Main CFD result** | `cfd/results/transient_coefficients.png` | Real inertance **1.02–1.26 × ideal** (straight pipe would be 1.22–1.33 ×). Damping **1.1–3.2 ×** straight pipe |
| 8 | Quarter-car grip | `python/results/cfd_vehicle_study.png` | Ideal **8.7 %**, CFD inerter **5.0 %**: real oil costs about 40 % of the benefit |
| 8b | The piston and its chambers | `cfd/results/device_cutaway.gif`, `piston_chamber_flow.gif`, `chamber_losses.png` | Port alone (2D): exit **K = 1.9** (textbook 1.0), entry 0.3–0.5; chambers add **+7.4 % damping** at 10 Hz. Drilled port as built (3D, `port3d_losses.png`, `port3d_flow.png`): two sharp elbows make it **K_in 2.6, K_out 3.8**. Quarter-car grip stays 5.0 %; track results move up to ±1 point. Lesson: radius the drillings |
| 8c | Cavitation | `cfd/results/cavitation.png` | Two-phase CFD: vapour below **1.75 MPa** pre-charge (hand calculation 1.73 MPa), in the ring vortex at the port |
| 9 | Real cars, real tracks | `sim/results/gt4_spa_eau_rouge.gif`, `f150_monza_braking.gif` | Toyota GR Supra (road + GT4) and Ford F-150 on Monza, Spa, Daytona. Weight transfer, pitch, roll, kerbs |
| 10 | Grip by track | `sim/results/chart_gain_by_track.png` | Table in section 3 below |
| 11 | Why it differs | `sim/results/chart_bumps_vs_body.png`, `supra_testroad_cfd.gif` | Inerter helps bumps (> 3 Hz). Removing damping hurts body control (< 3 Hz) |
| 12 | The trade-off | `sim/results/chart_tradeoff.png` | How much normal damping to keep depends on the car |
| 13 | Live demo | Simulator + project page | See section 5 |
| 14 | Conclusions | Section 4 below | |
| 15 | Limitations / next steps | Section 6 below | |

---

## 3. Track results (full laps, full-car model)

Change in tyre-load fluctuation vs the conventional suspension (**positive = steadier tyre load = more grip**).
"0 % kept" = the J-damper replaces the main damper; "50 %" = half the main damper is kept.
Source: `sim/results/track_comparison.csv` (all numbers, including bump/body split, wheel lifts, pitch, roll, heave).

| Vehicle | Track | Ideal J-damper, 0 % / 50 % kept | CFD J-damper, 0 % / 50 % kept |
|---|---|---|---|
| GR Supra (road) | Test road | +6.2 / +4.1 % | **+7.0 / +4.7 %** |
| | Monza | +1.4 / +2.0 % | **+4.8 / +3.8 %** |
| | Spa | −1.1 / +1.0 % | **+4.2 / +3.7 %** |
| | Daytona | **+7.3 / +9.6 %** | +5.0 / +7.0 % |
| GR Supra GT4 (race) | Test road | **+6.0 / +2.9 %** | −0.7 / −1.4 % |
| | Monza | **+4.9 / +4.6 %** | +1.9 / +1.8 % |
| | Spa | **+6.1 / +5.3 %** | +1.8 / +1.5 % |
| | Daytona | −1.9 / +0.6 % | **+2.8 / +3.6 %** |
| Ford F-150 | Test road | +6.1 / +4.3 % | **+6.8 / +5.2 %** |
| | Monza | +6.5 / +4.7 % | **+6.9 / +5.3 %** |
| | Spa | +4.0 / +3.5 % | **+7.2 / +6.0 %** |
| | Daytona | **+9.2 / +6.3 %** | +5.5 / +3.8 % |

**How the three suspensions differ:**

| | Conventional | Ideal J-damper | CFD J-damper (real fluid inerter) |
|---|---|---|---|
| What it is | Spring + damper per wheel | Adds a spring–damper–inerter branch with a perfect inerter (F = b·ẍ) | Same branch, but the inerter behaves as the CFD measured: inertance 1.02–1.26 × ideal plus parasitic damping |
| Bumps and wheel hop (> 3 Hz) | Baseline | Better (up to +7 %) | Better on soft cars (up to +9 %), little gain on the stiff GT4 |
| Body motion (< 3 Hz: braking, cornering) | Best controlled | Worse when the main damper is removed (down to −7 % on the Supra at Spa) | Its built-in fluid damping keeps body control (Supra +1 to +3 %) |
| Best for | Body control, simplicity | Stiff race car (GT4) on circuits | Soft road car (Supra) and heavy pickup (F-150) |
| Kerb strikes / wheel lifts | Same for all three: the inerter cannot stop a wheel lifting over a kerb | | |

**Vehicle dynamics (conventional, maximum over a lap):** pitch / roll

| Vehicle | Monza | Spa | Daytona |
|---|---|---|---|
| GR Supra (road) | 2.3° / 2.9° | 2.4° / 2.9° | 0.1° / 1.5° |
| GR Supra GT4 (race) | 1.0° / 1.6° | 1.0° / 1.7° | 0.1° / 0.8° |
| Ford F-150 | 1.6° / 3.2° | 1.7° / 3.2° | 0.3° / 0.6° |

Lap times (simulated): Supra road 2:10 Monza, 3:00 Spa; GT4 **1:54.6 Monza, 2:34.9 Spa** (real GT4 pace about 1:57 / 2:30);
F-150 2:37 Monza, 3:28 Spa.

---

## 4. Conclusions (for the last slide)

1. **CFD is validated:** within 0.3–3.6 % of established correlations, with mesh uncertainty 0.1–0.3 %.
2. **A real fluid inerter is not ideal:** its inertance is close to ideal (1.02–1.26 ×) because the Dean vortices flatten the
   flow, but it adds 1.1–3.2 × the parasitic damping of a straight pipe. A quasi-steady correlation predicts that damping
   to within about 4 %.
3. **On a single wheel**, real-fluid effects cost about 40 % of the ideal grip benefit (8.7 % → 5.0 %).
   The drilled ports and their sharp elbows lose ≈ 6.4 velocity heads (3D CFD; 2.3 for the port alone), yet grip stays at 5.0 %; the device
   needs at least ≈ 1.75 MPa pre-charge at 20 Hz, ±2.4 mm to stay free of cavitation.
4. **On real cars and tracks** the benefit is a trade-off between bump grip and body control:
   - soft road car / pickup: the real inerter's damping is an *advantage* (4–7 % better on circuits),
   - stiff race car: fluid losses cancel most of the gain (0–2 %); an ideal inerter would give 5–6 %,
   - kerb strikes are unaffected.
5. **Design implication:** for race cars, minimise parasitic damping (wider channel, see the diameter chart). For road cars,
   the parasitic damping can replace part of the main damper.

---

## 5. Live demo script (5 minutes)

1. Open the **project page** (`project_page.html`, or the online link) and scroll through the CFD results.
2. Show **"Watch the inerter work"**: play the CFD animation and switch the stroke between 2 mm and 5 mm.
3. Open the **track simulator** (`sim/track_simulator.html`):
   - **Test road, GR Supra, CFD J-damper, main damper 0 %**: the grip bars move clearly right (about +7 %).
   - Switch to **Spa**: watch Eau Rouge (compression, weight shift) and see the gain shrink. Point at the
     "Body (< 3 Hz)" bar for the **ideal** J-damper going negative.
   - Switch to the **GT4**: the CFD bars stay small. Explain the fluid losses at the higher frequencies of a stiff race car.
   - Move the **"Main damper kept"** slider to show the trade-off.
4. **ParaView** (`powershell -ExecutionPolicy Bypass -File open_paraview.ps1`, opens in about 20 s): press **Play** to animate the
   oscillating flow. Show the cross-section (Dean-vortex arrows), the residuals chart (converged to 1e-9), and the
   second layout tab "Steady helix Re 1000" (full 5-turn channel, streamlines and wall pressure).
   Tab **"Whole device"**: cutaway of the inerter, piston moving, chambers coloured by pressure, coil by oil velocity.
   Tab **"Piston chamber CFD"**: the port jet and ring vortex (left) and the vapour forming at 1 MPa pre-charge (right).
5. Optional: in Ubuntu, run the live CFD demo (`powershell -File live_demo.ps1`) to show OpenFOAM computing in real time.

---

## 6. Limitations and next steps (say these before you are asked)

- Laminar, isothermal oil (viscosity changes with temperature).
- The oscillating-piston and cavitation CFD are axisymmetric (2D) with a straight tube standing for the start of the coil; the
  3D drilled-port CFD is steady, and its unsteady damping uses the 2D oscillatory/steady ratio (0.85).
  The cavitation model uses a 2 kPa vapour/air-release pressure and does not model dissolved-air release in detail.
- Track simulator: tyres carry vertical load only. The lap profile is quasi-steady. Spring rates come from owner forums. CoG height, anti-roll bars and aero are estimates. The F-150's solid rear axle is modelled as independent.
- The live simulator uses the CFD inerter at 10 Hz. The frequency-domain study uses the full frequency dependence.
- Track numbers include the 3D port losses; the track charts and GIFs in `sim/results/` were recorded before that (CFD column differs by ≤ 1 point).
- Next: compare with published fluid-inerter experiments (Swift et al. 2013), radiused port passages, tyre force models, and a build-and-test rig.

---

## 7. Likely questions

- **Why a torus sector instead of the full helix?** Fully developed flow repeats every turn. I checked it against the full helix: < 0.1 % difference in friction, at about 1/100 of the cost (minutes instead of days).
- **How do you know the CFD is right?** Validation against the Ito/White correlations (0.3–3.6 %), a 3-mesh GCI study, and the Womersley exact solution as the straight-pipe limit.
- **Why is the inertance above the ideal formula?** The velocity profile isn't flat. A straight laminar pipe gives 4/3 × at low frequency. Dean vortices flatten the profile, bringing it closer to 1 ×.
- **Why does the ideal inerter do worse than the real one on the Supra at Spa?** With the main damper removed, an ideal inerter provides almost no damping at body frequencies, so the body wallows after braking. The real inerter's fluid friction damps that motion.
- **Is the track data real?** Monza and Spa centrelines come from the TUM racetrack database (satellite-measured). Daytona is built from its official dimensions. Vehicle mass, dimensions, power and tyres are published. The spring rates come from owner forums.
- **Did you model the piston?** Yes. The coil CFD uses continuity (piston area × piston speed = channel area × oil speed).
  The piston, its chambers and the ports are a separate axisymmetric CFD with a moving-piston boundary, coupled to the coil
  results at the tube end. It gives the port losses, a +7.4 % damping correction and the cavitation limit. A 3D CFD of the
  drilled port as built (radial hole + two sharp elbows into the helix) gives the full path loss: K_in 2.6, K_out 3.8.
- **Why is the exit loss 1.9 and not 1.0?** The textbook 1.0 assumes a flat (turbulent) velocity profile. Laminar flow leaves
  with a parabolic profile carrying twice the kinetic energy, and the chamber destroys all of it.
- **Why are the 3D port losses so much higher?** Each sharp 90° drilled elbow costs about one velocity head, and the oil arrives
  at the exit with a skewed Dean-flow profile. Radiusing the passages would bring the total back towards ≈ 2.3.
- **What would you do with more time?** Experimental validation, radiused port passages, a tyre model, and a full lap-time study.

---

## 8. Files and how to regenerate

| What | Where |
|---|---|
| Project page (all results, CFD animation, calculator) | `project_page.html` (online: claude.ai artifact) |
| Track simulator | `sim/track_simulator.html` (online: claude.ai artifact) |
| Track-sim charts and GIFs | `sim/results/*.png`, `sim/results/*.gif` |
| All track-sim numbers | `sim/results/track_comparison.csv` |
| CFD results | `cfd/results/` (validation, GCI, transient coefficients, Dean vortices, CFD animation) |
| Vehicle-study results | `python/results/` |

**Regenerating:** run `powershell -ExecutionPolicy Bypass -File run_all.ps1` for the CFD, vehicle study and simulator data. The track-sim
GIFs and comparison are recorded from the simulator: start `python sim/tools/sim_server.py`, open
`http://127.0.0.1:8766/sim/track_simulator.html`, load `sim/tools/capture.js`, then run `python sim/make_presentation_assets.py`.
