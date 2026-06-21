"""Seismic irregularity criteria (ASCE 7-16/22 thresholds).

A frozen, dataclass-based config of the numeric thresholds the P9 irregularity
checks compare against. The module-level :data:`ASCE7` is the default instance;
callers may pass a customized :class:`IrregularityCriteria` to any check method
to override thresholds (e.g. a jurisdiction amendment).

References are to ASCE 7-16/22 Table 12.3-1 (horizontal) and Table 12.3-2
(vertical) structural irregularities.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IrregularityCriteria:
    """ASCE 7-16/22 irregularity thresholds.

    All ratios are dimensionless. Defaults reproduce the code thresholds; build
    a non-default instance to model an amended jurisdiction.
    """

    torsion_1a: float = 1.2
    """Horizontal Type 1a (Torsional): ``delta_max/delta_avg > 1.2``
    (ASCE 7 Table 12.3-1)."""

    torsion_1b: float = 1.4
    """Horizontal Type 1b (Extreme Torsional): ``delta_max/delta_avg > 1.4``
    (ASCE 7 Table 12.3-1)."""

    soft_1a_adjacent: float = 0.70
    """Vertical Type 1a (Soft Story): a story is soft if its lateral stiffness
    is ``< 0.70`` that of the story above (ASCE 7 Table 12.3-2)."""

    soft_1a_avg3: float = 0.80
    """Vertical Type 1a (Soft Story): ...or ``< 0.80`` of the average stiffness
    of the three stories above (ASCE 7 Table 12.3-2)."""

    soft_1b_adjacent: float = 0.60
    """Vertical Type 1b (Extreme Soft Story): ``< 0.60`` of the story above
    (ASCE 7 Table 12.3-2)."""

    soft_1b_avg3: float = 0.70
    """Vertical Type 1b (Extreme Soft Story): ...or ``< 0.70`` of the average of
    the three stories above (ASCE 7 Table 12.3-2)."""

    mass_ratio: float = 1.50
    """Vertical Type 2 (Weight/Mass): a story is mass-irregular where its
    effective mass exceeds ``1.50`` times that of an adjacent story; a roof
    lighter than the floor below is exempt (ASCE 7 Table 12.3-2)."""


# Module-level default instance (ASCE 7-16/22).
ASCE7 = IrregularityCriteria()
