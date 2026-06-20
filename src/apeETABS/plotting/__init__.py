"""apeETABS plotting layer (ADR 0004) — pure functions over snapshots.

Importing this package mutates nothing (no rcParams changes, no matplotlib
backend selection). The house theme is opt-in via :mod:`apeETABS.plotting.style`
(``style.apply()`` / ``style.theme()``).

Public surface:

* :func:`drift_profile`, :func:`displacement_profile` — pure plotters that
  take a results snapshot and return ``(fig, ax)``.
* :mod:`style` — ``PALETTE``, ``BLUE``, ``GRAY``, ``apply()``, ``theme()``.
* :class:`Plot` — the ``e.plot`` session sugar composite.
"""

from __future__ import annotations

from . import style
from .profiles import drift_profile, displacement_profile
from .Plot import Plot

__all__ = [
    "style",
    "drift_profile",
    "displacement_profile",
    "Plot",
]
