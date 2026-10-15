"""Turn the recorded track-simulator results into presentation assets.

Inputs (written by the simulator through sim/tools/sim_server.py):
    sim/results/capture/track_comparison.json   3 vehicles x 4 tracks x 3 damper levels, full laps
    sim/results/capture/frames/<name>/frame_NNN.jpg   recorded animation frames
Outputs (sim/results/):
    track_comparison.csv                         every number, one row per vehicle/track/level/suspension
    chart_gain_by_track.png                      grip change vs conventional, by track, per vehicle
    chart_tradeoff.png                           grip change vs main damper kept: test road vs circuits
    chart_bumps_vs_body.png                      where the change comes from: bumps (>3 Hz) vs body (<3 Hz)
    chart_vehicle_dynamics.png                   max pitch / roll / heave per vehicle and track
    <name>.gif                                   animations from the frames
Usage: python make_presentation_assets.py
"""
import csv
import glob
import json
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
CAP = os.path.join(RES, 'capture')
VEH = {'supra': 'GR Supra (road)', 'gt4': 'GR Supra GT4 (race)', 'f150': 'Ford F-150'}
TRK = {'test': 'Test road', 'monza': 'Monza', 'spa': 'Spa', 'daytona': 'Daytona'}
COL = {'ideal': '#2c6496', 'cfd': '#c27a12', 'conventional': '#7b8996'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})


def gain(r, name, key='total'):
    conv = next(s for s in r['sus'] if s['name'] == 'conventional')[key]
    val = next(s for s in r['sus'] if s['name'] == name)[key]
    return 100 * (conv - val) / conv


def main():
    rows = json.load(open(os.path.join(CAP, 'track_comparison.json')))
    os.makedirs(RES, exist_ok=True)
    # ---- CSV
    with open(os.path.join(RES, 'track_comparison.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['vehicle', 'track', 'main_damper_kept_pct', 'suspension', 'tyre_load_fluct_total_pct', 'bumps_gt3Hz_pct',
                    'body_lt3Hz_pct', 'change_vs_conventional_pct', 'bumps_change_pct', 'body_change_pct', 'wheel_lifts',
                    'max_pitch_deg', 'max_roll_deg', 'max_heave_mm', 'max_wheel_load_ratio', 'simulated_s'])
        for r in rows:
            for s in r['sus']:
                w.writerow([VEH[r['vehicle']], TRK[r['track']], r['kept'], s['name'], s['total'], s['bumps'], s['body'],
                            round(gain(r, s['name']), 2), round(gain(r, s['name'], 'bumps'), 2), round(gain(r, s['name'], 'body'), 2),
                            s['wheel_lifts'], s['max_pitch_deg'], s['max_roll_deg'], s['max_heave_mm'], s['max_wheel_load_ratio'], r['seconds']])
    pick = lambda v, t, k: next(r for r in rows if r['vehicle'] == v and r['track'] == t and r['kept'] == k)

    # ---- chart 1: gain by track
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, v in zip(axs, VEH):
        x = np.arange(len(TRK))
        for j, (name, k, hatch) in enumerate([('ideal', 0, ''), ('cfd', 0, ''), ('ideal', 50, '//'), ('cfd', 50, '//')]):
            vals = [gain(pick(v, t, k), name) for t in TRK]
            ax.bar(x + (j - 1.5) * 0.2, vals, 0.19, color=COL[name], hatch=hatch, edgecolor='white',
                   label=f"{'Ideal' if name == 'ideal' else 'CFD'} J-damper, {k} % main damper")
        ax.axhline(0, color='k', lw=0.8)
        ax.set_xticks(x, TRK.values())
        ax.set_title(VEH[v], fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    axs[0].set_ylabel('Tyre-load fluctuation change vs conventional [%]\n(positive = steadier = more grip)')
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=9, loc='lower center', ncol=4, frameon=False)
    fig.suptitle('Grip effect of the J-damper on each track (full laps, full-car model)', fontsize=13, fontweight='bold')
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(os.path.join(RES, 'chart_gain_by_track.png'), dpi=160)
    plt.close(fig)

    # ---- chart 2: trade-off vs damper kept
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.4), sharey=True)
    for ax, v in zip(axs, VEH):
        for t, ls in (('test', '-'), ('monza', '--'), ('spa', ':'), ('daytona', '-.')):
            for name in ('ideal', 'cfd'):
                ks = [0, 50, 100]
                ax.plot(ks, [gain(pick(v, t, k), name) for k in ks], ls, marker='o', color=COL[name], lw=2 if t == 'test' else 1.3,
                        label=f"{TRK[t]} · {'ideal' if name == 'ideal' else 'CFD'}")
        ax.axhline(0, color='k', lw=0.8)
        ax.set_xticks([0, 50, 100], ['0 %\n(J-damper replaces\nmain damper)', '50 %', '100 %\n(J-damper added)'])
        ax.set_title(VEH[v], fontweight='bold')
        ax.grid(alpha=0.3)
    axs[0].set_ylabel('Change vs conventional [%]')
    axs[2].legend(fontsize=7, ncol=2, loc='lower right')
    fig.suptitle('Trade-off: how much normal damping to keep with the J-damper', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'chart_tradeoff.png'), dpi=160)
    plt.close(fig)

    # ---- chart 3: bumps vs body split (0 % kept)
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.4), sharey=True)
    for ax, v in zip(axs, VEH):
        x = np.arange(len(TRK))
        for j, (name, key, hatch) in enumerate([('ideal', 'bumps', ''), ('ideal', 'body', '..'), ('cfd', 'bumps', ''), ('cfd', 'body', '..')]):
            ax.bar(x + (j - 1.5) * 0.2, [gain(pick(v, t, 0), name, key) for t in TRK], 0.19, color=COL[name], hatch=hatch, edgecolor='white',
                   label=f"{'Ideal' if name == 'ideal' else 'CFD'}: {'bumps & wheel hop (>3 Hz)' if key == 'bumps' else 'body motion (<3 Hz)'}")
        ax.axhline(0, color='k', lw=0.8)
        ax.set_xticks(x, TRK.values())
        ax.set_title(VEH[v], fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    axs[0].set_ylabel('Change vs conventional [%]')
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=9, loc='lower center', ncol=4, frameon=False)
    fig.suptitle('Where the change comes from (J-damper replacing the main damper)', fontsize=13, fontweight='bold')
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(os.path.join(RES, 'chart_bumps_vs_body.png'), dpi=160)
    plt.close(fig)

    # ---- chart 4: vehicle dynamics
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.0))
    for ax, (key, lab) in zip(axs, [('max_pitch_deg', 'Max pitch [deg]'), ('max_roll_deg', 'Max roll [deg]'), ('max_heave_mm', 'Max body heave [mm]')]):
        x = np.arange(len(TRK) - 1)
        for j, v in enumerate(VEH):
            vals = [next(s for s in pick(v, t, 0)['sus'] if s['name'] == 'conventional')[key] for t in ('monza', 'spa', 'daytona')]
            ax.bar(x + (j - 1) * 0.26, vals, 0.25, label=VEH[v], color=['#9aa1a8', '#3a3f45', '#9b2230'][j])
        ax.set_xticks(x, ['Monza', 'Spa', 'Daytona'])
        ax.set_title(lab, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    axs[0].legend(fontsize=8)
    fig.suptitle('Vehicle dynamics on track (conventional suspension)', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(os.path.join(RES, 'chart_vehicle_dynamics.png'), dpi=160)
    plt.close(fig)

    # ---- GIFs from recorded frames
    for d in sorted(glob.glob(os.path.join(CAP, 'frames', '*'))):
        files = sorted(glob.glob(os.path.join(d, 'frame_*.jpg')))
        if not files:
            continue
        frames = [Image.open(f).convert('RGB') for f in files]
        w = 900
        frames = [f.resize((w, round(f.height * w / f.width)), Image.LANCZOS).convert('P', palette=Image.ADAPTIVE, colors=160) for f in frames]
        out = os.path.join(RES, os.path.basename(d) + '.gif')
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=70, loop=0, optimize=True)
        print(f'gif {os.path.basename(out)}: {len(frames)} frames, {os.path.getsize(out) / 1e6:.1f} MB')
    print('assets written to', RES)


if __name__ == '__main__':
    main()
