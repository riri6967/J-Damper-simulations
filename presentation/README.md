# Faculty presentation

**`J-Damper_CFD_Presentation.pptx`** is a 21-slide deck for the faculty review of this project.

- Course: Pneumatics and Dynamics (23ME2002), Karunya Institute of Technology and Sciences
- Presented by: Rishi Gerolaga Kumar (URK24RA3001) and C Y Nicholas (URKRA3012)

Every slide has speaker notes (what to say, with the key numbers). Open them in PowerPoint with
View → Notes, or use Presenter View. Slides 4 and 15 contain animated GIFs (the CFD flow and the
GT4 at Spa). They play during the slideshow.

| Section | Slides |
|---|---|
| Introduction | 1 Title · 2 Agenda · 3 What is an inerter · 4 How it works (CFD animation) · 5 Why the ideal model is not enough |
| Method | 6 Workflow and tools · 7 CFD models · 8 Vehicle model |
| CFD results | 9 Validation · 10 Dean vortices · 11 Inertance and damping · 12 Piston chamber and ports · 13 Cavitation |
| Vehicle results | 14 Quarter-car grip · 15 Full car on real circuits · 16 Grip by track · 17 Bump grip vs body control |
| Conclusions | 18 Conclusions · 19 Limitations and next steps · 20 References · 21 Thank you |

## Rebuilding

The deck is generated from the project's result figures, so it updates if those are re-run.
From the repo root:

```
python presentation/prepare_assets.py      # crops three figures into presentation/assets/
npm install pptxgenjs react react-dom react-icons sharp
node presentation/build_presentation.js     # writes presentation/J-Damper_CFD_Presentation.pptx
```

The charts on slides 14 and 16 are native PowerPoint charts, so you can edit their data in PowerPoint.
