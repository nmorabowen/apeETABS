"""apeETABS — a human-centric Python wrapper around the CSI ETABS Open API.

Composition-based API: a connected session exposes focused composites
(``units``, ``tables``, ``stories``) in the same style as apeGmsh.

Example
-------
::

    from apeETABS import apeETABS

    # Open a model file (launches ETABS):
    with apeETABS(path=r"C:\\models\\tower.edb", verbose=True) as e:
        e.units.set("kN", "m")
        story_forces = e.tables.get("Story Forces")
        drifts = e.tables.get("Joint Drifts")

    # Or attach to a model already open in ETABS:
    with apeETABS(attach=True) as e:
        e.units.use_report_system()          # default baseUnits (N-mm-tonne-s)
        V_base = e.units.to_base(125.0, "force")

The session is also usable without the context manager::

    e = apeETABS(attach=True).connect()
    ...
    e.end()
"""

from __future__ import annotations

from ._session import _SessionBase
from ._core import apeETABS
from .enums import eForce, eLength, eTemperature
from .errors import ETABSError, ConnectionError, ok

# Ergonomic alias.
ETABS = apeETABS

__version__ = "0.1.0"

__all__ = [
    "apeETABS",
    "ETABS",
    "_SessionBase",
    "eForce",
    "eLength",
    "eTemperature",
    "ETABSError",
    "ConnectionError",
    "ok",
    "__version__",
]
