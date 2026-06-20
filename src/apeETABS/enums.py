"""ETABS OAPI unit enumerations as Python ``IntEnum``s.

Values mirror the ``eForce`` / ``eLength`` / ``eTemperature`` enumerations
in the ETABS API (see ``.claude/skills/etabs-oapi/reference/enums.md``).
Because they are ``IntEnum``, members pass straight through to comtypes
calls that expect the integer code, while still printing readable names.
"""

from __future__ import annotations

from enum import IntEnum


class eForce(IntEnum):
    """Force units (``cSapModel.SetPresentUnits_2`` force argument)."""

    NotApplicable = 0
    lb = 1
    kip = 2
    N = 3
    kN = 4
    kgf = 5
    tonf = 6


class eLength(IntEnum):
    """Length units (``cSapModel.SetPresentUnits_2`` length argument)."""

    NotApplicable = 0
    inch = 1
    ft = 2
    micron = 3
    mm = 4
    cm = 5
    m = 6


class eTemperature(IntEnum):
    """Temperature units (``cSapModel.SetPresentUnits_2`` temp argument)."""

    NotApplicable = 0
    F = 1
    C = 2
