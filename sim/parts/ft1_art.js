  // ---------------- FT-1-style Supra artwork (side profile, metres from the CoG; y up from the ground)
  // Sculpted long hood, low nose with deep intakes, LED slit headlight, double-bubble roof, big side scoop,
  // muscular rear haunch, swan-neck wing; liquid-metal paint. race = GT4 kit (splitter, diffuser, slicks, livery).
  function ft1Art(race) {
    const R = V.wheelR, aF = V.a, aR = -V.b, rA = 0.405, sill = race ? 0.15 : 0.17;
    const top = [[2.27, .2], [2.31, .29], [2.28, .39], [2.16, .47], [1.98, .53], [1.78, .6], [1.52, .67], [1.22, .71], [.86, .76], [.52, .81], [.3, .85],
                 [.05, 1.04], [-.22, 1.22], [-.42, 1.27], [-.6, 1.26], [-.8, 1.24], [-1.08, 1.12], [-1.38, 1.0], [-1.62, .96], [-1.84, .95], [-2.02, .91],
                 [-2.14, .935], [-2.2, .88], [-2.235, .74], [-2.22, .58], [-2.17, .42]];
    return { style: 'ft1', race, R, rimRatio: 0.74, spokes: 14, turbine: true, rimC: race ? '#2b2f34' : '#5a6169', rimHi: race ? '#9aa1a8' : '#e4e8ec',
      caliper: race ? '#d4151f' : '#c8102e', tread: false, slick: race,
      body: outline(top, aF, aR, R, rA, sill, [[-2.08, .26], [-1.98, .2]], [[2.2, .15]]),
      glass: [[.27, .88], [.03, 1.05], [-.22, 1.2], [-.42, 1.245], [-.6, 1.235], [-.8, 1.21], [-1.06, 1.1], [-1.2, 1.02], [-.92, .95], [-.2, .9]],
      scoop: [[-.12, .64], [-.48, .76], [-.9, .82], [-1.24, .76], [-1.42, .6], [-1.36, .47], [-1.05, .42], [-.55, .43], [-.22, .5]],
      noseIntake: [[2.3, .37], [2.15, .42], [2.03, .36], [2.04, .27], [2.28, .25]],
      lowerIntake: [[2.22, .22], [1.98, .24], [1.9, .19], [2.18, .17]],
      head: [[2.19, .48], [1.98, .54], [1.84, .565], [1.83, .55], [1.96, .515], [2.16, .46]],
      tail: [[-2.21, .885], [-2.02, .925], [-2.0, .9], [-2.2, .862]],
      mirror: [[.36, .93], [.14, .99], [.06, .96], [.12, .91], [.3, .9]],
      char: [[1.64, .61], [1.1, .6], [.55, .62], [.05, .64]], haunch: [[-.85, .9], [-1.3, .96], [-1.7, .955], [-2.0, .92]],
      wing: race ? { plane: [[-2.47, 1.3], [-1.82, 1.33], [-1.83, 1.24], [-2.47, 1.22]], stalk: -2.0, deck: .95, end: [[-2.48, 1.36], [-2.42, 1.36], [-2.42, 1.12], [-2.48, 1.12]] }
                 : { plane: [[-2.32, 1.2], [-1.9, 1.22], [-1.91, 1.165], [-2.32, 1.15]], stalk: -2.04, deck: .94, end: null },
      splitter: race ? [[2.42, .12], [1.62, .12], [1.62, .15], [2.36, .16]] : null,
      diffuser: race ? [[-2.12, .21], [-2.36, .27], [-2.36, .31], [-2.12, .27]] : null,
      bodyTop: '#f2f5f7', bodyMid: '#a9b2ba', bodyHorizon: '#59626b', bodyLow: '#cfd6dc', bodyBot: '#3a4148', stroke: '#24292e' };
  }

  function drawFT1(c, A, P) {
    const yRoof = P(0, 1.3)[1], yGround = P(0, .12)[1];
    // liquid-metal paint: sky / horizon / ground reflections
    const g = c.createLinearGradient(0, yRoof, 0, yGround);
    g.addColorStop(0, A.bodyTop); g.addColorStop(.36, A.bodyMid); g.addColorStop(.5, A.bodyHorizon);
    g.addColorStop(.56, A.bodyLow); g.addColorStop(.8, '#8a939b'); g.addColorStop(1, A.bodyBot);
    smoothPath(c, A.body, P); c.fillStyle = g; c.fill();
    c.save(); smoothPath(c, A.body, P); c.clip();
    // specular highlights on the front fender and the rear haunch
    for (const [x, y, r] of [[1.25, .72, .55], [-1.45, .98, .6]]) {
      const [X, Y] = P(x, y), rg = c.createRadialGradient(X, Y, 2, X, Y, r * Math.abs(P(1, 0)[0]));
      rg.addColorStop(0, 'rgba(255,255,255,.55)'); rg.addColorStop(1, 'rgba(255,255,255,0)'); c.fillStyle = rg; c.fillRect(X - 400, Y - 400, 800, 800);
    }
    // sculpted flank: soft shadow band under the character line, light catch along the sill
    const fy0 = P(0, .6)[1], fy1 = P(0, .3)[1], fl = c.createLinearGradient(0, fy0, 0, fy1);
    fl.addColorStop(0, 'rgba(20,24,28,0)'); fl.addColorStop(.35, 'rgba(20,24,28,.28)'); fl.addColorStop(1, 'rgba(20,24,28,.05)');
    c.fillStyle = fl; c.fillRect(-2000, fy0, 4000, fy1 - fy0);
    const sy = P(0, .22)[1]; c.fillStyle = 'rgba(255,255,255,.18)'; c.fillRect(-2000, sy - 2, 4000, 2);
    // race livery: graphite lower body with a red pin-line, race number roundel
    if (A.race) {
      polyPath(c, [[2.4, .1], [2.4, .36], [1.6, .4], [.6, .44], [-.3, .4], [-1.4, .36], [-2.4, .44], [-2.4, .1]], P); c.fillStyle = 'rgba(22,24,28,.88)'; c.fill();
      c.strokeStyle = '#d4151f'; c.lineWidth = 2.5; c.beginPath(); [[2.4, .37], [1.6, .41], [.6, .45], [-.3, .41], [-1.4, .37], [-2.4, .45]].forEach(([x, y], k) => { const [X, Y] = P(x, y); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }); c.stroke();
    }
    c.restore();
    smoothPath(c, A.body, P); c.strokeStyle = A.stroke; c.lineWidth = 1.1; c.stroke();
    // side scoop: deep sculpted intake behind the door
    const [sx0, sy0] = P(-.3, .82), [sx1, sy1] = P(-1.0, .42);
    const sg = c.createLinearGradient(sx0, sy0, sx1, sy1); sg.addColorStop(0, '#2e353c'); sg.addColorStop(.6, '#0f1215'); sg.addColorStop(1, '#22282e');
    smoothPath(c, A.scoop, P); c.fillStyle = sg; c.fill();
    c.strokeStyle = 'rgba(255,255,255,.55)'; c.lineWidth = 1.4; c.beginPath(); A.scoop.slice(0, 5).forEach(([x, y], k) => { const [X, Y] = P(x, y + .012); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }); c.stroke();
    // glass with reflection streaks
    const gg = c.createLinearGradient(0, P(0, 1.25)[1], 0, P(0, .88)[1]); gg.addColorStop(0, '#0e161d'); gg.addColorStop(1, '#2f4555');
    smoothPath(c, A.glass, P); c.fillStyle = gg; c.fill();
    c.save(); smoothPath(c, A.glass, P); c.clip(); c.strokeStyle = 'rgba(220,235,245,.22)';
    for (const [x, w] of [[-.15, 7], [-.5, 3]]) { const [X, Y] = P(x, .88); c.lineWidth = w; c.beginPath(); c.moveTo(X, Y); c.lineTo(X + 45, Y - 60); c.stroke(); }
    c.restore();
    // character lines
    c.lineCap = 'round';
    for (const [line, a] of [[A.char, .7], [A.haunch, .6]]) { c.strokeStyle = `rgba(255,255,255,${a})`; c.lineWidth = 1.6; c.beginPath(); line.forEach(([x, y], k) => { const [X, Y] = P(x, y); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }); c.stroke();
      c.strokeStyle = 'rgba(0,0,0,.35)'; c.lineWidth = 1; c.beginPath(); line.forEach(([x, y], k) => { const [X, Y] = P(x, y - .02); k ? c.lineTo(X, Y) : c.moveTo(X, Y); }); c.stroke(); }
    c.lineCap = 'butt';
    // door shut line
    c.strokeStyle = 'rgba(0,0,0,.4)'; c.lineWidth = 1; c.beginPath(); c.moveTo(...P(.24, .86)); c.quadraticCurveTo(...P(.3, .5), ...P(.22, .2)); c.stroke();
    // nose: deep intakes, LED headlight slit with glow
    for (const pts of [A.noseIntake, A.lowerIntake]) { polyPath(c, pts, P); c.fillStyle = '#0c0e10'; c.fill(); }
    c.strokeStyle = 'rgba(160,170,180,.5)'; c.lineWidth = 1; for (let k = 1; k < 4; k++) { const [x0, y0] = P(2.27, .26 + k * .035), [x1] = P(2.06, 0); c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y0); c.stroke(); }
    polyPath(c, A.head, P); c.fillStyle = '#ffffff'; c.shadowColor = '#bfe3ff'; c.shadowBlur = 14; c.fill(); c.shadowBlur = 0;
    polyPath(c, A.tail, P); c.fillStyle = '#ff2a33'; c.shadowColor = '#ff2a33'; c.shadowBlur = 10; c.fill(); c.shadowBlur = 0;
    polyPath(c, A.mirror, P); c.fillStyle = '#1b1f23'; c.fill();
    // aero
    if (A.splitter) { polyPath(c, A.splitter, P); c.fillStyle = '#121416'; c.fill(); }
    if (A.diffuser) { polyPath(c, A.diffuser, P); c.fillStyle = '#121416'; c.fill(); }
    const W_ = A.wing, [stx, sty] = P(W_.stalk, W_.deck), [wtx, wty] = P(W_.stalk + .04, W_.plane[0][1] + .02);
    c.strokeStyle = '#8f979f'; c.lineWidth = A.race ? 5 : 4; c.beginPath(); c.moveTo(stx, sty); c.bezierCurveTo(stx - 4, sty - 25, wtx + 18, wty + 6, wtx, wty); c.stroke();  // swan neck
    const wy0 = P(0, W_.plane[0][1] + .03)[1], wy1 = P(0, W_.plane[3][1])[1], wgr = c.createLinearGradient(0, wy0, 0, wy1);
    wgr.addColorStop(0, '#5d656d'); wgr.addColorStop(.4, '#2a2f34'); wgr.addColorStop(1, '#121417');
    polyPath(c, W_.plane, P); c.fillStyle = wgr; c.fill();
    c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(...P(W_.plane[0][0], W_.plane[0][1])); c.lineTo(...P(W_.plane[1][0], W_.plane[1][1])); c.stroke();
    if (W_.end) { polyPath(c, W_.end, P); c.fillStyle = '#2a2f34'; c.fill(); c.strokeStyle = 'rgba(255,255,255,.35)'; c.lineWidth = 1; c.stroke(); }
    if (A.race) {                                                    // race number roundel on the door
      const [nx, ny] = P(.02, .74), r = Math.abs(P(.125, 0)[0]);
      c.fillStyle = '#ffffff'; c.beginPath(); c.arc(nx, ny, r, 0, 2 * Math.PI); c.fill();
      c.fillStyle = '#111'; c.font = `700 ${Math.round(r * 1.1)}px ${css('--f-display')}`; c.textAlign = 'center'; c.fillText('90', nx, ny + r * .38); c.textAlign = 'left';
    }
  }
