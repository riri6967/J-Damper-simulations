"""Live viewer: watch an oscillating OpenFOAM case while it is running.

Opens a window that refreshes every half second from the files OpenFOAM is writing:
    left    oil velocity in the channel vs simulated time (and the oscillating driving pressure)
    middle  latest snapshot of the channel cross-section: oil speed (colour) + Dean vortices
    right   piston force vs displacement, drawing itself as the cycles go by
Start it just before (or while) running the torus_demo set; it waits for the case to appear.

Usage: python watch_live.py [osc_X5|osc_X2]
"""
import glob
import math
import os
import subprocess
import sys
import time

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import render_demo as RD   # noqa: E402  (reuses the cross-section reader and plotting)

CASE = sys.argv[1] if len(sys.argv) > 1 else 'osc_X5'
home = subprocess.run(['wsl.exe', '-e', 'bash', '-c', 'wslpath -w ~'], capture_output=True, text=True).stdout
win = os.path.join(home.replace('\x00', '').strip(), 'inerter', 'torus_demo', CASE)
START = time.time()                                    # ignore files left over from an earlier run
print(f'watching {win}')
meta = RD.json.load(open(os.path.join(RD.root, CASE, 'case_info.json')))
w0, G_amp = 2 * math.pi * meta['freq'], meta['G_amp']
p = RD.p


def read_flux():
    f = glob.glob(os.path.join(win, 'postProcessing', 'flux', '*', 'surfaceFieldValue.dat'))
    if not f or os.path.getmtime(f[0]) < START - 5:
        return None
    try:
        a = np.array([[float(v) for v in ln.split()[:2]] for ln in open(f[0]) if ln.strip() and not ln.startswith('#')
                      and len(ln.split()) >= 2])
    except (ValueError, OSError):
        return None
    return a if len(a) > 2 else None


def latest_snapshot():
    snaps = [s for s in glob.glob(os.path.join(win, 'postProcessing', 'live', '*', 'U_cyc1.raw'))
             if os.path.getmtime(s) >= START - 5]
    if not snaps:
        return None, None
    s = max(snaps, key=lambda s: float(os.path.basename(os.path.dirname(s))))
    return s, float(os.path.basename(os.path.dirname(s)))


plt.ion()
fig, (a0, a1, a2) = plt.subplots(1, 3, figsize=(14, 4.6), gridspec_kw=dict(width_ratios=[1.3, 1, 1.15]))
fig.canvas.manager.set_window_title('Fluid inerter: live CFD')
shown_snap = None
t_wait = time.time()
while plt.fignum_exists(fig.number):
    a = read_flux()
    if a is None:
        fig.suptitle(f'Waiting for OpenFOAM to start {CASE} ... ({time.time() - t_wait:.0f} s)', fontsize=12)
        plt.pause(0.5)
        continue
    t, u = a[:, 0], -a[:, 1] / RD.A_mesh                      # bulk oil velocity in the channel
    xd = u * RD.A_c / p.A_p
    x = np.concatenate([[0], np.cumsum(0.5 * (xd[1:] + xd[:-1]) * np.diff(t))])
    F = p.A_p * p.rho * p.l * G_amp * np.sin(w0 * t)
    a0.cla()
    a0.plot(t, u, color=RD.OIL, lw=1.6, label='oil velocity in channel [m/s]')
    a0.plot(t, F / F.max() * max(abs(u).max(), 1e-6) * 0.9, color=RD.STEEL, lw=1, ls='--', label='driving pressure (scaled)')
    a0.set_xlim(0, meta['end_time']); a0.set_xlabel('simulated time [s]'); a0.grid(alpha=0.3)
    a0.legend(fontsize=8, loc='upper left'); a0.set_title('Oil flow vs time')
    a2.cla()
    last = t > t[-1] - 1 / meta['freq']
    a2.plot((x[~last] - x.mean()) * 1e3, F[~last] / 1e3, color=RD.MUTED, lw=0.8, alpha=0.5)
    a2.plot((x[last] - x.mean()) * 1e3, F[last] / 1e3, color=RD.OIL, lw=2)
    a2.plot([(x[-1] - x.mean()) * 1e3], [F[-1] / 1e3], 'o', color=RD.OIL, mec=RD.INK, ms=8)
    a2.set_xlabel('piston displacement [mm]'); a2.set_ylabel('piston force [kN]'); a2.grid(alpha=0.3)
    a2.set_title('Force loop (orange = latest cycle)')
    snap, ts = latest_snapshot()
    if snap and snap != shown_snap:
        try:
            W, Ur, Uz = RD.read_section(snap)
            a1.cla()
            RD.section_axes(a1, W / max(abs(u).max(), 1e-6), Ur, Uz, 1.6, f'Cross-section at t = {ts:.4f} s')
            shown_snap = snap
        except (ValueError, OSError, IndexError):
            pass                                           # file still being written: try next refresh
    done = os.path.exists(os.path.join(win, 'log.pimpleFoam')) and 'End' in open(os.path.join(win, 'log.pimpleFoam')).read()[-200:]
    fig.suptitle(f'{CASE}: {meta["freq"]:g} Hz   |   simulated {t[-1]:.4f} of {meta["end_time"]:.2f} s   |   '
                 + ('FINISHED' if done else 'OpenFOAM running...'), fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    plt.pause(0.5 if not done else 2.0)
