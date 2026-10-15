# Theory: Helical-Channel Fluid Inerter

## 1. Geometry and notation

| Symbol | Meaning | Baseline |
|---|---|---|
| `D_p` | Piston (bore) diameter | 40 mm |
| `A_p` | Effective piston area | π D_p²/4 |
| `d` | Channel (tube) inner diameter, `r = d/2` | 6 mm |
| `A_c` | Channel cross-section area | π d²/4 |
| `R_h` | Helix (coil) radius, measured to the channel centreline | 30 mm |
| `p_h` | Helix pitch | 10 mm |
| `n` | Number of turns | 10 |
| `l` | Channel length, `l = n·sqrt((2πR_h)² + p_h²)` | ≈ 1.89 m |
| `ρ, μ` | Oil density and dynamic viscosity (ISO VG 32 at 40 °C) | 870 kg/m³, 0.028 Pa·s |

The baseline values are a starting design. Use `matlab/analyse_inerter.m` to change them and see the effect.

## 2. Ideal inerter

Assume incompressible flow. Continuity links the piston velocity `ẋ` to the mean channel velocity:

    v = (A_p / A_c) · ẋ

The kinetic energy of the oil in the channel is `½ ρ A_c l v²`. Writing it in terms of `ẋ` gives the inertance:

    b = ρ · l · A_p² / A_c          [kg]

Baseline: about **92 kg** from roughly 0.05 kg of oil. The *area ratio squared* (A_p/A_c)² ≈ 1975 is
the mechanical "gearing". The force is `F_b = b · ẍ`.

## 3. Losses (the "real" part)

### 3.1 Total pressure drop (quasi-steady)

    Δp_loss = ( f_D · l/d + K_in + K_out ) · ½ ρ v |v|

- `f_D` is the Darcy friction factor for the **curved** channel.
- `K_in` (chamber → channel) and `K_out` (channel → chamber) are the minor-loss coefficients of everything between
  the chamber and the helix. Textbook values for a sharp port alone are 0.5 and 1.0. The axisymmetric port CFD
  (`cfd/results/chamber_summary.json`) gives 0.38 and 1.92 (laminar exit profile, α ≈ 2). The 3D CFD of the drilled
  port as built, a radial hole with two sharp 90° elbows into the helix (`cfd/results/port3d_summary.json`), gives
  `K_in ≈ 2.6` and `K_out ≈ 3.8` at Re 250–500. These are the model defaults.

The loss force is `F_loss = A_p · Δp_loss`.

### 3.2 Dimensionless groups

| Group | Definition | What it controls |
|---|---|---|
| Reynolds | `Re = ρ |v| d / μ` | Laminar vs turbulent flow |
| Dean | `De = Re · sqrt(r / R_h)` | Strength of the secondary (Dean) vortices |
| Womersley | `α = r · sqrt(ω ρ / μ)` | Quasi-steady (α < ~1) vs inertia-dominated oscillatory flow |
| Curvature ratio | `δ = r / R_h` | Geometric effect of the curvature |
| Torsion | `τ = p_h / (2π R_h)` (approximately) | Effect of the pitch. Second-order effect when small |

### 3.3 Curved-pipe friction correlations

Straight laminar pipe: `f_s = 64 / Re`.

**Laminar, curved (Ito 1959), valid for 13.5 < De < 2000:**

    f_c / f_s = 21.5 De / (1.56 + log10 De)^5.73

(Below De ≈ 13.5, `f_c / f_s ≈ 1`.)

**Laminar, curved (White 1929), useful for cross-checking:**

    f_c / f_s = 1 / { 1 - [ 1 - (11.6/De)^0.45 ]^(1/0.45) }

**Laminar-to-turbulent transition (Schmidt 1967).** Curvature *delays* transition:

    Re_crit = 2300 · ( 1 + 8.6 · (r/R_h)^0.45 )

At the baseline geometry, Re_crit ≈ 9300, so most operating points are laminar.

**Turbulent, curved (Ito 1959), valid for 0.034 < Re·(r/R_h)² < 300:**

    f_c = 0.304 · Re^(-0.25) + 0.029 · sqrt(r/R_h)

### 3.4 Linear (laminar, low-Re) parasitic damping

For straight-pipe Hagen-Poiseuille flow, `Δp = 128 μ l Q / (π d⁴)` with `Q = A_p ẋ`. This gives

    c_lin = 128 μ l A_p² / (π d⁴)        [N·s/m]

Baseline: about **2.6 kN·s/m**. This is the same order as a race-car damper, so **the parasitic damping is not
negligible**, and it is the central point of this study. Curvature multiplies it by `f_c/f_s`.

## 4. Unsteady (oscillatory) flow

For sinusoidal motion `x = X sin(ωt)`, the Stokes layer thickness is `δ_s = sqrt(2ν/ω)`.

- When `α` is small, the flow profile is parabolic and the quasi-steady model holds.
- When `α` is large (at baseline, α ≈ 4 at 10 Hz), the core moves like a plug and the shear is confined
  to a thin wall layer. As a result, **the effective inertance and damping change with frequency.**
  Womersley's solution for a straight pipe predicts this. CFD gives the version that includes curvature.

Write the fitted CFD result as a first-harmonic equivalent at each frequency:

    F(t) ≈ b_eq(ω) · ẍ + c_eq(ω) · ẋ

Or write it as a time-domain reduced-order model (ROM):

    F = b · ẍ + c1 · ẋ + c2 · ẋ|ẋ| + F_c · tanh(ẋ / v_s)

The last term is seal (Coulomb) friction. Since this project has no seals, it is optional.

## 5. Cavitation check

The inertial pressure difference across the piston is `Δp_b = b · ẍ / A_p = ρ l (A_p/A_c) ẍ`.

Cavitation occurs on the low-pressure side if

    p_charge - Δp_b/2 - Δp_loss/2  <  p_vap  (≈ a few kPa for mineral oil)

The baseline at 20 Hz and ±5 mm gives Δp_b ≈ 5-6 MPa, so **the device must be pre-charged** (that is,
pressurised). Report the onset map (amplitude vs frequency) as a design result.

## 5b. Parasitic damping per kg of inertance

Divide the laminar damping by the inertance:

    c_par / b = 32 ν / d² · (f_c / f_s)        [1/s]

This ratio **does not depend on the channel length or the piston area**. Only the channel diameter (and
the curvature, through Dean flow) sets how lossy each kilogram of inertance is. At the baseline
(d = 6 mm, inerter velocity about 0.04 m/s) the ratio is about 43 1/s.

The design tension is:

    l = b · A_c / (ρ · A_p²)

A wider channel has smaller losses, but it needs a *longer* helix (or a bigger piston) to reach the same `b`.
**Packaging against fluid losses** is therefore the central design trade-off, and CFD is what quantifies
the loss side of it.

## 6. Quarter-car model with an inerter

The spring `k_s`, damper `c_s` and inerter `F_in` act in parallel between the sprung mass `m_s` and the
unsprung mass `m_u`. The tyre stiffness is `k_t` and the road input is `z_r`.

    m_s z̈_s = -k_s(z_s - z_u) - c_s(ż_s - ż_u) - F_in
    m_u z̈_u =  k_s(z_s - z_u) + c_s(ż_s - ż_u) + F_in - k_t(z_u - z_r)
    F_in    =  b(z̈_s - z̈_u) + F_loss(ż_s - ż_u)

Because `F_in` contains accelerations, move the inertance terms to a **mass matrix**:

    [ m_s + b    -b     ] [z̈_s]   [ -k_s Δz - c_s Δż - F_loss                 ]
    [   -b     m_u + b  ] [z̈_u] = [  k_s Δz + c_s Δż + F_loss - k_t(z_u - z_r) ]

This system is solved with `ode45` and `odeset('Mass', M)`.

**Performance metrics** (Smith & Wang 2004):

- **Grip:** `J_grip = RMS(k_t (z_r - z_u)) / ((m_s + m_u) g)`, the dynamic tyre-load ratio. Lower is better.
- **Ride:** RMS sprung-mass acceleration.
- **Packaging:** RMS suspension travel `z_s - z_u`.

### 6.1 Suspension layouts (admittance form)

Each element has a mechanical admittance Q (force/velocity): spring `k/s`, damper `c`, inerter `b·s`,
and fluid inerter `b·s + c_par`. Parallel elements add. Series elements combine as `1/(1/Q1 + 1/Q2)`.

| Layout | Network | Comment |
|---|---|---|
| L1 | k ‖ c | Conventional baseline |
| L2 | k ‖ c ‖ b | Parallel inerter |
| L3 | k ‖ (c in series with b) | |
| L4 | k ‖ c1 ‖ (k2 in series with c2 in series with b) | J-damper style series branch |

The layout with the series branch (L4) needs extra internal states in the time domain:
inerter stroke `x1`, damper stroke `x2`, and branch force `F_b = k2(x - x1 - x2) = c2·ẋ2 = b·ẍ1 + F_loss(ẋ1)`.

### 6.2 Preliminary results (baseline car, class A road, 180 km/h; frequency domain)

| Layout | Ideal inerter | Fluid inerter, d = 6 mm |
|---|---|---|
| L2 parallel | 0 % | 0 % |
| L3 damper-inerter series | 3.1 % | 0 % |
| L4 J-damper branch | **8.7 %** | **about 4.4 %** |

The values are the reduction in RMS dynamic tyre load, with all element values re-optimised for each case.
**Fluid losses remove roughly half of the grip benefit**, and a parallel inerter gives none. The
d-sweep gives 3.7 % (3 mm) up to 6.5 % (12 mm). Treat these as placeholders until the CFD-fitted model
replaces the correlation-based loss model.

Road excitation follows ISO 8608, `G_d(n) = G_d(n0)·(n/n0)^-2` with `n0 = 0.1` cycles/m. A race
track is about class A, `G_d(n0) = 16e-6 m³`.
