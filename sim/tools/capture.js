// Records an animation clip from the running simulator page (served by sim/tools/sim_server.py).
// Paste/inject into the page, then: await captureClip({...}). Frames go to sim/results/capture/frames/<name>/.
window.captureClip = async function ({ name, veh, trk, sus = 2, kept = 2, mag = 4, startS = 0, settle = 1.5, frames = 80, dtSim = 0.03, caption = '' }) {
  if (document.getElementById('play').textContent === 'Pause') document.getElementById('play').click();
  document.querySelector(`[data-veh=${veh}]`).click();
  document.querySelector(`[data-trk=${trk}]`).click();
  document.querySelector(`[data-sus="${sus}"]`).click();
  const k = document.getElementById('kept'); k.value = kept; k.dispatchEvent(new Event('input'));
  const m = document.getElementById('mag'); m.value = mag; m.dispatchEvent(new Event('input'));
  __sim.setS(Math.max(0, startS - settle * 60));
  for (let i = 0; i < Math.round(settle / 2e-4); i++) __sim.stepAll();         // let the car settle before recording
  // fixed recording size, independent of the browser window
  document.querySelector('.wrap').style.maxWidth = 'none';
  for (const [id, w] of [['cv-side', 1160], ['cv-top', 420], ['cv-trace', 740]]) { const e = document.getElementById(id); e.style.width = w + 'px'; e.style.maxWidth = 'none'; }
  __sim.redraw();                                                              // size the canvases before measuring them
  const side = document.getElementById('cv-side'), top = document.getElementById('cv-top'), tr = document.getElementById('cv-trace');
  const W = 1200, sideH = Math.round(W * side.height / side.width), trW = Math.round(W * 0.62), topW = W - trW - 8;
  const trH = Math.round(trW * tr.height / tr.width), topH = Math.round(topW * top.height / top.width), lowH = Math.max(trH, topH), H = sideH + lowH + 40;
  const out = document.createElement('canvas'); out.width = W; out.height = H; const c = out.getContext('2d');
  const bg = getComputedStyle(document.body).backgroundColor;
  for (let f = 0; f < frames; f++) {
    for (let i = 0; i < Math.round(dtSim / 2e-4); i++) __sim.stepAll();
    __sim.tick(dtSim);                                                       // kerb-strike label lasts 0.6 s of sim time
    __sim.redraw();
    c.fillStyle = bg; c.fillRect(0, 0, W, H);
    c.drawImage(side, 0, 0, W, sideH);
    c.drawImage(tr, 0, sideH + 4, trW, trH);
    c.drawImage(top, trW + 8, sideH + 4, topW, topH);
    c.fillStyle = '#e4e9ee'; c.font = '600 16px "IBM Plex Sans", Arial';
    c.fillText(caption, 12, H - 11);
    const blob = await new Promise(r => out.toBlob(r, 'image/jpeg', 0.88));
    await fetch(`/save/frames/${name}/frame_${String(f).padStart(3, '0')}.jpg`, { method: 'POST', body: blob });
  }
  return `${name}: ${frames} frames`;
};
'capture ready';
