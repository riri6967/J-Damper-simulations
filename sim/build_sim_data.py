"""Build the data for the track simulator (sim/track_simulator.html).

1. Tracks
   Monza, Spa-Francorchamps: centrelines from the TUM FTM racetrack-database (LGPL-3.0,
   https://github.com/TUMFTM/racetrack-database), smoothed with a periodic spline.
   Spa elevation: approximate profile from published altitude figures (about 100 m total range,
   Eau Rouge/Raidillon compression and climb, Kemmel, Stavelot low point).
   Daytona International Speedway: tri-oval built from official dimensions (2.5 mi lap,
   turns 31 deg banking, tri-oval 18 deg, straights 3 deg, turn radius ~305 m).
   Kerbs: at corners tighter than R = 120 m, on the inside of the apex.
2. Vehicles: GT race coupe and a high-riding performance pickup (generic, representative values).
3. Quasi-steady-state lap simulation per vehicle and track: friction-ellipse limited speed profile
   with power, drag, downforce, banking and slope -> speed, ax, ay (in road plane) and the extra
   vertical acceleration (crests/compressions + banking) along the lap.
4. Suspension tuning per vehicle (front-corner quarter car, ISO 8608 class A, same method as
   python/run_cfd_vehicle_study.py): conventional damper, J-damper with ideal inerter, J-damper
   with the CFD-measured inerter (channel + piston chambers/ports, 10 Hz, 2 mm).
Writes sim/sim_data.json and sim/track_simulator.html.   Usage: python build_sim_data.py
"""
import json
import math
import os
import sys
from dataclasses import replace

import numpy as np
from scipy.interpolate import splprep, splev, PchipInterpolator
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'python'))
import inerter_model as im   # noqa: E402

G, RHO_AIR, DS = 9.81, 1.2, 5.0

# Wheel rates = spring rate x motion ratio^2. Published = manufacturer data; forum = owner-community
# figures (not official); est = engineering estimate. See the 'sources' field of each vehicle.
VEHICLES = {
    'supra': dict(name='Toyota GR Supra 3.0 (A90)', ms=1520.0 - 2 * 42 - 2 * 46, mu=44.0, a=1.235, b=1.235,
                  track=1.592, h=0.46, hrc=0.06,
                  ksf=29.4e3 * 0.95 ** 2, ksr=90.2e3 * 0.60 ** 2, karbf=32e3, karbr=14e3,
                  anti_dive=0.20, anti_squat=0.25, bump_gap=0.040, bump_k=60e3, bump_k2=4e7, kt=290e3, mu_tyre=1.10, ClA=0.08, CdA=0.62,
                  power=285e3, vmax=69.4, Iy=1700.0, Ix=480.0, wheelR=0.334, gmax=1.4,
                  sources=['mass 1,495-1,541 kg, wheelbase 2,470 mm, track 1,594/1,589 mm, 50:50, 285 kW, '
                           '255/35R19 F / 275/35R19 R, 250 km/h limit: Toyota (published)',
                           'spring rates 29.4 N/mm F / 90.2 N/mm R: SupraMKV owner forum (not official)',
                           'motion ratios 0.95 F / 0.60 R, progressive bump stops (40 mm gap), anti-roll bars, CoG height, aero, inertias: estimated']),
    'gt4': dict(name='Toyota GR Supra GT4 (race)', ms=1350.0 - 2 * 38 - 2 * 42, mu=40.0, a=1.21, b=1.26,
                track=1.62, h=0.42, hrc=0.06,
                ksf=140e3, ksr=160e3, karbf=120e3, karbr=70e3,
                anti_dive=0.25, anti_squat=0.30, bump_gap=0.025, bump_k=150e3, bump_k2=8e7, kt=320e3, mu_tyre=1.55,
                ClA=0.85, CdA=0.78, power=330e3, vmax=72.0, Iy=1500.0, Ix=430.0, wheelR=0.330, gmax=2.0,
                sources=['GT4: weight 1,350 kg, length 4,460 mm, width 1,855 mm, 2,998 cc turbo I6 up to 660 Nm, '
                         'MacPherson F / multilink R, KW dampers, Pirelli tyres: Toyota Gazoo Racing (published)',
                         'power (Balance of Performance, ~330 kW), wheelbase (road car), springs, anti-roll bars, aero, '
                         'slick grip, weight split, CoG height: estimated']),
    'f150': dict(name='Ford F-150 SuperCrew 4x4 (2021)', ms=2270.0 - 2 * 70 - 2 * 95, mu=82.0, a=3.683 * 0.43, b=3.683 * 0.57,
                 track=1.73, h=0.80, hrc=0.30,
                 ksf=104e3 * 0.60 ** 2, ksr=43e3, karbf=26e3, karbr=8e3,
                 anti_dive=0.25, anti_squat=0.30, bump_gap=0.070, bump_k=80e3, bump_k2=3e7, kt=260e3, mu_tyre=0.85, ClA=0.0, CdA=1.55,
                 power=298e3, vmax=47.8, Iy=5200.0, Ix=1250.0, wheelR=0.419, gmax=1.1,
                 sources=['mass 2,025-2,502 kg (SuperCrew range), wheelbase 145 in (3,683 mm), 3.5 EcoBoost 298 kW, '
                          '275/60R20: Ford / dealer listings (published)',
                          'front coil 594 lb/in (104 N/mm), rear leaf 247/388 lb/in (first stage used): F150Gen14 owner forum (not official)',
                          'track 1.73 m, 57:43 weight split, motion ratio 0.60 F, bump stops (70 mm gap), anti-roll bars, CoG height, aero, '
                          '172 km/h limiter: estimated']),
}
DAMPER_KEPT = [0.0, 0.25, 0.5, 0.75, 1.0]      # fraction of the conventional damper kept with the J-damper
LOG_LO, LOG_HI = np.log([0.5, 50.0, 1e3]), np.log([3000.0, 1e6, 1e8])   # bounds on b [kg], c2 [N s/m], k2 [N/m]


# ------------------------------------------------------------------ tracks
def load_tumftm(name):
    a = np.loadtxt(os.path.join(HERE, 'track_data_raw', f'{name}.csv'), delimiter=',', comments='#')
    x, y = a[:, 0], a[:, 1]
    tck, _ = splprep([np.append(x, x[0]), np.append(y, y[0])], s=len(x) * 1.5, per=True)
    u = np.linspace(0, 1, 20000)
    xs, ys = splev(u, tck)
    L = np.sum(np.hypot(np.diff(xs), np.diff(ys)))
    n = int(round(L / DS))
    # arc-length resample
    sc = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
    s = np.linspace(0, sc[-1], n, endpoint=False)
    uu = np.interp(s, sc, u)
    xs, ys = splev(uu, tck)
    dx, dy = splev(uu, tck, der=1)
    ddx, ddy = splev(uu, tck, der=2)
    kappa = (dx * ddy - dy * ddx) / (dx * dx + dy * dy) ** 1.5
    return s, np.asarray(xs), np.asarray(ys), kappa, sc[-1]


def spa_elevation(s, L):
    # (distance from start line [km], relative altitude [m]); approximate published profile
    pts = [(0.00, 0), (0.30, -4), (0.45, -8), (0.62, -20), (0.72, -27), (0.80, -24), (0.93, -6), (1.05, 6),
           (1.30, 14), (1.60, 25), (2.00, 36), (2.20, 38), (2.45, 30), (2.70, 18), (3.00, 6), (3.40, -8),
           (3.90, -22), (4.40, -42), (4.80, -60), (5.20, -55), (5.60, -40), (6.00, -28), (6.40, -16),
           (6.70, -6), (L / 1000, 0)]
    k, z = np.array(pts).T
    return PchipInterpolator(k * 1000, z)(s)


def daytona():
    R, bank_turn, bank_tri, bank_str = 305.0, 31.0, 18.0, 3.0
    turn_ang, tri_ang, tri_R = math.radians(170), math.radians(20), 1100.0
    L_total = 4023.4
    L_turn, L_tri = R * turn_ang, tri_R * tri_ang
    L_back = 914.4
    L_front = (L_total - 2 * L_turn - L_tri - L_back) / 2
    segs = [(L_tri / 2, 1 / tri_R, bank_tri), (L_front, 0, bank_str), (L_turn, 1 / R, bank_turn),
            (L_back, 0, bank_str), (L_turn, 1 / R, bank_turn), (L_front, 0, bank_str), (L_tri / 2, 1 / tri_R, bank_tri)]
    n = int(round(L_total / DS))
    s = np.linspace(0, L_total, n, endpoint=False)
    kappa, bank = np.zeros(n), np.zeros(n)
    edges = np.cumsum([0] + [sg[0] for sg in segs])
    for (Ls, k, bk), e0 in zip(segs, edges[:-1]):
        m = (s >= e0) & (s < e0 + Ls)
        kappa[m], bank[m] = k, bk
    # smooth transitions (spiral entries ~ 120 m)
    w = int(120 / DS)
    ker = np.ones(w) / w
    sm = lambda a: np.convolve(np.concatenate([a[-w:], a, a[:w]]), ker, 'same')[w:-w]
    kappa, bank = sm(kappa), sm(bank)
    kappa *= 2 * math.pi / (np.sum(kappa) * DS)                       # exact closure in heading
    th = np.cumsum(kappa) * DS
    x, y = np.cumsum(np.cos(th)) * DS, np.cumsum(np.sin(th)) * DS
    gap = np.array([x[-1] + DS * math.cos(th[-1]) - x[0], y[-1] + DS * math.sin(th[-1]) - y[0]])
    x -= np.linspace(0, 1, n) * gap[0]
    y -= np.linspace(0, 1, n) * gap[1]
    return s, x, y, kappa, np.radians(bank), L_total


def kerbs(s, kappa, Rmax=120.0):
    out = []
    ak = np.abs(kappa)
    for i in range(len(s)):
        if ak[i] > 1 / Rmax and ak[i] >= ak[i - 1] and ak[i] >= ak[(i + 1) % len(s)]:
            if not out or s[i] - out[-1][0] > 60:
                out.append((float(s[i]), 1 if kappa[i] > 0 else -1))   # +1: left-hand corner -> left wheels hit kerb
    return out


# ------------------------------------------------------------------ lap simulation
def lap_sim(veh, s, kappa, z, bank):
    m = veh['ms'] + 4 * veh['mu']
    n = len(s)
    slope = np.gradient(z, DS)
    curv_v = np.gradient(slope, DS)                                    # + in a dip (compression)
    mu = veh['mu_tyre']

    def lat_limit(v, k, b):
        if abs(k) < 1e-6:
            return -1.0                                                # straight: never limited by grip
        Fd = 0.5 * RHO_AIR * veh['ClA'] * v * v
        need = v * v * abs(k) * math.cos(b) - G * math.sin(b)         # banking leans into the turn
        avail = mu * (G * math.cos(b) + v * v * abs(k) * math.sin(b) + Fd / m)
        return need - avail

    vlim = np.empty(n)
    for i in range(n):
        lo, hi = 1.0, veh['vmax']
        if lat_limit(hi, kappa[i], bank[i]) <= 0:
            vlim[i] = hi
            continue
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if lat_limit(mid, kappa[i], bank[i]) <= 0 else (lo, mid)
        vlim[i] = lo

    def ay_of(v, i):
        return v * v * kappa[i] * math.cos(bank[i]) - G * math.sin(bank[i]) * np.sign(kappa[i])

    def ay_max(v, i):
        Fd = 0.5 * RHO_AIR * veh['ClA'] * v * v
        return mu * (G * math.cos(bank[i]) + v * v * abs(kappa[i]) * math.sin(bank[i]) + Fd / m)

    v = vlim.copy()
    for rep in range(2):                                               # two laps -> periodic solution
        for i in range(n):                                             # forward: traction / power
            j = (i + 1) % n
            vi = v[i]
            amax = ay_max(vi, i)
            ellipse = math.sqrt(max(0.0, 1 - (ay_of(vi, i) / amax) ** 2))
            a_trac = min(veh['power'] / (m * max(vi, 5.0)), 0.6 * amax) * ellipse
            a = a_trac - 0.5 * RHO_AIR * veh['CdA'] * vi * vi / m - G * slope[i]
            v[j] = min(v[j], math.sqrt(max(1.0, vi * vi + 2 * a * DS)), vlim[j])
        for i in range(n - 1, -1, -1):                                 # backward: braking
            j = (i + 1) % n
            vj = v[j]
            amax = ay_max(vj, j)
            ellipse = math.sqrt(max(0.0, 1 - (ay_of(vj, j) / amax) ** 2))
            a_brk = amax * ellipse + 0.5 * RHO_AIR * veh['CdA'] * vj * vj / m + G * slope[j]
            v[i] = min(v[i], math.sqrt(max(1.0, vj * vj + 2 * a_brk * DS)))
    ax = (np.roll(v, -1) ** 2 - v ** 2) / (2 * DS)
    ay = np.array([ay_of(v[i], i) for i in range(n)])
    az = v * v * curv_v + (G * np.cos(bank) + v * v * np.abs(kappa) * np.sin(bank) - G)   # extra vertical accel
    lap = float(np.sum(DS / v))
    return v, ax, ay, az, lap


# ------------------------------------------------------------------ suspension tuning (quarter car)
CFD = json.load(open(os.path.join(HERE, '..', 'cfd', 'results', 'inerter_cfd_coeffs.json')))
CHAMBER = json.load(open(os.path.join(HERE, '..', 'cfd', 'results', 'chamber_summary.json')))


def tune_axle(veh, axle):
    front = axle == 'front'
    L = veh['a'] + veh['b']
    ms_corner = veh['ms'] * (veh['b'] if front else veh['a']) / L / 2
    p = replace(im.params(), ms=ms_corner, mu_u=veh['mu'], ks=veh['ksf'] if front else veh['ksr'], kt=veh['kt'], V=35.0)
    f = np.linspace(0.2, 50, 2000)
    s = 1j * 2 * np.pi * f
    bw, cw, _ = im.womersley_inerter(p, f)
    d = CFD['amplitudes']['2mm']
    lq = np.log(f)
    kb = np.interp(lq, np.log(d['f']), np.array(d['b_ratio']) / np.array(d['b_womersley_ratio']))
    kc = np.interp(lq, np.log(d['f']), np.array(d['c_ratio']) / np.array(d['c_womersley_ratio']))
    cport = im.port_damping(p, f, 2e-3, CHAMBER)                       # chambers, ports, drilled elbows (X = 2 mm)
    qbs = {'ideal': (s, 0.0), 'cfd': (kb * bw / p.b * s + kc * cw / p.b, cport)}
    ser = lambda a, b: 1 / (1 / a + 1 / b)
    J = lambda Q: im.grip_metric(p, lambda _s: Q, f)
    r0 = minimize(lambda lc: J(p.ks / s + math.exp(lc[0])), [math.log(3000.0)], method='Nelder-Mead')
    cs = math.exp(r0.x[0])
    levels = []
    for frac in DAMPER_KEPT:
        lev = dict(kept=frac)
        for key, (qb, cadd) in qbs.items():
            best = None
            for sc in (0.3, 1.0, 3.0):
                bx = lambda lx: np.exp(np.clip(lx, LOG_LO, LOG_HI))          # b, c2, k2 kept in physical ranges
                r = minimize(lambda lx: J(p.ks / s + frac * cs + ser(ser(bx(lx)[2] / s, bx(lx)[1]), bx(lx)[0] * qb + cadd)),
                             np.log(np.array([300.0, 3500.0, 5e5]) * sc), method='Nelder-Mead',
                             options=dict(maxiter=3000, xatol=1e-6, fatol=1e-10))
                if best is None or r.fun < best.fun:
                    best = r
            b, c2, k2 = np.exp(np.clip(best.x, LOG_LO, LOG_HI))
            lev[key] = dict(b=round(b, 2), c2=round(c2, 1), k2=round(k2, 0), gain=round(100 * (r0.fun - best.fun) / r0.fun, 2))
        levels.append(lev)
    i10 = d['f'].index(10.0)
    return dict(cs=round(cs, 1), zeta=round(cs / (2 * math.sqrt(p.ks * ms_corner)), 3),
                ride_hz=round(math.sqrt(p.ks * p.kt / (p.ks + p.kt) / ms_corner) / (2 * math.pi), 2), levels=levels,
                cfd_bEff_ratio=d['b_ratio'][i10], cfd_cPar_per_kg=d['c_ratio'][i10] * p.c_lin / p.b,
                cfd_cPort=round(float(im.port_damping(p, 10.0, 2e-3, CHAMBER)), 1))


def tune(veh):
    return dict(front=tune_axle(veh, 'front'), rear=tune_axle(veh, 'rear'))


def main():
    tracks = {}
    for name, key in (('Monza', 'monza'), ('Spa', 'spa')):
        s, x, y, k, L = load_tumftm(name)
        z = spa_elevation(s, L) if key == 'spa' else np.zeros_like(s)
        tracks[key] = dict(s=s, x=x, y=y, kappa=k, z=z, bank=np.zeros_like(s), L=L)
    s, x, y, k, bank, L = daytona()
    tracks['daytona'] = dict(s=s, x=x, y=y, kappa=k, z=np.zeros_like(s), bank=bank, L=L)
    # straight test road: constant speed, no braking or cornering, rough public-road surface (ISO 8608 class B)
    L = 3000.0
    s = np.arange(0, L, DS)
    tracks['test'] = dict(s=s, x=s.copy(), y=np.zeros_like(s), kappa=np.zeros_like(s), z=np.zeros_like(s), bank=np.zeros_like(s), L=L)
    names = {'test': 'Straight test road (ISO 8608 class B, 100 km/h)', 'monza': 'Monza (Autodromo Nazionale)', 'spa': 'Spa-Francorchamps', 'daytona': 'Daytona International Speedway (oval)'}
    out = dict(source='Monza/Spa centrelines: TUM FTM racetrack-database (LGPL-3.0). Spa elevation approximate. '
                      'Daytona from official dimensions.', vehicles={}, tracks={})
    for vk, veh in VEHICLES.items():
        t = tune(veh)
        out['vehicles'][vk] = dict(veh, susp=t)
        for ax in ('front', 'rear'):
            a = t[ax]
            print(f"{veh['name']:<34} {ax:<5} ride {a['ride_hz']:.2f} Hz  damper {a['cs']:.0f} N s/m (zeta {a['zeta']:.2f})  " +
                  '  '.join(f"kept {l['kept']:.0%}: ideal {l['ideal']['gain']:.1f}% cfd {l['cfd']['gain']:.1f}%" for l in a['levels']))
    for tk, tr in tracks.items():
        rec = dict(name=names[tk], L=round(float(tr['L']), 1), ds=DS,
                   x=np.round(tr['x'], 2).tolist(), y=np.round(tr['y'], 2).tolist(),
                   z=np.round(tr['z'], 3).tolist(), bank=np.round(np.degrees(tr['bank']), 2).tolist(),
                   kappa=np.round(tr['kappa'], 6).tolist(), kerbs=kerbs(tr['s'], tr['kappa']), laps={},
                   gd0=64e-6 if tk == 'test' else 4e-6)
        for vk, veh in VEHICLES.items():
            if tk == 'test':
                n = len(tr['s']); v = np.full(n, 27.8); ax = ay = az = np.zeros(n); lap = tr['L'] / 27.8
            else:
                v, ax, ay, az, lap = lap_sim(veh, tr['s'], tr['kappa'], tr['z'], tr['bank'])
            rec['laps'][vk] = dict(v=np.round(v, 2).tolist(), ax=np.round(ax, 2).tolist(), ay=np.round(ay, 2).tolist(),
                                   az=np.round(az, 2).tolist(), lap_time=round(lap, 2))
            print(f"  {names[tk]:<40} {veh['name']:<20} lap {int(lap // 60)}:{lap % 60:05.2f}  vmax {v.max() * 3.6:5.0f} km/h  "
                  f"max lat {np.abs(ay).max() / G:.2f} g  max brake {-ax.min() / G:.2f} g  max vert {az.max() / G:+.2f} g")
        rec['n_kerbs'] = len(rec['kerbs'])
        out['tracks'][tk] = rec
    path = os.path.join(HERE, 'sim_data.json')
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    tpl = open(os.path.join(HERE, 'track_simulator.template.html'), encoding='utf-8').read()
    data = open(path, encoding='utf-8').read().replace('</', '<\/')
    open(os.path.join(HERE, 'track_simulator.html'), 'w', encoding='utf-8').write(tpl.replace('__SIMDATA__', data))
    print(f'wrote {path} ({os.path.getsize(path) / 1024:.0f} KB) and track_simulator.html; kerbs: ' +
          ', '.join(f"{k} {v['n_kerbs']}" for k, v in out['tracks'].items()))


if __name__ == '__main__':
    main()
