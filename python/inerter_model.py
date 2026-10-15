"""Core models for the helical-channel fluid inerter study (Python port of matlab/).

Contents
    params()                  baseline parameters (matlab/inerter_params.m)
    friction_factor_helical() curved-pipe Darcy friction factor (friction_factor_helical.m)
    inerter_force()           nonlinear quasi-steady inerter force (inerter_force.m)
    parasitic_ratio()         c_par / b for a channel diameter (parasitic_ratio.m)
    iso8608_psd(), iso8608_road()   road input (iso8608_road.m)
    quarter_car_freq()        linear quarter-car FRFs for any admittance Q(s) (quarter_car_freq.m)
    LAYOUTS                   suspension networks L1-L4 (run_quarter_car_study.m)
    fit_rom()                 reduced-order model fit to CFD force histories (fit_rom_from_cfd.m)

Units are SI throughout. Equations and their sources are in docs/theory.md.
"""
from dataclasses import dataclass, replace
import math

import numpy as np

trapz = getattr(np, 'trapezoid', None) or np.trapz      # NumPy 2 renamed trapz


# --------------------------------------------------------------------------- parameters
@dataclass(frozen=True)
class Params:
    # fluid: ISO VG 32 hydraulic oil at 40 C (isothermal)
    rho: float = 870.0          # density [kg/m^3]
    mu: float = 0.028           # dynamic viscosity [Pa s]
    p_vap: float = 2e3          # vapour pressure (approx.) [Pa]
    # inerter geometry
    D_p: float = 40e-3          # piston bore [m]
    d: float = 6e-3             # helical channel inner diameter [m]
    R_h: float = 30e-3          # helix radius to channel centreline [m]
    p_h: float = 10e-3          # helix pitch [m]
    n: int = 10                 # number of turns
    K_in: float = 2.6           # chamber -> channel loss: radial drilled port + 2 sharp elbows (3D port CFD, Re 250-500)
    K_out: float = 3.8          # channel -> chamber loss, same path (3D port CFD; 2D axisymmetric port alone: 0.4 / 1.9)
    F_c: float = 0.0            # seal Coulomb friction [N]
    v_s: float = 1e-3           # tanh smoothing velocity [m/s]
    # quarter car (GT / prototype race car corner - placeholder values)
    ms: float = 250.0           # sprung mass per corner [kg]
    mu_u: float = 35.0          # unsprung mass [kg]
    ks: float = 80e3            # wheel-rate spring [N/m]
    cs: float = 4000.0          # damper [N s/m]
    kt: float = 300e3           # tyre vertical stiffness [N/m]
    g: float = 9.81
    # road / speed
    V: float = 50.0             # vehicle speed [m/s]
    Gd_n0: float = 16e-6        # ISO 8608 class A [m^3]
    n0: float = 0.1             # reference spatial frequency [cycles/m]
    # optional override of the channel length (used to scale b in vehicle studies)
    l_override: float = 0.0

    # derived quantities
    @property
    def A_p(self):
        return math.pi * self.D_p ** 2 / 4

    @property
    def A_c(self):
        return math.pi * self.d ** 2 / 4

    @property
    def l(self):
        if self.l_override > 0:
            return self.l_override
        return self.n * math.hypot(2 * math.pi * self.R_h, self.p_h)

    @property
    def b(self):
        """Ideal inertance rho*l*A_p^2/A_c [kg]."""
        return self.rho * self.l * self.A_p ** 2 / self.A_c

    @property
    def c_lin(self):
        """Straight-pipe laminar damping 128*mu*l*A_p^2/(pi*d^4) [N s/m]."""
        return 128 * self.mu * self.l * self.A_p ** 2 / (math.pi * self.d ** 4)

    @property
    def delta(self):
        """Curvature ratio r/R_h."""
        return (self.d / 2) / self.R_h

    def with_inertance(self, b):
        """Same channel, length chosen so that the ideal inertance equals b."""
        return replace(self, l_override=b * self.A_c / (self.rho * self.A_p ** 2))


def params(**overrides):
    return Params(**overrides)


# --------------------------------------------------------------------------- fluid model
def friction_factor_helical(Re, delta, model='ito'):
    """Darcy friction factor in a helical/curved pipe.

    Laminar:    Ito (1959)   f_c/f_s = 21.5 De / (1.56 + log10 De)^5.73, 13.5 < De < 2000
                White (1929) f_c/f_s = 1/(1 - (1 - (11.6/De)^0.45)^(1/0.45)), De > 11.6
    Turbulent:  Ito (1959)   f_c = 0.304 Re^-0.25 + 0.029 sqrt(delta)
    Transition: Schmidt (1967) Re_crit = 2300 (1 + 8.6 delta^0.45)
    Returns (f, turbulent_mask, Re_crit).
    """
    Re = np.maximum(np.asarray(Re, dtype=float), 1e-9)
    De = Re * math.sqrt(delta)
    Re_crit = 2300 * (1 + 8.6 * delta ** 0.45)
    ratio = np.ones_like(Re)
    if model == 'ito':
        m = De > 13.5
        ratio[m] = 21.5 * De[m] / (1.56 + np.log10(De[m])) ** 5.73
    elif model == 'white':
        m = De > 11.6
        ratio[m] = 1 / (1 - (1 - (11.6 / De[m]) ** 0.45) ** (1 / 0.45))
    else:
        raise ValueError(f'unknown model {model!r}')
    f = 64 / Re * np.maximum(ratio, 1)
    turb = Re > Re_crit
    f = np.where(turb, 0.304 * Re ** -0.25 + 0.029 * math.sqrt(delta), f)
    return f, turb, Re_crit


def inerter_force(xdd, xd, p):
    """Quasi-steady fluid inerter force.

    F = b*xdd + A_p*dp_loss(v) + F_c*tanh(xd/v_s), with v = (A_p/A_c)*xd and
    dp_loss = (f_D*l/d + K_in + K_out)*0.5*rho*v|v|.
    The laminar friction term is evaluated in closed form so it stays finite as v -> 0.
    Returns (F, F_b, F_loss, dp_loss).
    """
    xdd = np.asarray(xdd, dtype=float)
    xd = np.asarray(xd, dtype=float)
    v = p.A_p / p.A_c * xd
    Re = p.rho * np.abs(v) * p.d / p.mu
    f, turb, _ = friction_factor_helical(Re, p.delta)
    ratio = f * np.maximum(Re, 1e-9) / 64
    dp_fric = np.where(turb,
                       f * p.l / p.d * 0.5 * p.rho * v * np.abs(v),
                       32 * p.mu * p.l * v / p.d ** 2 * ratio)
    dp_minor = (p.K_in + p.K_out) * 0.5 * p.rho * v * np.abs(v)
    dp_loss = dp_fric + dp_minor
    F_b = p.b * xdd
    F_loss = p.A_p * dp_loss + p.F_c * np.tanh(xd / p.v_s)
    return F_b + F_loss, F_b, F_loss, dp_loss


def parasitic_ratio(p, d=None, xd_rep=0.04):
    """Parasitic damping per kg of inertance, c_par/b [1/s].

    Laminar: c_par/b = 32*nu/d^2 * (f_c/f_s), which does not depend on channel length or piston area.
    Evaluated at a representative inerter velocity xd_rep (RMS found by run_time_domain.py).
    """
    d = p.d if d is None else d
    A_c = math.pi * d ** 2 / 4
    delta = (d / 2) / p.R_h
    v = p.A_p / A_c * xd_rep
    Re = p.rho * v * d / p.mu
    f, turb, _ = friction_factor_helical(Re, delta)
    f, turb = float(f), bool(turb)
    if not turb:
        return 32 * (p.mu / p.rho) / d ** 2 * (f * Re / 64)
    return f * 0.5 * v / d          # linearised turbulent loss


def port_damping(p, f, X, chamber_summary):
    """Equivalent linear damping of the piston chambers and ports [N s/m] at stroke X [m], frequency f [Hz].

    Quasi-steady linearisation of dp = (K_in + K_out) 1/2 rho v|v| (v = (A_p/A_c) xd):
        c = (8/3pi) (K_in + K_out) 1/2 rho (A_p/A_c)^2 A_p w X * r_cfd,
    r_cfd = oscillatory chamber CFD / quasi-steady value of the same (axisymmetric) geometry, K_tot,2D at Re 250-500
    (chamber_summary = cfd/results/chamber_summary.json). Independent of the channel length, i.e. of b.
    """
    osc = chamber_summary['oscillatory']
    k2d = np.mean([chamber_summary['K_in'][r] + chamber_summary['K_out'][r] for r in ('250', '500')])
    qs = 8 / (3 * math.pi) * 0.5 * p.rho * (p.A_p / p.A_c) ** 2 * p.A_p          # per unit K * w X
    r_cfd = osc['c_ports'] / (qs * k2d * 2 * math.pi * osc['f'] * osc['X_mm'] * 1e-3)
    return r_cfd * qs * (p.K_in + p.K_out) * 2 * np.pi * np.asarray(f) * X


def womersley_inerter(p, f):
    """Exact laminar oscillatory-flow (Womersley 1955) inerter coefficients for a STRAIGHT
    channel of the same length, at frequency f [Hz] (scalar or array).

    Mean velocity u = (G/(i w)) * F10,  F10 = 1 - 2 J1(L)/(L J0(L)),  L = alpha * i^(3/2),
    alpha = r sqrt(w/nu). With u = (A_p/A_c) xd and F = A_p rho l G this gives
    F = b_ideal (i w / F10) xd = b_eq(w) xdd + c_eq(w) xd, so
        b_eq = b_ideal Re(1/F10),   c_eq = -b_ideal w Im(1/F10).
    Limits: alpha -> 0: b_eq -> (4/3) b_ideal, c_eq -> c_lin;  alpha -> inf: b_eq -> b_ideal.
    Returns (b_eq, c_eq, alpha).
    """
    from scipy.special import jv
    f = np.asarray(f, dtype=float)
    w = 2 * np.pi * f
    alpha = (p.d / 2) * np.sqrt(w * p.rho / p.mu)
    L = alpha * np.exp(1j * 3 * np.pi / 4)
    F10 = 1 - 2 * jv(1, L) / (L * jv(0, L))
    inv = 1 / F10
    return p.b * inv.real, -p.b * w * inv.imag, alpha


def fit_harmonic(t, F, xd, xdd):
    """First-harmonic equivalent inertance and damping: least squares F = b_eq xdd + c_eq xd + F0
    for sinusoidal motion of arbitrary phase. Returns (b_eq, c_eq, nrmse)."""
    A = np.column_stack([xdd, xd, np.ones_like(xd)])
    th = np.linalg.lstsq(A, F, rcond=None)[0]
    res = F - A @ th
    return th[0], th[1], math.sqrt(np.mean(res ** 2)) / (F.max() - F.min())


# --------------------------------------------------------------------------- road input
def iso8608_psd(p, f):
    """One-sided temporal road displacement PSD [m^2/Hz] at frequencies f [Hz], speed p.V."""
    n = np.asarray(f) / p.V
    return p.Gd_n0 * (n / p.n0) ** -2 / p.V


def iso8608_road(p, T, fs=1000, f_band=(0.2, 50.0), df=0.05, seed=1):
    """Road displacement realisation by harmonic superposition (fixed seed, repeatable)."""
    t = np.arange(0, T + 0.5 / fs, 1 / fs)
    f = np.arange(f_band[0], f_band[1] + 1e-9, df)
    A = np.sqrt(2 * iso8608_psd(p, f) * df)
    ph = 2 * np.pi * np.random.default_rng(seed).random(f.size)
    zr = np.zeros_like(t)
    for Ak, fk, pk in zip(A, f, ph):          # loop keeps memory small for long records
        zr += Ak * np.sin(2 * np.pi * fk * t + pk)
    return t, zr


# --------------------------------------------------------------------------- quarter car
def quarter_car_freq(f, p, Q):
    """Linear quarter-car FRFs per unit road displacement for suspension admittance Q(jw).

    Admittance = force/velocity: spring k/s, damper c, inerter b*s (fluid inerter b*s + c_par);
    parallel: Q1 + Q2, series: 1/(1/Q1 + 1/Q2).
    Returns dict: Ft (dynamic tyre force), acc (sprung acceleration), st (suspension travel).
    """
    s = 1j * 2 * np.pi * np.asarray(f)
    Y = s * Q
    Zu = p.kt / (p.mu_u * s ** 2 + p.kt + Y * p.ms * s ** 2 / (p.ms * s ** 2 + Y))
    Zs = Y * Zu / (p.ms * s ** 2 + Y)
    return dict(Ft=p.kt * (1 - Zu), acc=s ** 2 * Zs, st=Zs - Zu)


def _ser(a, b):
    return 1 / (1 / a + 1 / b)


def _inr(s, b, cpb):
    return b * s + cpb * b          # fluid inerter admittance


# name, parameter names, initial guess, admittance builder Q(s, x, cpb, p)
LAYOUTS = [
    ('L1: k || c', ['c'], [3000.0],
     lambda s, x, cpb, p: p.ks / s + x[0]),
    ('L2: k || c || b', ['c', 'b'], [3000.0, 50.0],
     lambda s, x, cpb, p: p.ks / s + x[0] + _inr(s, x[1], cpb)),
    ('L3: k || (c ser b)', ['c', 'b'], [3000.0, 300.0],
     lambda s, x, cpb, p: p.ks / s + _ser(x[0], _inr(s, x[1], cpb))),
    ('L4: k || c1 || (k2 ser c2 ser b)', ['c1', 'b', 'c2', 'k2'], [300.0, 300.0, 3500.0, 5e5],
     lambda s, x, cpb, p: p.ks / s + x[0] + _ser(_ser(x[3] / s, x[2]), _inr(s, x[1], cpb))),
]


def grip_metric(p, Q_fun, f=None):
    """J_grip = RMS dynamic tyre force / static wheel load on the ISO 8608 road."""
    if f is None:
        f = np.linspace(0.2, 50, 3000)
    H = quarter_car_freq(f, p, Q_fun(1j * 2 * np.pi * f))
    return math.sqrt(trapz(np.abs(H['Ft']) ** 2 * iso8608_psd(p, f), f)) / ((p.ms + p.mu_u) * p.g)


# --------------------------------------------------------------------------- ROM fitting
def fit_rom(t, F, X, freq):
    """Fit inerter reduced-order models to one periodic force history.

    Motion assumed x = X sin(2*pi*freq*t); only the final full cycle is used.
    Returns dict with first-harmonic b_eq, c_eq and the time-domain fit
    F = b*xdd + c1*xd + c2*xd|xd| (b, c1, c2, nrmse).
    """
    t, F = np.asarray(t, float), np.asarray(F, float)
    m = t >= t[-1] - 1 / freq
    t, F = t[m], F[m]
    w = 2 * np.pi * freq
    xd, xdd = X * w * np.cos(w * t), -X * w ** 2 * np.sin(w * t)
    h = np.linalg.lstsq(np.column_stack([np.sin(w * t), np.cos(w * t), np.ones_like(t)]), F, rcond=None)[0]
    A = np.column_stack([xdd, xd, xd * np.abs(xd)])
    theta = np.linalg.lstsq(A, F, rcond=None)[0]
    Ffit = A @ theta
    return dict(b_eq=-h[0] / (X * w ** 2), c_eq=h[1] / (X * w),
                b=theta[0], c1=theta[1], c2=theta[2],
                nrmse=math.sqrt(np.mean((F - Ffit) ** 2)) / (F.max() - F.min()),
                freq=freq, X=X, x=X * np.sin(w * t), F=F, Ffit=Ffit)
