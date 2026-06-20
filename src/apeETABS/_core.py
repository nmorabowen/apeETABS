"""apeETABS — the session facade.

A single connected ETABS model exposed through focused composites, in the
same composition style as apeGmsh::

    from apeETABS import apeETABS

    # Open a model file (launches ETABS):
    with apeETABS(path=r"C:\\models\\tower.edb", verbose=True) as e:
        e.units.set("kN", "m")
        stories = e.stories.table
        drifts = e.tables.get("Joint Drifts")

    # Or attach to a model already open in ETABS:
    with apeETABS(attach=True) as e:
        forces = e.tables.get("Story Forces")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._session import _SessionBase

if TYPE_CHECKING:
    from .core.Units import Units
    from .core.Tables import Tables
    from .core.Stories import Stories
    from .results.Results import Results
    from .plotting.Plot import Plot


class apeETABS(_SessionBase):
    """Standalone single-model ETABS session with all composites.

    Parameters
    ----------
    path : str or Path, optional
        Model file to open. Opening a path launches ETABS unless combined
        with ``attach``/``process_id``.
    attach : bool
        Attach to the active running ETABS instance instead of launching.
    process_id : int, optional
        Attach to a specific running ETABS instance by process id.
    program_path : str or Path, optional
        Explicit ``ETABS.exe`` to launch (else the latest installed).
    visible : bool
        Show the ETABS window when launching (default True).
    verbose : bool
        Print diagnostics.
    """

    _COMPOSITES = (
        ("units",   ".core.Units",   "Units",   False),
        ("tables",  ".core.Tables",  "Tables",  False),
        ("stories", ".core.Stories", "Stories", False),
        ("results", ".results.Results", "Results", False),
        # Optional: degrade to None (not raise) if matplotlib is absent.
        ("plot",    ".plotting.Plot", "Plot",    True),
    )

    # Static type declarations for composites (created at runtime by begin()).
    units: "Units"
    tables: "Tables"
    stories: "Stories"
    results: "Results"
    plot: "Plot"
