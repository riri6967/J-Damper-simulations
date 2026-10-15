"""Insert / refresh the 'Real cars on real tracks' section of project_page.template.html from
sim/results/capture/track_comparison.json, then rebuild project_page.html.
Usage: python sim/insert_track_section.py"""
import json
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
rows = json.load(open(os.path.join(ROOT, 'sim', 'results', 'capture', 'track_comparison.json')))
VEH = {'supra': 'Supra road', 'gt4': 'Supra GT4', 'f150': 'F-150'}
TRK = {'test': 'Test road', 'monza': 'Monza', 'spa': 'Spa', 'daytona': 'Daytona'}


def g(r, n):
    c = r['sus'][0]['total']
    v = next(s for s in r['sus'] if s['name'] == n)['total']
    return 100 * (c - v) / c


def pick(v, t, k):
    return next(r for r in rows if r['vehicle'] == v and r['track'] == t and r['kept'] == k)


trs = []
for v in VEH:
    for j, t in enumerate(TRK):
        a = [g(pick(v, t, k), 'ideal') for k in (0, 50)]
        b = [g(pick(v, t, k), 'cfd') for k in (0, 50)]
        best = 'cfd' if max(b) > max(a) else 'ideal'
        def cell(vals, key):
            cls = ' class="oil"' if best == key else ''
            return f'<td{cls}>{vals[0]:+.1f} / {vals[1]:+.1f}</td>'
        name = VEH[v] if j == 0 else ''
        trs.append(f'<tr><td>{name}</td><td>{TRK[t]}</td>{cell(a, "ideal")}{cell(b, "cfd")}</tr>')
table = '\n'.join(trs)

section = f'''<section id="tracks">
  <div class="sec-head"><span class="tag">Result 5 · Real cars on real tracks</span><h2>The trade-off on track</h2></div>
  <div class="two">
    <div class="prose">
      <p>A <b>full-car model</b> (body heave, pitch and roll, four wheels, anti-roll bars, bump stops, anti-dive) drives a <b>Toyota GR Supra</b> (road and GT4 race) and a <b>Ford F-150</b> around <b>Monza</b> and <b>Spa</b> (satellite-measured centrelines), the <b>Daytona</b> oval (31° banking) and a straight rough test road. Each lap runs three suspensions on the same road at once.</p>
      <p>On the <b>straight test road</b> every car reproduces the tuned gain (about +6–7 %). On <b>circuits</b>, braking and cornering transients excite body pitch and roll. Removing the main damper then costs grip, so <b>the J-damper is a trade-off between bump grip and body control</b>.</p>
      <p>The surprise: on the <b>soft road Supra and the F-150</b>, the real inerter's fluid damping <em>helps</em> on track (+4 to +7 %), often beating the ideal inerter. On the <b>stiff GT4</b>, the fluid losses at higher frequencies cancel most of the gain (+0 to +2 %).</p>
      <p><a class="play" href="https://claude.ai/artifact/7UrPWUneP5iQ4BjgckWrzH" style="display:inline-block;text-decoration:none" target="_blank" rel="noopener">Open the track simulator</a></p>
    </div>
    <div class="panel">
      <div class="panel-title">Change in tyre-load fluctuation vs conventional (full laps; + = more grip)</div>
      <div class="tbl" style="border:0;font-size:.85rem"><table>
        <thead><tr><th>Car</th><th>Track</th><th>Ideal<br>0 / 50 %</th><th>CFD<br>0 / 50 %</th></tr></thead>
        <tbody>{table}</tbody></table></div>
      <p class="muted" style="font-size:.8rem">0 / 50 % = share of the normal damper kept alongside the J-damper. Highlighted: the better inerter for that car and track. All numbers: <span class="mono">sim/results/track_comparison.csv</span>.</p>
    </div>
  </div>
  <div class="tbl wrap-cells">
    <table>
      <thead><tr><th></th><th>Conventional</th><th>Ideal J-damper</th><th>CFD J-damper (real fluid inerter)</th></tr></thead>
      <tbody>
        <tr><td>What it is</td><td>Spring + damper</td><td>+ spring–damper–perfect-inerter branch (F = b·ẍ)</td><td>Same branch; inerter as measured by CFD (inertance 1.02–1.26 × ideal + parasitic damping)</td></tr>
        <tr><td>Bumps &amp; wheel hop (&gt; 3 Hz)</td><td>Baseline</td><td>Better (up to +7 %)</td><td>Better on soft cars (up to +9 %); little gain on the stiff GT4</td></tr>
        <tr><td>Body motion (&lt; 3 Hz)</td><td>Best controlled</td><td>Worse if the main damper is removed (Supra at Spa −7 %)</td><td>Fluid damping keeps body control (Supra +1 to +3 %)</td></tr>
        <tr><td>Best on</td><td>Body control, simplicity</td><td>Stiff race car (GT4) on circuits</td><td>Soft road car (Supra) and heavy pickup (F-150)</td></tr>
        <tr><td>Kerb strikes</td><td colspan="3">Same for all three: the inerter cannot stop a wheel lifting over a kerb</td></tr>
      </tbody>
    </table>
  </div>
  <div class="gallery">
    <figure><img src="sim/results/gt4_spa_eau_rouge.gif" alt="GR Supra GT4 through Eau Rouge at Spa" loading="lazy"><figcaption><b>GT4 through Eau Rouge.</b> +1.0 g compression at 227 km/h: all four tyres carry 160–230 % of their static load.</figcaption></figure>
    <figure><img src="sim/results/f150_monza_braking.gif" alt="Ford F-150 braking at Monza" loading="lazy"><figcaption><b>F-150 braking at 0.94 g.</b> Weight shifts forward, the nose dives and the rear unloads.</figcaption></figure>
    <figure><img src="sim/results/supra_testroad_cfd.gif" alt="GR Supra on the rough test road" loading="lazy"><figcaption><b>Supra on the rough test road.</b> CFD J-damper about 7 % steadier. The bottom strip shows its tyre load minus the conventional car's.</figcaption></figure>
    <figure><img src="sim/results/supra_monza_kerb.gif" alt="GR Supra over a Monza kerb" loading="lazy"><figcaption><b>Supra over a Monza chicane kerb</b> (slow motion). Kerb strikes look the same for all three suspensions.</figcaption></figure>
    <figure><img src="sim/results/gt4_daytona_banking.gif" alt="GT4 on Daytona banking" loading="lazy"><figcaption><b>GT4 entering Daytona's 31° banking</b> flat out: the banking adds about +0.7 g of vertical load.</figcaption></figure>
    <figure><img src="sim/results/chart_gain_by_track.png" alt="Grip change by track" loading="lazy"><figcaption><b>Grip change by track</b> for each car, J-damper replacing (0 %) or sharing (50 %) the main damper.</figcaption></figure>
    <figure><img src="sim/results/chart_bumps_vs_body.png" alt="Bumps vs body split" loading="lazy"><figcaption><b>Where the change comes from.</b> Bumps (&gt; 3 Hz) vs body motion (&lt; 3 Hz).</figcaption></figure>
    <figure><img src="sim/results/chart_tradeoff.png" alt="Trade-off vs damper kept" loading="lazy"><figcaption><b>The trade-off.</b> Grip change vs how much of the normal damper is kept, test road vs circuits.</figcaption></figure>
  </div>
</section>

'''
p = os.path.join(ROOT, 'project_page.template.html')
t = open(p, encoding='utf-8').read()
t = re.sub(r'<section id="tracks">.*?</section>\n\n', '', t, flags=re.S)        # refresh if already present
marker = '<section>\n  <div class="sec-head"><span class="tag">Interactive</span>'
assert marker in t, 'marker not found'
t = t.replace(marker, section + marker, 1)
t = t.replace("<li><b>Quarter-car only</b>A full-vehicle model with heave and roll, plus lap-time simulation, would follow.</li>",
              "<li><b>Track simulator scope</b>Vertical tyre model only; quasi-steady lap profile; spring rates from owner forums; CoG, anti-roll bars and aero estimated.</li>")
open(p, 'w', encoding='utf-8').write(t)
print('section inserted into project_page.template.html')
# rebuild the page if the page data is given:  python sim/insert_track_section.py pagedata.json
import sys
if len(sys.argv) > 1:
    data = open(sys.argv[1], encoding='utf-8').read().replace('</', '<\\/')
    open(os.path.join(ROOT, 'project_page.html'), 'w', encoding='utf-8').write(t.replace('__DATA__', data))
    print('project_page.html rebuilt')
