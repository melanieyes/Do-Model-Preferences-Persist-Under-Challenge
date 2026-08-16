"""Shared figure palette and matplotlib defaults.

Every figure in the paper is emitted from here so the plates match. These values
were previously defined in `analysis/pilot_figures.py`, which the live figure
scripts imported purely for the palette; that file belonged to the exploratory
phase and was removed, so the constants live in their own module rather than
inside a script that does something else.

Importing this module sets the Agg backend and the rcParams — import it before
creating any figure.

    from figure_style import AXIS, DPI, GRID, INK, INK_2, MUTED, SURFACE
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

# Ink, secondary ink, muted text; grid, axis rule, page surface. Unchanged from
# the original definitions — the committed figures are drawn with these.
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"

DPI = 220   # figures are emitted as PNG at print density

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "savefig.dpi": DPI,
    "figure.dpi": DPI,
})

__all__ = ["INK", "INK_2", "MUTED", "GRID", "AXIS", "SURFACE", "DPI"]
