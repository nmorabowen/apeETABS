"""apeETABS plotting layer (ADR 0004) — pure functions over snapshots.

Importing this package mutates nothing (no rcParams changes, no matplotlib
backend selection). The house theme is opt-in via :mod:`apeETABS.plotting.style`
(``style.apply()`` / ``style.theme()``).

Public surface:

* :func:`drift_profile`, :func:`displacement_profile` — pure profile plotters.
* :func:`story_shear`, :func:`story_forces`, :func:`wall_forces`,
  :func:`wall_force_envelopes` — pure force plotters.
* :mod:`style` — ``PALETTE``, ``BLUE``, ``GRAY``, ``apply()``, ``theme()``.
* :class:`Plot` — the ``e.plot`` session sugar composite.

All plotters take a results snapshot (in report units) and return ``(fig, ax)``
or ``(fig, axes)``.
"""

from __future__ import annotations

from . import style
from .profiles import drift_profile, displacement_profile
from .forces import story_shear, story_forces, wall_forces, wall_force_envelopes
from .Plot import Plot

__all__ = [
    "style",
    "drift_profile",
    "displacement_profile",
    "story_shear",
    "story_forces",
    "wall_forces",
    "wall_force_envelopes",
    "Plot",
]
