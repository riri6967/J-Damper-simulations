"""Crop the project figures used in the slide deck (removes the built-in plot titles,
which the slides replace with their own headings). Run from the repo root."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(exist_ok=True)

CROPS = {
    "helix_geometry.png": ("cfd/results/models/01_helix_geometry.png", (120, 80, 1010, 744)),
    "mesh_cross_sections.png": ("cfd/results/models/02_cross_section_meshes.png", (0, 60, 1440, 528)),
    "torus_sector.png": ("cfd/results/models/04_torus_sector.png", (200, 170, 880, 610)),
}

for name, (src, box) in CROPS.items():
    Image.open(ROOT / src).convert("RGB").crop(box).save(OUT / name)
    print("wrote", OUT / name)
