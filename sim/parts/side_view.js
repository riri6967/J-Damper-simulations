  // ---------------- car artwork: side views in metres (x forward from the CoG, y up from the ground)
  function arch(cx, cy, r) { const p = []; for (let k = 0; k <= 16; k++) { const a = Math.PI * (1 - k / 16); p.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } return p; }
  function outline(top, aF, aR, R, rA, sill, rearBottom, frontBottom) {
    // sill -> down into the rear arch -> over the rear wheel -> back down to the sill -> along the sill -> front arch -> sill
    return [...top, ...rearBottom, [aR - rA - 0.02, sill], [aR - rA, R], ...arch(aR, R, rA), [aR + rA, R], [aR + rA + 0.02, sill],
            [aF - rA - 0.02, sill], [aF - rA, R], ...arch(aF, R, rA), [aF + rA, R], [aF + rA + 0.02, sill], ...frontBottom];
  }
  const ART = {
    supra: () => ft1Art(false),
    gt4: () => ft1Art(true),
    f150: () => {
      const R = V.wheelR, aF = V.a, aR = -V.b;
      return { R, rimRatio: 0.61, spokes: 6, rimC: '#1f2226', rimHi: '#9aa2aa', caliper: '#4a4f55', tread: true,
        body: outline([[2.5, .44], [2.57, .55], [2.58, .8], [2.56, 1.18], [2.4, 1.28], [1.7, 1.33], [1.05, 1.41], [.56, 1.93], [-.95, 1.96], [-1.08, 1.87],
                       [-1.1, 1.45], [-1.12, 1.41], [-3.33, 1.41], [-3.35, .62]], aF, aR, R, .56, .58, [[-3.3, .46]], [[2.4, .46]]),
        glass: [[[1.0, 1.44], [.57, 1.88], [.02, 1.89], [.02, 1.44]], [[-.06, 1.44], [-.06, 1.89], [-.92, 1.88], [-.99, 1.46]]],
        darks: [[[2.585, 1.15], [2.585, .8], [2.42, .82], [2.42, 1.12]], [[2.6, .8], [2.42, .8], [2.42, .44], [2.56, .45]], [[-3.38, .68], [-3.04, .68], [-3.04, .5], [-3.38, .52]],
                [[.95, .6], [-.95, .6], [-.95, .54], [.95, .54]], [[1.12, 1.52], [.96, 1.6], [.88, 1.55], [1.02, 1.46]],
                [[-.02, 1.89], [.02, 1.89], [.02, 1.44], [-.02, 1.44]]],
        accents: [[[-1.2, 1.25], [-3.2, 1.25], [-3.2, 1.31], [-1.2, 1.31]]],
        lights: [[[2.56, 1.22], [2.3, 1.27], [2.28, 1.16], [2.54, 1.14]]], tails: [[[-3.345, 1.39], [-3.26, 1.39], [-3.26, 1.04], [-3.345, 1.04]]],
        lines: [[[1.0, 1.44], [1.0, .66]], [[.02, 1.44], [.0, .66]], [[-.99, 1.46], [-.99, .66]], [[-3.28, 1.4], [-3.28, .66]], [[.55, 1.12], [.68, 1.12]], [[-.45, 1.12], [-.32, 1.12]]],
        flares: true, bodyTop: '#b3263a', bodyBot: '#5e0f1a', stroke: '#2a0c11' };
    },
  };

  function coil(c, x0, y0, x1, y1, w, turns, color, lw) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
    c.beginPath(); c.moveTo(x0, y0);
    for (let i = 1; i < turns * 2; i++) { const f = .1 + .8 * i / (turns * 2), s = i % 2 ? w : -w; c.lineTo(x0 + dx * f + nx * s, y0 + dy * f + ny * s); }
    c.lineTo(x1, y1); c.strokeStyle = color; c.lineWidth = lw; c.stroke();
  }

  // smooth closed path through points (quadratic midpoints): rounded panels instead of facets
  function smoothPath(c, pts, P) {
    const q = pts.map(([x, y]) => P(x, y)), n = q.length;
    const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    c.beginPath(); const m0 = mid(q[n - 1], q[0]); c.moveTo(m0[0], m0[1]);
    for (let i = 0; i < n; i++) { const m = mid(q[i], q[(i + 1) % n]); c.quadraticCurveTo(q[i][0], q[i][1], m[0], m[1]); }
    c.closePath();
  }
  function polyPath(c, pts, P) { c.beginPath(); pts.forEach(([x, y], k) => { const [X, Y] = P(x, y); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }); c.closePath(); }

  function drawBody(c, A, P, ghost) {
    if (ghost) { smoothPath(c, A.body, P); c.setLineDash([3, 5]); c.globalAlpha = .45; c.strokeStyle = css('--c-conv'); c.lineWidth = 1; c.stroke(); c.globalAlpha = 1; c.setLineDash([]); return; }
    if (A.style === 'ft1') { drawFT1(c, A, P); return; }
    const yTop = P(0, 2.0)[1], yBot = P(0, 0.1)[1];
    const g = c.createLinearGradient(0, yTop, 0, yBot); g.addColorStop(0, A.bodyTop); g.addColorStop(0.55, A.bodyTop); g.addColorStop(1, A.bodyBot);
    smoothPath(c, A.body, P); c.fillStyle = g; c.fill(); c.strokeStyle = A.stroke; c.lineWidth = 1.2; c.stroke();
    // shoulder highlight
    c.save(); smoothPath(c, A.body, P); c.clip();
    const ySh = P(0, V.h + 0.35)[1], hl = c.createLinearGradient(0, ySh - 14, 0, ySh + 14);
    hl.addColorStop(0, 'rgba(255,255,255,0)'); hl.addColorStop(.5, 'rgba(255,255,255,.22)'); hl.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = hl; c.fillRect(-2000, ySh - 14, 4000, 28); c.restore();
    for (const w of A.glass) {
      const gg = c.createLinearGradient(0, P(0, 1.9)[1], 0, P(0, .85)[1]);
      gg.addColorStop(0, '#1c2a35'); gg.addColorStop(1, '#3d5566'); polyPath(c, w, P); c.fillStyle = gg; c.fill();
      c.save(); polyPath(c, w, P); c.clip(); c.strokeStyle = 'rgba(255,255,255,.18)'; c.lineWidth = 6;
      const [x0, y0] = P(w[0][0], w[0][1]); c.beginPath(); c.moveTo(x0 - 40, y0); c.lineTo(x0 + 10, y0 - 70); c.stroke(); c.restore();
    }
    for (const d of A.darks) { polyPath(c, d, P); c.fillStyle = '#1d2024'; c.fill(); }
    for (const a of A.accents) { polyPath(c, a, P); c.fillStyle = '#121417'; c.fill(); }
    for (const l of A.lights) { polyPath(c, l, P); c.fillStyle = '#eaf4fb'; c.shadowColor = '#cfe8ff'; c.shadowBlur = 8; c.fill(); c.shadowBlur = 0; }
    for (const l of A.tails) { polyPath(c, l, P); c.fillStyle = '#d31f2b'; c.fill(); }
    c.strokeStyle = 'rgba(0,0,0,.45)'; c.lineWidth = 1;
    for (const [[x0, y0], [x1, y1]] of A.lines) { c.beginPath(); c.moveTo(...P(x0, y0)); c.lineTo(...P(x1, y1)); c.stroke(); }
    if (vk === 'f150') {                                  // grille bars
      c.strokeStyle = 'rgba(255,255,255,.35)'; c.lineWidth = 2;
      for (let k = 0; k < 4; k++) { const [x0, y0] = P(2.585, .86 + k * .075), x1 = P(2.43, 0)[0]; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y0); c.stroke(); }
    }
    if (A.flares) for (const ax of [V.a, -V.b]) {        // black fender flares
      c.beginPath();
      for (let k = 0; k <= 16; k++) { const a = Math.PI * (1 - k / 16), [X, Y] = P(ax + (A.R + .16) * Math.cos(a), A.R + (A.R + .16) * Math.sin(a)); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }
      c.strokeStyle = '#141619'; c.lineWidth = 7; c.stroke();
    }
  }

  function drawWheel(c, A, X, Y, Rp, rot, squash, ghost) {
    if (ghost) { c.setLineDash([3, 5]); c.globalAlpha = .45; c.strokeStyle = css('--c-conv'); c.lineWidth = 1; c.beginPath(); c.arc(X, Y, Rp, 0, 2 * Math.PI); c.stroke(); c.globalAlpha = 1; c.setLineDash([]); return; }
    c.save(); c.translate(X, Y + squash / 2); c.scale(1 + squash / Rp * .25, 1 - squash / Rp * .5);
    c.fillStyle = '#16181b'; c.beginPath(); c.arc(0, 0, Rp, 0, 2 * Math.PI); c.fill();
    if (A.tread) { c.fillStyle = '#2c3035'; for (let k = 0; k < 28; k++) { c.save(); c.rotate(rot + k * 2 * Math.PI / 28); c.fillRect(Rp - 5, -4, 6, 8); c.restore(); } }
    c.strokeStyle = '#2b2f34'; c.lineWidth = 2; c.beginPath(); c.arc(0, 0, Rp * .9, 0, 2 * Math.PI); c.stroke();
    if (A.slick || A.style === 'ft1') { c.strokeStyle = 'rgba(255,255,255,.12)'; c.lineWidth = 3; c.beginPath(); c.arc(0, 0, Rp * .86, -2.6, -1.2); c.stroke(); }
    c.restore();
    const rr = Rp * A.rimRatio;
    c.fillStyle = '#6b7178'; c.beginPath(); c.arc(X, Y, rr * .78, 0, 2 * Math.PI); c.fill();                 // brake disc
    c.fillStyle = A.caliper; c.beginPath(); c.arc(X, Y, rr * .84, -2.3, -1.4); c.arc(X, Y, rr * .55, -1.4, -2.3, true); c.closePath(); c.fill();
    const rg = c.createRadialGradient(X - rr * .3, Y - rr * .3, rr * .1, X, Y, rr);
    rg.addColorStop(0, A.rimHi); rg.addColorStop(1, A.rimC);
    c.strokeStyle = rg; c.lineCap = 'round';
    for (let k = 0; k < A.spokes; k++) {
      const a = rot + k * 2 * Math.PI / A.spokes; c.lineWidth = A.turbine ? 2.4 : A.spokes > 6 ? 3 : 6;
      c.beginPath(); c.moveTo(X + Math.cos(a) * rr * .2, Y + Math.sin(a) * rr * .2);
      if (A.turbine) { const am = a + .35; c.quadraticCurveTo(X + Math.cos(am) * rr * .62, Y + Math.sin(am) * rr * .62, X + Math.cos(a + .55) * rr * .95, Y + Math.sin(a + .55) * rr * .95); }
      else c.lineTo(X + Math.cos(a) * rr * .95, Y + Math.sin(a) * rr * .95);
      c.stroke();
    }
    c.lineCap = 'butt';
    c.lineWidth = Math.max(3, rr * .1); c.beginPath(); c.arc(X, Y, rr * .96, 0, 2 * Math.PI); c.stroke();
    c.fillStyle = A.rimHi; c.beginPath(); c.arc(X, Y, rr * .17, 0, 2 * Math.PI); c.fill();
  }

  function drawSide(inp) {
    const [c, W, H] = fit($('cv-side'));
    const car = cars[sel], A = ART[vk]();
    c.clearRect(0, 0, W, H);
    const carLen = vk === 'f150' ? 5.95 : 4.75, px = Math.min(W * 0.66 / carLen, (H - 90) / 2.1), groundY = H - 46, cx = W * 0.47;
    const z0 = trackInterp(T.z, sDist);
    const roadY = xm => groundY - ((trackInterp(T.z, sDist + xm) - z0) * px) - roadL(sDist + xm) * mag * px - kerbAt(sDist + xm, 1) * mag * px;
    const sky = c.createLinearGradient(0, 0, 0, groundY); sky.addColorStop(0, css('--sky')); sky.addColorStop(1, css('--surface'));
    c.fillStyle = sky; c.fillRect(0, 0, W, H);
    c.beginPath(); c.moveTo(0, H); for (let X = 0; X <= W; X += 4) c.lineTo(X, roadY((X - cx) / px)); c.lineTo(W, H); c.closePath(); c.fillStyle = css('--grid'); c.fill();
    c.beginPath(); for (let X = 0; X <= W; X += 4) { const yy = roadY((X - cx) / px); X ? c.lineTo(X, yy) : c.moveTo(X, yy); } c.strokeStyle = css('--road'); c.lineWidth = 3; c.stroke();
    for (const [ks, side] of T.kerbs) {
      if (side !== 1) continue; let dxm = ks - sDist; if (dxm < -T.L / 2) dxm += T.L; if (Math.abs(dxm) > W / px) continue;
      const X = cx + dxm * px; for (let k = -3; k < 3; k++) { c.fillStyle = k % 2 ? '#c0392b' : '#f2f2f2'; c.fillRect(X + k * KERB_LEN / 6 * px, roadY(dxm) - 3, KERB_LEN / 6 * px, 4); }
    }
    c.fillStyle = css('--muted'); c.font = '10px ' + css('--f-mono');
    for (let m = Math.ceil((sDist - cx / px) / 10) * 10; m < sDist + (W - cx) / px; m += 10) { const X = cx + (m - sDist) * px; c.fillRect(X, H - 18, 1, 5); if (m % 50 === 0) c.fillText(((m % T.L + T.L) % T.L).toFixed(0) + ' m', X + 3, H - 6); }
    const slope = Math.atan((trackInterp(T.z, sDist + 1) - trackInterp(T.z, sDist - 1)) / 2);
    c.save(); c.translate(cx, groundY); c.rotate(-slope);
    const P = (xm, ym) => [xm * px, -ym * px];
    const sh = c.createRadialGradient(0, 0, 10, 0, 0, carLen * px * .55); sh.addColorStop(0, 'rgba(0,0,0,.35)'); sh.addColorStop(1, 'rgba(0,0,0,0)');
    c.save(); c.scale(1, .12); c.fillStyle = sh; c.beginPath(); c.arc(0, 0, carLen * px * .55, 0, 2 * Math.PI); c.fill(); c.restore();
    const hY = P(0, V.h)[1];
    const pose = cc => {
      const yy = cc.y, bz = yy[0] * mag, bth = yy[1] * Math.min(mag, 1.5);   // pitch kept near true scale (max x1.5)
      const toW = (X, Y) => { const dy = Y - hY; return [X * Math.cos(-bth) - dy * Math.sin(-bth), X * Math.sin(-bth) + dy * Math.cos(-bth) + hY - bz * px]; };
      return { bz, bth, toW, hubs: [[V.a, 0], [-V.b, 2]].map(([xm, i]) => { const [X, Y] = P(xm, A.R + yy[6 + i] * mag); return [X, Y, i]; }) };
    };
    const drawCarAt = (cc, ghost) => {
      const ps = pose(cc);
      c.save(); c.translate(0, -ps.bz * px); c.translate(0, hY); c.rotate(-ps.bth); c.translate(0, -hY);
      drawBody(c, A, P, ghost);
      c.restore();
      for (const [X, Y, i] of ps.hubs) drawWheel(c, A, X, Y, A.R * px, sDist / A.R, ghost ? 0 : Math.max(0, (inp.zr[i] - cc.y[6 + i]) * mag * px), ghost);
      return ps;
    };
    c.save(); c.scale(1, -1); c.globalAlpha = .12; { const ps0 = pose(car); c.translate(0, ps0.bz * px); c.translate(0, hY); c.rotate(ps0.bth); c.translate(0, -hY); drawBody(c, A, P, false); } c.restore();
    c.fillStyle = 'rgba(0,0,0,.5)'; for (const xm of [V.a, -V.b]) { c.beginPath(); c.ellipse(xm * px, 0, A.R * px * .9, 4, 0, 0, 2 * Math.PI); c.fill(); }
    const ps = drawCarAt(car, false);
    if (sel !== 0) drawCarAt(cars[0], true);                 // ghost: conventional car on the same road
    c.globalAlpha = .85;                                     // x-ray suspension: slim and translucent
    for (const [hx, hy, i] of ps.hubs) {
      const [mx, my] = ps.toW(...P(i === 0 ? V.a : -V.b, A.R + (vk === 'f150' ? .62 : .45)));
      coil(c, hx - 5, hy - A.R * px * .25, mx - 5, my, 4, 7, '#f1f4f7', 1.6);
      if (car.br[i]) {
        const col = css(SUS[sel].color), ym = (hy + my) / 2;
        c.strokeStyle = col; c.lineWidth = 2; c.beginPath(); c.moveTo(hx + 6, hy - A.R * px * .25); c.lineTo(mx + 6, my); c.stroke();
        // inerter shown as a flywheel that spins with the inerter stroke (oil column moving through the helix)
        const fx = hx + 6, ang = car.y[14 + 3 * i] * 400, rr = 8;
        c.fillStyle = css('--surface'); c.beginPath(); c.arc(fx, ym, rr, 0, 2 * Math.PI); c.fill(); c.lineWidth = 2; c.stroke();
        c.lineWidth = 2; for (const k of [0, 2.09, 4.19]) { c.beginPath(); c.moveTo(fx, ym); c.lineTo(fx + Math.cos(ang + k) * rr, ym + Math.sin(ang + k) * rr); c.stroke(); }
      }
    }
    c.globalAlpha = 1;
    const [gx, gy] = ps.toW(...P(0, V.h)), axr = -inp.ax / G * 60;
    if (Math.abs(axr) > 2) {
      c.strokeStyle = css('--hot'); c.fillStyle = css('--hot'); c.lineWidth = 3; c.beginPath(); c.moveTo(gx, gy); c.lineTo(gx + axr, gy); c.stroke();
      c.beginPath(); c.moveTo(gx + axr, gy); c.lineTo(gx + axr - Math.sign(axr) * 8, gy - 5); c.lineTo(gx + axr - Math.sign(axr) * 8, gy + 5); c.fill();
    }
    c.fillStyle = '#fff'; c.beginPath(); c.arc(gx, gy, 8, 0, 2 * Math.PI); c.fill();
    c.fillStyle = '#111'; c.beginPath(); c.moveTo(gx, gy); c.arc(gx, gy, 8, 0, Math.PI / 2); c.lineTo(gx, gy); c.arc(gx, gy, 8, Math.PI, 1.5 * Math.PI); c.fill();
    c.strokeStyle = '#111'; c.lineWidth = 1; c.beginPath(); c.arc(gx, gy, 8, 0, 2 * Math.PI); c.stroke();
    for (const [hx, , i] of ps.hubs) {
      const dl = (car.load[i] - car.stat[i]) / car.stat[i], hgt = Math.max(-1, Math.min(1.5, dl)) * 40;
      c.fillStyle = dl >= 0 ? css('--hot') : css('--steel'); c.fillRect(hx + A.R * px + 6, -2 - Math.max(0, hgt), 7, Math.abs(hgt));
      c.fillStyle = css('--ink'); c.font = '10px ' + css('--f-mono'); c.fillText((dl >= 0 ? '+' : '') + (100 * dl).toFixed(0) + '%', hx + A.R * px + 15, -4);
    }
    c.restore();
    c.fillStyle = css('--ink'); c.font = '700 26px ' + css('--f-display'); c.fillText(`${(inp.v * 3.6).toFixed(0)} km/h`, 10, 46);
    c.font = '11px ' + css('--f-mono'); c.fillStyle = css('--muted');
    const gx2 = inp.ax / G, gy2 = inp.ay / G, gz2 = inp.az / G;
    c.fillText(`${gx2 >= 0 ? 'accel' : 'brake'} ${Math.abs(gx2).toFixed(2)} g   lateral ${Math.abs(gy2).toFixed(2)} g ${gy2 > .05 ? '(left)' : gy2 < -.05 ? '(right)' : ''}   vertical ${gz2 >= 0 ? '+' : ''}${gz2.toFixed(2)} g`, 10, 63);
    const bk = trackInterp(T.bank, sDist);
    c.fillText(`lap ${lapCount + 1} · ${fmtT(lapT % T.lap.lap_time)} · ${sDist.toFixed(0)} m${bk > 1 ? ` · banking ${bk.toFixed(0)}°` : ''}`, 10, 78);
    if (car.br[0]) {                                        // live front inerter readout
      const b = car.br[0], yv = car.y, d = yv[0] + V.a * yv[1] + (V.track / 2) * yv[2] - yv[6], Fb = b.k2 * (d - yv[14] - yv[16]);
      c.fillStyle = css(SUS[sel].color); c.font = '11px ' + css('--f-mono');
      c.fillText(`front inerter: ${(Fb / 1000).toFixed(2)} kN · oil ${Math.abs(yv[15] * 44.4).toFixed(2)} m/s · b ${b.b.toFixed(0)} kg`, 10, 93);
    }
    if (kerbFlash > 0) { c.fillStyle = css('--hot'); c.font = '700 18px ' + css('--f-display'); c.fillText('KERB STRIKE', W - 120, 46); }
    if (car.load.some(l => l <= 1)) { c.fillStyle = css('--hot'); c.font = '700 18px ' + css('--f-display'); c.fillText('WHEEL OFF THE GROUND', W - 200, 68); }
    c.fillStyle = css('--muted'); c.font = '10px ' + css('--f-mono'); c.textAlign = 'right';
    c.fillText(`vertical motion ×${mag}, pitch ×${Math.min(mag, 1.5)}${sel ? ' · dashed = conventional car' : ''} · ⊗ CoG · red arrow = weight shift`, W - 8, H - 26); c.textAlign = 'left';
    $('lbl-side').textContent = `Side view · ${V.name} · ${SUS[sel].name}${sel ? ` (${KEPT[lvl]} % main damper)` : ''}`;
  }

