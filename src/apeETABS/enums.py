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


class eMatType(IntEnum):
    """Material type (``cPropMaterial.SetMaterial`` ``MatType`` argument)."""

    Steel = 1
    Concrete = 2
    NoDesign = 3
    Aluminum = 4
    ColdFormed = 5
    Rebar = 6
    Tendon = 7
    Masonry = 8


class eLoadPatternType(IntEnum):
    """Load pattern type (``cLoadPatterns.Add`` ``MyType`` argument)."""

    Dead = 1
    SuperDead = 2
    Live = 3
    ReduceLive = 4
    Quake = 5
    Wind = 6
    Snow = 7
    Other = 8
    Move = 9
    Temperature = 10
    Rooflive = 11
    Notional = 12
    PatternLive = 13
    Wave = 14
    Braking = 15
