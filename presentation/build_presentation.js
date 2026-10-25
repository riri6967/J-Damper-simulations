// Builds J-Damper_CFD_Presentation.pptx from the project's result figures.
// Run from the repo root:  python presentation/prepare_assets.py  &&  node presentation/build_presentation.js
// Needs: pptxgenjs, react, react-dom, react-icons, sharp (npm).
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = path.resolve(__dirname, "..");
const P = (...p) => path.join(ROOT, ...p);
const OUT = path.join(__dirname, "J-Damper_CFD_Presentation.pptx");

// ---------- theme ----------
const HEX = {
  graphite: "1B1F24", slate: "2B3440", white: "FFFFFF", mist: "F2F4F6",
  copper: "C2581B", steel: "2F6690", grey: "6B7682", amber: "E3A23B",
  lightGrey: "9AA4AE", grid: "DDE1E5", softCopper: "F8E9DF",
};
const THEME = {
  name: "Copper Graphite",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: HEX.graphite, lt1: HEX.white, dk2: HEX.slate, lt2: HEX.mist,
    accent1: HEX.copper, accent2: HEX.steel, accent3: HEX.grey, accent4: HEX.amber,
    accent5: "3A7D44", accent6: "9B2C2C", hlink: HEX.steel, folHlink: HEX.grey,
  },
};

const TEAM = [
  { name: "Rishi Gerolaga Kumar", reg: "URK24RA3001" },
  { name: "C Y Nicholas", reg: "URK24RA3012" },
];
const COURSE = "Pneumatics and Dynamics (23ME2002)";
const INSTITUTE = "Karunya Institute of Technology and Sciences";

// ---------- helpers ----------
async function icon(name, color = "FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(fa[name], { color: "#" + color, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const dims = {};
async function loadDims(files) {
  for (const f of files) {
    const m = await sharp(f, { animated: false }).metadata();
    dims[f] = { w: m.width, h: m.pageHeight || m.height };
  }
}

// Place an image inside a box, keeping its aspect ratio; centred in the box.
function fitImage(slide, file, box, extra = {}) {
  const d = dims[file];
  const r = d.w / d.h;
  let w = box.w, h = box.w / r;
  if (h > box.h) { h = box.h; w = h * r; }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  slide.addImage({ path: file, x, y, w, h, ...extra });
  return { x, y, w, h };
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
  pres.author = TEAM.map((t) => t.name).join(", ");
  pres.company = INSTITUTE;
  pres.subject = COURSE;
  pres.title = "CFD Characterisation of a Helical-Channel Fluid Inerter (J-Damper)";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  const IMG = {
    helix: path.join(__dirname, "assets", "helix_geometry.png"),
    meshes: path.join(__dirname, "assets", "mesh_cross_sections.png"),
    torus: path.join(__dirname, "assets", "torus_sector.png"),
    oscGif: P("cfd", "results", "demo", "osc_X5.gif"),
    layouts: P("cfd", "results", "models", "05_suspension_layouts.png"),
    friction: P("cfd", "results", "s01_friction_ratio.png"),
    dean: P("cfd", "results", "dean_vortices.png"),
    coeffs: P("cfd", "results", "transient_coefficients.png"),
    chamber: P("cfd", "results", "chamber_losses.png"),
    cavitation: P("cfd", "results", "cavitation.png"),
    spaGif: P("sim", "results", "gt4_spa_eau_rouge.gif"),
  };
  await loadDims(Object.values(IMG));

  const ICON = {};
  for (const n of ["FaCube", "FaCheckDouble", "FaWaveSquare", "FaSquareRootAlt", "FaCarSide",
    "FaWater", "FaSyncAlt", "FaDoorOpen", "FaTint", "FaRoad", "FaTruckPickup", "FaCar",
    "FaFlagCheckered", "FaExclamationTriangle", "FaLightbulb", "FaTools", "FaWrench",
    "FaTachometerAlt", "FaChevronRight", "FaWind", "FaUniversity", "FaUserGraduate", "FaCogs"]) {
    ICON[n] = await icon(n);
  }
  ICON.chevronGrey = await icon("FaChevronRight", HEX.lightGrey);

  // Copper circle with a white icon: the deck's recurring motif.
  function badge(slide, x, y, d, iconName, fill = C.accent1) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" },
      objectName: `badge ${iconName}` });
    const p = d * 0.26;
    slide.addImage({ data: ICON[iconName], x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p,
      altText: iconName.replace(/^Fa/, "") });
  }
  function numBadge(slide, x, y, d, n, fill = C.accent1) {
    slide.addText(String(n), { shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color: fill },
      color: C.background1, bold: true, fontSize: Math.round(d * 26), align: "center", valign: "middle",
      margin: 0, isTextBox: true, objectName: `number ${n}` });
  }
  function card(slide, x, y, w, h, fill = C.background2, name = "card") {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill },
      line: { type: "none" }, objectName: name });
  }

  // ---------- layouts ----------
  const footer = [
    { text: { text: `${COURSE}  ·  ${INSTITUTE}`,
      options: { x: 0.6, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: C.accent3, margin: 0 } } },
  ];
  pres.defineSlideMaster({
    title: "TITLE_DARK",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 7.3, h: 2.5,
        fontSize: 34, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.13, h: 0.85,
        fontSize: 30, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      ...footer,
    ],
    slideNumber: { x: 12.23, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.grey, align: "right" },
  });
  pres.defineSlideMaster({
    title: "CONTENT_DARK",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.13, h: 0.85,
        fontSize: 30, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: `${COURSE}  ·  ${INSTITUTE}`,
        options: { x: 0.6, y: 7.0, w: 9, h: 0.3, fontSize: 10, color: C.background2, margin: 0 } } },
    ],
    slideNumber: { x: 12.23, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.mist, align: "right" },
  });

  const content = (title, section) => {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    return s;
  };
  const body = { fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true };
  const caption = { fontSize: 11, color: C.accent3, italic: true, margin: 0, isTextBox: true };

  // =============== 1. Introduction ===============
  pres.addSection({ title: "Introduction" });

  // --- Slide 1: title ---
  {
    const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
    s.addShape(pres.shapes.RECTANGLE, { x: 8.4, y: 0, w: 4.933, h: 7.5, fill: { color: C.background1 },
      line: { type: "none" }, objectName: "image panel" });
    fitImage(s, IMG.helix, { x: 8.7, y: 1.2, w: 4.33, h: 5.1 }, { altText: "Helical oil channel of the fluid inerter" });
    s.addText("PNEUMATICS AND DYNAMICS  ·  23ME2002", { x: 0.6, y: 0.9, w: 7.3, h: 0.4, fontSize: 14, bold: true,
      color: C.accent1, charSpacing: 2, margin: 0, isTextBox: true });
    s.addText("CFD Characterisation of a Helical-Channel Fluid Inerter for Race-Car Suspension",
      { placeholder: "title" });
    s.addText("The J-damper: how much of the ideal inerter's grip benefit survives real fluid behaviour?",
      { x: 0.6, y: 3.6, w: 7.3, h: 0.8, fontSize: 16, italic: true, color: C.background2, margin: 0, isTextBox: true });
    s.addText("PRESENTED BY", { x: 0.6, y: 5.05, w: 7.3, h: 0.3, fontSize: 11, bold: true, color: HEX.lightGrey,
      charSpacing: 2, margin: 0, isTextBox: true });
    s.addText(TEAM.flatMap((t, i) => [
      { text: t.name, options: { bold: true, color: C.background1 } },
      { text: `   ${t.reg}`, options: { color: C.accent1, breakLine: i < TEAM.length - 1 } },
    ]), { x: 0.6, y: 5.4, w: 7.3, h: 0.8, fontSize: 16, margin: 0, paraSpaceAfter: 4, isTextBox: true });
    s.addText(INSTITUTE, { x: 0.6, y: 6.55, w: 7.3, h: 0.35, fontSize: 13, color: HEX.lightGrey, margin: 0,
      isTextBox: true });
    s.addNotes("Good morning. We are " + TEAM.map((t) => `${t.name} (${t.reg})`).join(" and ") +
      ". Our project for " + COURSE + " is a CFD characterisation of a helical-channel fluid inerter, " +
      "the device McLaren raced in Formula 1 as the 'J-damper'. The question we answer is how much of the ideal " +
      "inerter's grip benefit survives once real fluid behaviour is included.");
  }

  // --- Slide 2: agenda ---
  {
    const s = content("What we will cover", "Introduction");
    const items = [
      ["Background", "The inerter, the J-damper and why real fluid behaviour matters"],
      ["Method", "Meshing, CFD validation, oscillating-flow CFD and vehicle models"],
      ["CFD results", "Inertance, parasitic damping, port losses and cavitation"],
      ["Vehicle results", "Quarter-car grip and full-car laps of real circuits"],
      ["Conclusions", "Findings, limitations and next steps"],
    ];
    const w = (12.13 - 4 * 0.3) / 5;
    items.forEach(([h, d], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 1.5, w, 3.6, C.background2, `agenda ${i + 1}`);
      numBadge(s, x + 0.3, 1.8, 0.7, i + 1);
      s.addText(h, { x: x + 0.3, y: 2.75, w: w - 0.6, h: 0.5, fontSize: 18, bold: true, color: C.text1,
        margin: 0, isTextBox: true });
      s.addText(d, { ...body, x: x + 0.3, y: 3.3, w: w - 0.6, h: 1.65, fontSize: 16, color: C.text2 });
    });
    card(s, 0.6, 5.4, 12.13, 1.4, C.text1, "research question card");
    badge(s, 0.9, 5.75, 0.7, "FaLightbulb");
    s.addText([
      { text: "Research question:  ", options: { bold: true, color: C.accent1 } },
      { text: "How far does a real fluid inerter depart from the ideal model, and how much of the theoretical grip benefit to a race car survives?", options: { color: C.background1 } },
    ], { x: 1.85, y: 5.4, w: 10.6, h: 1.4, fontSize: 18, margin: 0, valign: "middle", isTextBox: true });
    s.addNotes("The talk has five parts: background, method, CFD results, vehicle results and conclusions. " +
      "Everything is driven by one research question: how far does a real fluid inerter depart from the ideal model, " +
      "and how much of the grip benefit survives?");
  }

  // --- Slide 3: what is an inerter ---
  {
    const s = content("What is an inerter?", "Introduction");
    card(s, 0.6, 1.5, 6.6, 1.2, C.background2, "equation card");
    s.addText([
      { text: "F = b · (a", options: {} }, { text: "1", options: { subscript: true } },
      { text: " − a", options: {} }, { text: "2", options: { subscript: true } }, { text: ")", options: {} },
    ], { x: 0.9, y: 1.6, w: 3.4, h: 1.0, fontSize: 30, bold: true, color: C.accent1, valign: "middle", margin: 0,
      fontFace: "Cambria", isTextBox: true });
    s.addText("Force ∝ relative acceleration of the two ends.  b = inertance, in kg (Smith, 2002)",
      { ...body, x: 4.3, y: 1.6, w: 2.75, h: 1.0, valign: "middle", color: C.text2 });
    s.addText([
      { text: "Raced by McLaren in Formula 1 (2005–2007) under the codename “J-damper”", options: { bullet: true, breakLine: true } },
      { text: "A fluid inerter makes inertance hydraulically: a piston forces oil through a long, narrow helical channel", options: { bullet: true, breakLine: true } },
      { text: "The fast-moving oil column acts as a large effective mass", options: { bullet: true, breakLine: true } },
      { text: "The ideal model F = b·ẍ ignores friction, swirl and frequency effects in the real oil", options: { bullet: true } },
    ], { ...body, x: 0.6, y: 3.0, w: 6.6, h: 3.7, fontSize: 16, paraSpaceAfter: 10 });

    card(s, 7.6, 1.5, 5.13, 5.25, C.text1, "baseline inerter card");
    s.addText("BASELINE INERTER", { x: 8.0, y: 1.8, w: 4.4, h: 0.3, fontSize: 12, bold: true, color: C.accent1,
      charSpacing: 2, margin: 0, isTextBox: true });
    s.addText([
      { text: "46 g", options: { fontSize: 40, bold: true, color: C.background1 } },
      { text: "  of oil acts like", options: { fontSize: 16, color: C.background2 } },
    ], { x: 8.0, y: 2.2, w: 4.4, h: 0.8, margin: 0, valign: "bottom", isTextBox: true });
    s.addText([
      { text: "91.7 kg", options: { fontSize: 54, bold: true, color: C.accent1 } },
    ], { x: 8.0, y: 3.0, w: 4.4, h: 0.95, margin: 0, valign: "middle", isTextBox: true });
    const specs = [["Piston diameter", "40 mm"], ["Channel", "6 mm × 1.89 m"], ["Coil radius", "30 mm"], ["Oil", "ISO VG 32"]];
    specs.forEach(([k, v], i) => {
      s.addText(k, { x: 8.0, y: 4.3 + i * 0.55, w: 2.2, h: 0.45, fontSize: 14, color: HEX.lightGrey, margin: 0, valign: "middle", isTextBox: true });
      s.addText(v, { x: 10.2, y: 4.3 + i * 0.55, w: 2.2, h: 0.45, fontSize: 14, bold: true, color: C.background1, margin: 0, valign: "middle", align: "right", isTextBox: true });
    });
    s.addNotes("An inerter is a two-terminal suspension element whose force is proportional to the relative acceleration " +
      "between its ends, F = b times (a1 minus a2). b is called the inertance and has units of kilograms. McLaren raced it " +
      "in F1 from 2005 to 2007 as the J-damper. A fluid inerter pushes oil through a long, narrow helical channel. " +
      "In our baseline device, only 46 grams of oil behave like 91.7 kilograms, because the oil moves much faster than the piston.");
  }

  // --- Slide 4: CFD animation ---
  {
    const s = content("How the fluid inerter works", "Introduction");
    fitImage(s, IMG.oscGif, { x: 0.6, y: 1.35, w: 12.13, h: 4.25 }, { altText: "CFD animation of the oscillating flow in the helical channel" });
    const pts = [
      ["FaTachometerAlt", "Piston strokes ±5.6 mm at 10 Hz"],
      ["FaWater", "Oil in the coil moves about 44× faster than the piston"],
      ["FaSyncAlt", "Area of the force loop = energy lost to the oil (parasitic damping)"],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    pts.forEach(([ic, t], i) => {
      const x = 0.6 + i * (w + 0.3);
      badge(s, x, 5.95, 0.6, ic);
      s.addText(t, { ...body, x: x + 0.8, y: 5.85, w: w - 0.8, h: 0.8, valign: "middle" });
    });
    s.addNotes("This is our CFD result animated (it plays in slideshow mode). On the left the piston moves plus/minus 5.6 mm at 10 Hz. " +
      "In the middle is the channel cross-section: colour is oil speed and the arrows are the Dean vortices. On the right is the " +
      "force loop: an ideal inerter would be the dotted straight line; the real oil gives an ellipse, and its area is the energy lost every cycle.");
  }

  // --- Slide 5: why the ideal model is not enough ---
  {
    const s = content("Why the ideal model is not enough", "Introduction");
    const fx = [
      ["FaSyncAlt", "Viscous and curvature losses", "Dean vortices in the curved channel raise the pressure drop above straight-pipe values: parasitic damping"],
      ["FaWaveSquare", "Unsteady flow", "With Womersley number above about 1 the velocity profile changes with frequency, so b and c do too"],
      ["FaDoorOpen", "Entry and exit losses", "Sharp ports at the piston chambers and channel junctions waste kinetic energy"],
      ["FaTint", "Cavitation", "Large inertial pressures can drop the chamber pressure below the oil's vapour pressure"],
    ];
    const w = 3.7, h = 2.5;
    fx.forEach(([ic, t, d], i) => {
      const x = 0.6 + (i % 2) * (w + 0.3), y = 1.5 + Math.floor(i / 2) * (h + 0.3);
      card(s, x, y, w, h, C.background2, `effect ${i + 1}`);
      badge(s, x + 0.3, y + 0.3, 0.6, ic);
      s.addText(t, { x: x + 0.3, y: y + 1.0, w: w - 0.6, h: 0.4, fontSize: 16, bold: true, color: C.text1, margin: 0, isTextBox: true });
      s.addText(d, { ...body, x: x + 0.3, y: y + 1.42, w: w - 0.6, h: 1.0, color: C.text2 });
    });
    card(s, 8.6, 1.5, 4.13, 5.3, C.text1, "research question card");
    badge(s, 8.95, 1.85, 0.7, "FaLightbulb");
    s.addText("RESEARCH QUESTION", { x: 8.95, y: 2.8, w: 3.5, h: 0.3, fontSize: 12, bold: true, color: C.accent1,
      charSpacing: 2, margin: 0, isTextBox: true });
    s.addText("How far does a real fluid inerter depart from the ideal model, and how much of the theoretical grip benefit to a race car survives once these effects are included?",
      { x: 8.95, y: 3.2, w: 3.45, h: 3.3, fontSize: 18, color: C.background1, margin: 0, valign: "top", isTextBox: true });
    s.addNotes("The ideal formula ignores four real effects. One: viscous and curvature losses; the Dean vortices raise the pressure drop and add parasitic damping. " +
      "Two: unsteady flow; above a Womersley number of about 1 the velocity profile, and therefore b and c, depend on frequency. " +
      "Three: entry and exit losses at the ports. Four: cavitation, when the chamber pressure drops below the vapour pressure. " +
      "So our question is: how far does the real device depart from the ideal, and how much grip benefit survives?");
  }

  // =============== 2. Method ===============
  pres.addSection({ title: "Method" });

  // --- Slide 6: workflow ---
  {
    const s = content("Method: CFD as a virtual test rig", "Method");
    const steps = [
      ["FaCube", "Mesh", "Own structured O-grid hex mesh generator in Python (0.16–0.90 M cells)"],
      ["FaCheckDouble", "Validate", "Steady full-helix CFD vs the Ito and White correlations, plus a GCI mesh study"],
      ["FaWaveSquare", "Oscillate", "Periodic torus sector at 1–20 Hz, 2 and 5 mm stroke (pimpleFoam)"],
      ["FaSquareRootAlt", "Reduce", "Fit b(ω), c(ω) and a reduced-order force model"],
      ["FaCarSide", "Drive", "Quarter car, then a full car on Monza, Spa and Daytona"],
    ];
    const gap = 0.4, w = (12.13 - 4 * gap) / 5;
    steps.forEach(([ic, h, d], i) => {
      const x = 0.6 + i * (w + gap);
      card(s, x, 1.5, w, 3.6, C.background2, `step ${i + 1}`);
      badge(s, x + 0.25, 1.8, 0.7, ic);
      s.addText(`STEP ${i + 1}`, { x: x + 0.25, y: 2.7, w: w - 0.5, h: 0.3, fontSize: 11, bold: true, color: C.accent1, charSpacing: 2, margin: 0, isTextBox: true });
      s.addText(h, { x: x + 0.25, y: 3.0, w: w - 0.5, h: 0.4, fontSize: 18, bold: true, color: C.text1, margin: 0, isTextBox: true });
      s.addText(d, { ...body, x: x + 0.25, y: 3.45, w: w - 0.5, h: 1.55, color: C.text2 });
      if (i < steps.length - 1) {
        s.addImage({ data: ICON.chevronGrey, x: x + w + 0.08, y: 3.15, w: 0.24, h: 0.3, altText: "next step" });
      }
    });
    s.addText([
      { text: "Reduced-order model:  ", options: { bold: true, color: C.text1 } },
      { text: "F = b·ẍ + c₁·ẋ + c₂·ẋ|ẋ|", options: { color: C.accent1, bold: true, fontFace: "Cambria" } },
    ], { ...body, x: 0.6, y: 5.35, w: 12.13, h: 0.45, fontSize: 16, valign: "middle" });
    const tools = ["OpenFOAM v2406", "Python: NumPy, SciPy, Matplotlib", "ParaView", "MATLAB (equivalent scripts)"];
    s.addText("TOOLS (all free / open source)", { x: 0.6, y: 6.0, w: 2.6, h: 0.6, fontSize: 11, bold: true, color: C.accent3, charSpacing: 1, margin: 0, valign: "middle", isTextBox: true });
    const tw = [1.9, 3.0, 1.3, 2.6];
    let tx = 3.3;
    tools.forEach((t, i) => {
      s.addText(t, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: tx, y: 6.05, w: tw[i], h: 0.5,
        fill: { color: C.background2 }, color: C.text1, fontSize: 14, align: "center", valign: "middle", margin: 0, isTextBox: true });
      tx += tw[i] + 0.2;
    });
    s.addNotes("Our method uses CFD as a virtual test rig, because we have no hardware. Step 1: we wrote our own structured hex mesh generator. " +
      "Step 2: we validated steady flow in the full helix against published correlations and did a mesh-independence study. " +
      "Step 3: oscillating flow on a periodic torus sector from 1 to 20 Hz. Step 4: we fitted frequency-dependent inertance and damping " +
      "and a reduced-order model. Step 5: we put that model into a quarter car and then a full car on real tracks. All tools are free and open source.");
  }

  // --- Slide 7: CFD models ---
  {
    const s = content("CFD models: full helix and periodic sector", "Method");
    fitImage(s, IMG.meshes, { x: 0.6, y: 1.5, w: 7.0, h: 3.0 }, { altText: "Coarse, medium and fine O-grid cross-sections" });
    s.addText("Structured O-grid cross-sections: coarse / medium / fine", { ...caption, x: 0.6, y: 4.55, w: 7.0, h: 0.3, align: "center" });
    fitImage(s, IMG.torus, { x: 8.1, y: 1.5, w: 4.63, h: 3.0 }, { altText: "Periodic 10 degree torus sector mesh" });
    s.addText("Periodic 10° torus sector, 2,560 cells", { ...caption, x: 8.1, y: 4.55, w: 4.63, h: 0.3, align: "center" });
    const stats = [
      ["0.16 / 0.38 / 0.90 M", "cells in the full 5-turn helix (d = 6 mm, R = 30 mm, pitch 10 mm)"],
      ["2,560", "cells in the periodic sector: cyclic faces make the flow repeat like an endless coil"],
      ["≈\u00A01/100", "of the cost: minutes instead of days per oscillating case"],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    stats.forEach(([n, l], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 4.95, w, 1.85, C.background2, `model stat ${i + 1}`);
      s.addText(n, { x: x + 0.3, y: 5.1, w: w - 0.6, h: 0.6, fontSize: 26, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(l, { ...body, x: x + 0.3, y: 5.75, w: w - 0.6, h: 0.95, color: C.text2 });
    });
    s.addNotes("Two CFD models. The full helix (five turns, 6 mm channel) with three structured meshes from 0.16 to 0.90 million cells, used for steady validation. " +
      "For the oscillating flow we used a 10-degree torus sector with cyclic faces, only 2,560 cells. Fully developed flow repeats every turn, " +
      "so this costs about one hundredth of the full helix. We checked that the helix pitch changes friction by less than 0.1\u00A0%.");
  }

  // --- Slide 8: vehicle models ---
  {
    const s = content("Vehicle model: four suspension layouts", "Method");
    fitImage(s, IMG.layouts, { x: 0.6, y: 1.4, w: 12.13, h: 4.35 }, { altText: "Quarter-car layouts L1 to L4" });
    const chips = [
      ["FaCar", "Quarter car: 250 kg sprung, 35 kg unsprung mass"],
      ["FaRoad", "ISO 8608 class A road at 180 km/h"],
      ["FaFlagCheckered", "Goal: minimise dynamic tyre load (more grip)"],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    chips.forEach(([ic, t], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 5.95, w, 0.85, C.background2, `vehicle chip ${i + 1}`);
      badge(s, x + 0.15, 6.075, 0.6, ic);
      s.addText(t, { ...body, x: x + 0.9, y: 5.95, w: w - 1.05, h: 0.85, valign: "middle" });
    });
    s.addNotes("For the vehicle we compared four quarter-car layouts: L1 conventional, L2 parallel inerter (which gives no grip benefit), " +
      "L3 damper and inerter in series, and L4, the J-damper branch, which is the best. Each was optimised to minimise dynamic tyre load " +
      "on an ISO 8608 class A road at 180 km/h, using an ideal inerter and then each fluid-inerter model.");
  }

  // =============== 3. CFD results ===============
  pres.addSection({ title: "CFD results" });

  // --- Slide 9: validation ---
  {
    const s = content("CFD validation: we can trust the numbers", "CFD results");
    fitImage(s, IMG.friction, { x: 0.6, y: 1.4, w: 6.5, h: 5.4 }, { altText: "CFD friction factor ratio against Ito and White correlations" });
    const stats = [
      ["0.3–3.6\u00A0%", "agreement with the Ito (1959) friction correlation, Re 100–4000 (De 32–1265)"],
      ["0.1–0.3\u00A0%", "discretisation uncertainty from a 3-mesh GCI study (up to De ≈\u00A0300)"],
      ["< 0.1\u00A0%", "effect of helix pitch: the torus sector reproduces the full helix"],
    ];
    stats.forEach(([n, l], i) => {
      const y = 1.5 + i * 1.8;
      card(s, 7.5, y, 5.23, 1.55, C.background2, `validation stat ${i + 1}`);
      s.addText(n, { x: 7.8, y: y + 0.15, w: 4.6, h: 0.65, fontSize: 32, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(l, { ...body, x: 7.8, y: y + 0.8, w: 4.7, h: 0.65, color: C.text2 });
    });
    s.addNotes("Validation. The black dots are our OpenFOAM friction factors; the lines are the Ito and White correlations. " +
      "We agree within 0.3 to 3.6\u00A0% from Re 100 to 4000. The grid convergence index study with three meshes gives 0.1 to 0.3\u00A0% uncertainty " +
      "up to Dean number 300. At De about 1265 only the fine mesh converges, so very high Dean numbers need more wall resolution.");
  }

  // --- Slide 10: Dean vortices ---
  {
    const s = content("Seeing the flow: Dean vortices", "CFD results");
    fitImage(s, IMG.dean, { x: 0.6, y: 1.4, w: 12.13, h: 4.35 }, { altText: "Axial speed and Dean vortex streamlines at three Dean numbers" });
    const pts = [
      ["FaWind", "The coil's curvature drives two counter-rotating Dean vortices"],
      ["FaChevronRight", "The fastest oil is pushed to the outer wall as De rises"],
      ["FaWater", "Extra friction, but a flatter profile: inertance moves towards ideal"],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    pts.forEach(([ic, t], i) => {
      const x = 0.6 + i * (w + 0.3);
      badge(s, x, 6.05, 0.6, ic);
      s.addText(t, { ...body, x: x + 0.8, y: 5.95, w: w - 0.8, h: 0.8, valign: "middle" });
    });
    s.addNotes("Here is the flow inside the channel at three Dean numbers. Colour is axial speed and the streamlines are the secondary flow. " +
      "Curvature creates two counter-rotating Dean vortices that push the fastest oil to the outer wall. That costs extra friction, " +
      "but it also flattens the velocity profile, which brings the inertance closer to the ideal formula.");
  }

  // --- Slide 11: main CFD result ---
  {
    const s = content("Main CFD result: inertance and parasitic damping", "CFD results");
    fitImage(s, IMG.coeffs, { x: 0.6, y: 1.35, w: 12.13, h: 4.35 }, { altText: "Effective inertance and damping against frequency" });
    const stats = [
      ["1.02–1.26 × ideal", "Effective inertance (straight pipe: 1.22–1.33 ×)"],
      ["1.1–3.2 × straight pipe", "Parasitic damping (quasi-steady correlation: within ≈\u00A04\u00A0%)"],
    ];
    const w = (12.13 - 0.3) / 2;
    stats.forEach(([n, l], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 5.85, w, 0.95, C.background2, `cfd stat ${i + 1}`);
      s.addText(n, { x: x + 0.25, y: 5.85, w: 2.6, h: 0.95, fontSize: 20, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(l, { ...body, x: x + 2.9, y: 5.85, w: w - 3.1, h: 0.95, valign: "middle", color: C.text2 });
    });
    s.addNotes("This is the main CFD result. Left: the effective inertance is 1.02 to 1.26 times the ideal formula. It falls with frequency " +
      "and Dean number, because the vortices flatten the profile; a straight laminar pipe would give 1.22 to 1.33. Right: the parasitic damping " +
      "is 1.1 to 3.2 times the straight-pipe value, rising with frequency and stroke. A quasi-steady correlation predicts the damping within about 4\u00A0%, " +
      "but the frequency-dependent inertance is only captured by the CFD.");
  }

  // --- Slide 12: piston chamber and ports ---
  {
    const s = content("Piston chamber and ports: bigger losses than textbooks", "CFD results");
    const a = fitImage(s, IMG.chamber, { x: 0.6, y: 1.4, w: 6.2, h: 4.4 }, { altText: "Port loss coefficients against Reynolds number" });
    s.addText("Axisymmetric CFD of the chamber and port; two meshes agree within 0–6\u00A0%", { ...caption, x: 0.6, y: a.y + a.h + 0.1, w: 6.2, h: 0.3 });
    const hdr = { bold: true, color: HEX.white, fill: { color: HEX.graphite }, fontSize: 13, valign: "middle" };
    const cell = { fontSize: 14, color: HEX.graphite, valign: "middle" };
    const hi = { ...cell, bold: true, color: HEX.copper };
    s.addTable([
      [{ text: "Loss coefficient K", options: hdr }, { text: "Textbook", options: { ...hdr, align: "center" } },
        { text: "2D port", options: { ...hdr, align: "center" } }, { text: "3D drilled port", options: { ...hdr, align: "center" } }],
      [{ text: "Entry, K_in", options: cell }, { text: "0.5", options: { ...cell, align: "center" } },
        { text: "0.32–0.54", options: { ...cell, align: "center" } }, { text: "≈\u00A02.6", options: { ...hi, align: "center" } }],
      [{ text: "Exit, K_out", options: cell }, { text: "1.0", options: { ...cell, align: "center" } },
        { text: "1.89–1.95", options: { ...cell, align: "center" } }, { text: "≈\u00A03.8", options: { ...hi, align: "center" } }],
      [{ text: "Total (velocity heads)", options: { ...cell, bold: true } }, { text: "1.5", options: { ...cell, align: "center" } },
        { text: "≈\u00A02.3", options: { ...cell, align: "center" } }, { text: "≈\u00A06.4", options: { ...hi, align: "center" } }],
    ], { x: 7.2, y: 1.5, w: 5.53, colW: [1.95, 1.0, 1.15, 1.43], rowH: 0.45, border: { type: "solid", pt: 0.75, color: HEX.grid },
      fill: { color: HEX.white }, margin: 0.06 });
    s.addText([
      { text: "Laminar oil leaves the channel with a peaked profile (α ≈\u00A02): exit loss ≈\u00A01.9, not 1.0", options: { bullet: true, breakLine: true } },
      { text: "Each sharp 90° drilled elbow costs about one extra velocity head", options: { bullet: true, breakLine: true } },
      { text: "Chambers add +7.4\u00A0% damping at 10 Hz; quarter-car grip still 5.0\u00A0%", options: { bullet: true } },
    ], { ...body, x: 7.2, y: 3.55, w: 5.53, h: 2.0, paraSpaceAfter: 8 });
    card(s, 7.2, 5.75, 5.53, 1.05, C.text1, "design lesson card");
    badge(s, 7.45, 5.97, 0.6, "FaWrench");
    s.addText([
      { text: "Design lesson:  ", options: { bold: true, color: C.accent1 } },
      { text: "radius the drilled passages", options: { bold: true, color: C.background1 } },
    ], { x: 8.25, y: 5.75, w: 4.3, h: 1.05, fontSize: 16, margin: 0, valign: "middle", isTextBox: true });
    s.addNotes("The coil CFD drives only the channel, so we simulated the piston, its chambers and the ports separately. " +
      "The exit loss is about 1.9, not the textbook 1.0: laminar oil leaves with a peaked profile carrying twice the kinetic energy, and the chamber destroys it all. " +
      "A 3D model of the drilled port as built, a radial hole with two sharp elbows, gives K_in about 2.6 and K_out about 3.8, a total of 6.4 velocity heads. " +
      "The oscillating-piston CFD shows the chambers add 7.4\u00A0% damping. Quarter-car grip stays at 5.0\u00A0%. Lesson: radius the drillings.");
  }

  // --- Slide 13: cavitation ---
  {
    const s = content("Cavitation: how much pre-charge is needed?", "CFD results");
    fitImage(s, IMG.cavitation, { x: 0.6, y: 1.35, w: 12.13, h: 4.1 }, { altText: "Vapour volume over time and minimum chamber pressure against charge pressure" });
    const stats = [
      ["≈\u00A01.75 MPa", "CFD onset; hand calculation Δp/2 gives 1.73 MPa"],
      ["up to 28\u00A0%", "of chamber volume is vapour at 0.5–1.5 MPa"],
      ["≥ 2.0 MPa", "pre-charge: no vapour forms at all"],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    stats.forEach(([n, l], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 5.65, w, 1.15, C.background2, `cavitation stat ${i + 1}`);
      s.addText(n, { x: x + 0.2, y: 5.65, w: 1.65, h: 1.15, fontSize: 20, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(l, { ...body, x: x + 1.9, y: 5.65, w: w - 2.1, h: 1.15, valign: "middle", color: C.text2 });
    });
    s.addNotes("Cavitation, using two-phase CFD (interPhaseChangeFoam with the Schnerr–Sauer model) at 20 Hz and plus/minus 2.4 mm. " +
      "At 0.5, 1.0 and 1.5 MPa pre-charge vapour forms, up to 28\u00A0% of the chamber volume, in the ring vortex next to the port and at the piston corner. " +
      "At 2.0 and 3.0 MPa there is none. The CFD onset of about 1.75 MPa matches our hand calculation of 1.73 MPa.");
  }

  // =============== 4. Vehicle results ===============
  pres.addSection({ title: "Vehicle results" });

  // --- Slide 14: quarter-car grip chart ---
  {
    const s = content("Quarter-car grip: real oil costs about 40\u00A0% of the benefit", "Vehicle results");
    const labels = ["Ideal inerter", "Quasi-steady correlation", "Womersley (straight pipe)", "CFD channel, 2 mm stroke",
      "CFD channel, 5 mm stroke", "CFD + piston chambers, 2 mm"];
    const values = [8.69, 4.44, 5.36, 5.03, 4.51, 5.01];
    s.addChart(pres.charts.BAR, [{ name: "Reduction in dynamic tyre load (%)", labels, values }], {
      x: 0.6, y: 1.4, w: 7.4, h: 5.4, barDir: "bar", catAxisOrientation: "maxMin", barGapWidthPct: 45,
      chartColors: [HEX.steel, HEX.lightGrey, HEX.lightGrey, HEX.copper, HEX.copper, HEX.copper],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', dataLabelFontSize: 12,
      dataLabelColor: HEX.graphite, dataLabelFontFace: "+mn-lt",
      showTitle: true, title: "Reduction in dynamic tyre load, J-damper layout", titleFontSize: 14, titleColor: HEX.graphite, titleFontFace: "+mn-lt",
      catAxisLabelColor: HEX.graphite, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisLineShow: false,
      valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 10, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showLegend: false,
    });
    card(s, 8.4, 1.5, 4.33, 2.5, C.background2, "grip stat card");
    s.addText("8.7\u00A0% → 5.0\u00A0%", { x: 8.7, y: 1.7, w: 3.9, h: 0.9, fontSize: 36, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
    s.addText("Grip benefit: ideal inerter vs the CFD-measured fluid inerter", { ...body, x: 8.7, y: 2.7, w: 3.8, h: 1.1, color: C.text2 });
    card(s, 8.4, 4.3, 4.33, 2.5, C.text1, "loss stat card");
    s.addText("≈\u00A040\u00A0%", { x: 8.7, y: 4.5, w: 3.9, h: 0.9, fontSize: 44, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
    s.addText("of the ideal grip benefit is removed by real fluid behaviour", { ...body, x: 8.7, y: 5.5, w: 3.8, h: 1.1, color: C.background1 });
    s.addNotes("Quarter-car results with the J-damper layout. An ideal inerter reduces the dynamic tyre load by 8.7\u00A0%. " +
      "With our CFD inerter at 2 mm stroke it is 5.0\u00A0%, and 4.5\u00A0% at 5 mm. Including the piston chambers and ports it stays at 5.0\u00A0%. " +
      "So real fluid behaviour removes about 40 to 50\u00A0% of the ideal benefit.");
  }

  // --- Slide 15: real cars, real tracks ---
  {
    const s = content("Full car on real circuits", "Vehicle results");
    const g = fitImage(s, IMG.spaGif, { x: 0.6, y: 1.4, w: 7.8, h: 3.4 }, { altText: "GR Supra GT4 through Eau Rouge at Spa, animated" });
    s.addText("GR Supra GT4 through Eau Rouge / Raidillon at Spa: +1.0 g compression at 227 km/h", { ...caption, x: 0.6, y: g.y + g.h + 0.1, w: 7.8, h: 0.3 });
    const laps = [["1:54.6", "GT4 at Monza (real pace ≈\u00A01:57)"], ["2:34.9", "GT4 at Spa (real pace ≈\u00A02:30)"]];
    laps.forEach(([n, l], i) => {
      const x = 0.6 + i * 4.05;
      card(s, x, 5.45, 3.75, 1.35, C.background2, `lap time ${i + 1}`);
      s.addText(n, { x: x + 0.25, y: 5.55, w: 3.3, h: 0.6, fontSize: 28, bold: true, color: C.accent1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(l, { ...body, x: x + 0.25, y: 6.2, w: 3.3, h: 0.45, color: C.text2 });
    });
    s.addText("VEHICLES", { x: 8.9, y: 1.45, w: 3.8, h: 0.3, fontSize: 12, bold: true, color: C.accent1, charSpacing: 2, margin: 0, isTextBox: true });
    const veh = [["FaCar", "Toyota GR Supra (road car)"], ["FaFlagCheckered", "GR Supra GT4 (race car)"], ["FaTruckPickup", "Ford F-150 (pickup)"]];
    veh.forEach(([ic, t], i) => {
      badge(s, 8.9, 1.9 + i * 0.65, 0.5, ic);
      s.addText(t, { ...body, x: 9.55, y: 1.9 + i * 0.65, w: 3.2, h: 0.5, valign: "middle" });
    });
    s.addText("TRACKS", { x: 8.9, y: 4.0, w: 3.8, h: 0.3, fontSize: 12, bold: true, color: C.accent1, charSpacing: 2, margin: 0, isTextBox: true });
    s.addText([
      { text: "Monza and Spa (TUM racetrack database)", options: { bullet: true, breakLine: true } },
      { text: "Daytona (banking, built from official dimensions)", options: { bullet: true, breakLine: true } },
      { text: "Straight rough test road", options: { bullet: true, breakLine: true } },
      { text: "Weight transfer, pitch, roll, kerbs and bump stops are modelled", options: { bullet: true } },
    ], { ...body, x: 8.9, y: 4.4, w: 3.83, h: 2.4, paraSpaceAfter: 6 });
    s.addNotes("Then we built a full-car track simulator: Toyota GR Supra road car and GT4 race car, and a Ford F-150, on Monza, Spa, " +
      "Daytona and a straight rough test road. It models weight transfer, pitch, roll, kerbs and bump stops. The animation is the GT4 through " +
      "Eau Rouge at Spa. Simulated GT4 lap times are 1:54.6 at Monza and 2:34.9 at Spa, close to real GT4 pace.");
  }

  // --- Slide 16: grip by track (native charts) ---
  {
    const s = content("Grip effect on each track", "Vehicle results");
    s.addText("Steadier tyre load vs conventional suspension (%, positive = more grip); J-damper replaces the main damper",
      { ...body, x: 0.6, y: 1.3, w: 12.13, h: 0.4, color: C.text2 });
    const tracks = ["Test road", "Monza", "Spa", "Daytona"];
    const data = [
      ["GR Supra (road)", [6.23, 1.44, -1.06, 7.3], [6.98, 4.84, 4.21, 4.97]],
      ["GR Supra GT4 (race)", [6.05, 4.93, 6.09, -1.91], [-0.74, 1.92, 1.76, 2.76]],
      ["Ford F-150", [6.13, 6.46, 4.0, 9.15], [6.78, 6.93, 7.17, 5.51]],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    data.forEach(([veh, ideal, cfd], i) => {
      s.addChart(pres.charts.BAR, [
        { name: "Ideal J-damper", labels: tracks, values: ideal },
        { name: "CFD J-damper", labels: tracks, values: cfd },
      ], {
        x: 0.6 + i * (w + 0.3), y: 1.8, w, h: 4.1, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
        chartColors: [HEX.steel, HEX.copper],
        showTitle: true, title: veh, titleFontSize: 14, titleColor: HEX.graphite, titleFontFace: "+mn-lt",
        showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", dataLabelFontSize: 10,
        dataLabelColor: HEX.graphite, dataLabelFontFace: "+mn-lt",
        catAxisLabelColor: HEX.graphite, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
        valAxisLabelColor: HEX.grey, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt",
        valAxisMinVal: -4, valAxisMaxVal: 10, valAxisMajorUnit: 2, valAxisLabelFormatCode: "0",
        valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false,
      });
    });
    const lg = [[HEX.steel, "Ideal J-damper"], [HEX.copper, "CFD J-damper (real fluid inerter)"]];
    let lx = 0.6;
    lg.forEach(([c, t], i) => {
      s.addShape(pres.shapes.RECTANGLE, { x: lx, y: 6.05, w: 0.2, h: 0.2, fill: { color: i === 0 ? C.accent2 : C.accent1 }, line: { type: "none" }, objectName: `legend ${t}` });
      s.addText(t, { x: lx + 0.3, y: 5.97, w: 3.2, h: 0.36, fontSize: 12, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      lx += i === 0 ? 2.1 : 0;
    });
    s.addText([
      { text: "Soft road car and pickup: ", options: { bold: true, color: C.accent1 } },
      { text: "the real inerter's fluid damping helps (+4 to +7\u00A0% on circuits).  ", options: {} },
      { text: "Stiff GT4: ", options: { bold: true, color: C.accent2 } },
      { text: "fluid losses cancel most of the gain (0 to +2\u00A0%).", options: {} },
    ], { ...body, x: 0.6, y: 6.4, w: 12.13, h: 0.45, valign: "middle" });
    s.addNotes("Full-lap results with the J-damper replacing the main damper. On the soft Supra road car and the F-150 the CFD J-damper is 4 to 7\u00A0% better " +
      "than conventional on circuits, often better than the ideal inerter, because its built-in fluid damping helps body control. " +
      "On the stiff GT4 race car the fluid losses cancel most of the benefit: 0 to 2\u00A0%, where an ideal inerter would give 5 to 6\u00A0%.");
  }

  // --- Slide 17: trade-off ---
  {
    const s = content("The trade-off: bump grip vs body control", "Vehicle results");
    const cols = [
      [C.accent3, "FaCogs", "Conventional", "Spring + damper per wheel",
        [["Bumps (> 3 Hz)", "Baseline"], ["Body motion (< 3 Hz)", "Best controlled"], ["Best for", "Body control, simplicity"]]],
      [C.accent2, "FaWaveSquare", "Ideal J-damper", "Perfect inerter, F = b·ẍ",
        [["Bumps (> 3 Hz)", "Better, up to +7\u00A0%"], ["Body motion (< 3 Hz)", "Worse without the main damper (down to −7\u00A0%)"], ["Best for", "Stiff race car (GT4)"]]],
      [C.accent1, "FaWater", "CFD J-damper", "Real fluid inerter, as measured",
        [["Bumps (> 3 Hz)", "Better on soft cars (up to +9\u00A0%)"], ["Body motion (< 3 Hz)", "Fluid damping keeps control (+1 to +3\u00A0%)"], ["Best for", "Road car and pickup"]]],
    ];
    const w = (12.13 - 2 * 0.3) / 3;
    cols.forEach(([col, ic, h, sub, rows], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 1.45, w, 3.95, C.background2, `suspension ${h}`);
      badge(s, x + 0.3, 1.7, 0.6, ic, col);
      s.addText(h, { x: x + 1.05, y: 1.65, w: w - 1.25, h: 0.4, fontSize: 18, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(sub, { ...caption, x: x + 1.05, y: 2.05, w: w - 1.25, h: 0.3 });
      rows.forEach(([k, v], j) => {
        const y = 2.6 + j * 0.92;
        s.addText(k.toUpperCase(), { x: x + 0.3, y, w: w - 0.6, h: 0.28, fontSize: 10, bold: true, color: C.accent3, charSpacing: 1, margin: 0, isTextBox: true });
        s.addText(v, { ...body, x: x + 0.3, y: y + 0.3, w: w - 0.6, h: 0.55 });
      });
    });
    card(s, 0.6, 5.65, 12.13, 1.15, C.text1, "design implication card");
    badge(s, 0.85, 5.92, 0.6, "FaLightbulb");
    s.addText([
      { text: "Design implication:  ", options: { bold: true, color: C.accent1 } },
      { text: "parasitic damping per kg of inertance, c_par / b = 32ν / d² · (f_c / f_s), depends only on channel diameter. Race cars: widen the channel. Road cars: let the fluid damping replace part of the main damper.", options: { color: C.background1 } },
    ], { x: 1.65, y: 5.65, w: 10.85, h: 1.15, fontSize: 14, margin: 0, valign: "middle", isTextBox: true });
    s.addNotes("Why the results differ. The inerter helps with bumps and wheel hop above about 3 Hz. But if you remove the main damper, " +
      "an ideal inerter gives almost no damping at body frequencies, so the body wallows after braking and cornering. The real inerter's " +
      "fluid friction damps that motion, which is why it beats the ideal one on soft cars. Kerb strikes and wheel lifts are unaffected by all three. " +
      "Design implication: parasitic damping per kg of inertance depends only on the channel diameter, so packaging versus fluid losses is the core trade-off.");
  }

  // =============== 5. Conclusions ===============
  pres.addSection({ title: "Conclusions" });

  // --- Slide 18: conclusions ---
  {
    const s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "Conclusions" });
    s.addText("Conclusions", { placeholder: "title" });
    const pts = [
      ["CFD is validated", "within 0.3–3.6\u00A0% of established correlations; mesh uncertainty 0.1–0.3\u00A0%"],
      ["A real fluid inerter is not ideal", "inertance 1.02–1.26 × ideal, plus 1.1–3.2 × the parasitic damping of a straight pipe"],
      ["On a single wheel", "real-fluid effects cost about 40\u00A0% of the ideal grip benefit (8.7\u00A0% → 5.0\u00A0%)"],
      ["Ports and cavitation", "drilled ports lose ≈\u00A06.4 velocity heads; at least ≈\u00A01.75 MPa pre-charge avoids cavitation"],
      ["On real cars and tracks", "a trade-off between bump grip and body control: +4–7\u00A0% for soft cars, 0–2\u00A0% for the stiff race car"],
    ];
    pts.forEach(([h, d], i) => {
      const y = 1.5 + i * 1.05;
      numBadge(s, 0.6, y + 0.1, 0.6, i + 1);
      s.addText([
        { text: h, options: { bold: true, color: C.background1, breakLine: true } },
        { text: d, options: { color: C.background2 } },
      ], { x: 1.45, y, w: 11.28, h: 0.85, fontSize: 16, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addNotes("To conclude. One: our CFD is validated against correlations and a mesh study. Two: a real fluid inerter's inertance is close to ideal, " +
      "but it adds significant parasitic damping. Three: on a single wheel that costs about 40\u00A0% of the grip benefit. Four: the drilled ports lose about 6.4 velocity heads " +
      "and the device needs at least 1.75 MPa pre-charge. Five: on real cars it is a trade-off between bump grip and body control; " +
      "the real inerter helps soft cars, while for a stiff race car the fluid losses must be minimised.");
  }

  // --- Slide 19: limitations and next steps ---
  {
    const s = content("Limitations and next steps", "Conclusions");
    const cols = [
      ["FaExclamationTriangle", "Limitations", [
        "Laminar, isothermal oil (viscosity changes with temperature)",
        "Chamber and cavitation CFD are axisymmetric; the 3D port CFD is steady",
        "Track simulator: tyres carry vertical load only; CoG, anti-roll bars and aero are estimates",
        "Spring rates from owner forums; F-150 rear axle modelled as independent",
      ]],
      ["FaTools", "Next steps", [
        "Compare with published fluid-inerter experiments (Swift et al. 2013; Liu et al. 2018)",
        "CFD of radiused port passages",
        "Finer study of the high-Dean regime (De > 1000)",
        "Tyre force model, lap-time study and a build-and-test rig",
      ]],
    ];
    const w = (12.13 - 0.3) / 2;
    cols.forEach(([ic, h, items], i) => {
      const x = 0.6 + i * (w + 0.3);
      card(s, x, 1.5, w, 5.3, C.background2, h);
      badge(s, x + 0.35, 1.8, 0.7, ic, i === 0 ? C.accent3 : C.accent1);
      s.addText(h, { x: x + 1.25, y: 1.8, w: w - 1.6, h: 0.7, fontSize: 22, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true });
      s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
        { ...body, x: x + 0.35, y: 2.8, w: w - 0.7, h: 3.8, fontSize: 18, paraSpaceAfter: 16 });
    });
    s.addNotes("Limitations: laminar isothermal oil; the chamber and cavitation CFD are axisymmetric and the 3D port CFD is steady; " +
      "the track simulator uses vertical tyre load only, and some vehicle parameters are estimates. Next steps: compare with published " +
      "fluid-inerter experiments, simulate radiused ports, refine the high-Dean regime, and add a tyre model and a physical test rig.");
  }

  // --- Slide 20: references ---
  {
    const s = content("References", "Conclusions");
    const refs = [
      "Smith, M.C. (2002). Synthesis of mechanical networks: the inerter. IEEE Trans. Automatic Control, 47(10), 1648–1662.",
      "Smith, M.C. & Wang, F.-C. (2004). Performance benefits in passive vehicle suspensions employing inerters. Vehicle System Dynamics, 42(4), 235–257.",
      "Swift, S.J. et al. (2013). Design and modelling of a fluid inerter. Int. J. Control, 86(11), 2035–2051.",
      "Liu, X., Jiang, J.Z., Titurus, B. & Harrison, A. (2018). Model identification methodology for fluid-based inerters. Mech. Systems and Signal Processing, 106, 479–494.",
      "Dean, W.R. (1927/1928). The stream-line motion of fluid in a curved pipe. Phil. Mag.",
      "White, C.M. (1929). Streamline flow through curved pipes. Proc. R. Soc. Lond. A, 123, 645–663.",
      "Ito, H. (1959). Friction factors for turbulent flow in curved pipes. J. Basic Engineering, 81, 123–134.",
      "Womersley, J.R. (1955). Method for the calculation of velocity, rate of flow and viscous drag in arteries when the pressure gradient is known. J. Physiology, 127, 553–563.",
      "Celik, I.B. et al. (2008). Procedure for estimation and reporting of uncertainty due to discretization in CFD applications. J. Fluids Eng., 130(7), 078001.",
      "Schnerr, G.H. & Sauer, J. (2001). Physical and numerical modeling of unsteady cavitation dynamics. ICMF 2001.",
      "ISO 8608:2016. Mechanical vibration — Road surface profiles — Reporting of measured data.",
    ];
    const half = 6;
    [refs.slice(0, half), refs.slice(half)].forEach((list, i) => {
      s.addText(list.map((t, j) => ({ text: t, options: { breakLine: j < list.length - 1 } })),
        { ...body, x: 0.6 + i * 6.215, y: 1.5, w: 5.915, h: 5.3, fontSize: 14, color: C.text2, paraSpaceAfter: 10 });
    });
    s.addNotes("These are the main references for the inerter theory, curved-pipe flow, oscillating pipe flow, the mesh-uncertainty method and the cavitation model.");
  }

  // --- Slide 21: thank you ---
  {
    const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Conclusions" });
    s.addShape(pres.shapes.RECTANGLE, { x: 8.4, y: 0, w: 4.933, h: 7.5, fill: { color: C.background1 },
      line: { type: "none" }, objectName: "image panel" });
    fitImage(s, IMG.helix, { x: 8.7, y: 1.2, w: 4.33, h: 5.1 }, { altText: "Helical oil channel of the fluid inerter" });
    s.addText("Thank you", { x: 0.6, y: 1.6, w: 7.3, h: 1.1, fontSize: 48, bold: true, color: C.background1, margin: 0, isTextBox: true });
    s.addText("Questions and discussion", { x: 0.6, y: 2.7, w: 7.3, h: 0.6, fontSize: 22, color: C.accent1, margin: 0, isTextBox: true });
    TEAM.forEach((t, i) => {
      const x = 0.6, yy = 3.8 + i * 1.0;
      badge(s, x, yy, 0.7, "FaUserGraduate");
      s.addText([
        { text: t.name, options: { bold: true, color: C.background1, breakLine: true } },
        { text: t.reg, options: { color: HEX.lightGrey } },
      ], { x: x + 0.9, y: yy - 0.1, w: 6.4, h: 0.9, fontSize: 16, margin: 0, valign: "middle", isTextBox: true });
    });
    badge(s, 0.6, 5.9, 0.7, "FaUniversity");
    s.addText([
      { text: INSTITUTE, options: { bold: true, color: C.background1, breakLine: true } },
      { text: COURSE, options: { color: HEX.lightGrey } },
    ], { x: 1.5, y: 5.8, w: 6.4, h: 0.9, fontSize: 16, margin: 0, valign: "middle", isTextBox: true });
    s.addNotes("Thank you. We are happy to take questions. Likely ones: why a torus sector (fully developed flow repeats every turn; < 0.1\u00A0% difference), " +
      "how we know the CFD is right (correlations, GCI, Womersley limit), and why the exit loss is 1.9 not 1.0 (laminar profile carries twice the kinetic energy).");
  }

  await pres.writeFile({ fileName: OUT });
  await applyThemeColors(OUT, THEME);
  console.log("wrote", OUT);
}

// pptxgenjs writes Office's stock palette into the theme; replace it with ours so the
// scheme colours used above resolve to the deck's own colours.
async function applyThemeColors(file, theme) {
  const fs = require("fs");
  const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const part = "ppt/theme/theme1.xml";
  let xml = await zip.file(part).async("string");
  for (const [key, hex] of Object.entries(theme.colors)) {
    const re = new RegExp(`<a:${key}>[\\s\\S]*?</a:${key}>`);
    if (!re.test(xml)) throw new Error(`theme slot ${key} not found`);
    xml = xml.replace(re, `<a:${key}><a:srgbClr val="${hex}"/></a:${key}>`);
  }
  xml = xml.replace(/<a:clrScheme name="[^"]*">/, `<a:clrScheme name="${theme.name}">`);
  zip.file(part, xml);
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

main().catch((e) => { console.error(e); process.exit(1); });
