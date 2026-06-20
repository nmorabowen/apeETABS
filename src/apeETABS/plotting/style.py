"""APE house theme — opt-in palette and rcParams (no import-time side effects).

Per ADR 0004 §2: importing this module mutates nothing. The old code's
``set_default_plot_params()` ran at import in every results module; here the
theme is applied **only** when the caller asks::

    from apeETABS.plotting import style

    style.apply()                  # set APE rcParams globally (caller's choice)
    with style.theme():            # or scoped, restored on exit
        drift_profile(drift, ax=ax)

The palette/colors ship inside the package — there is no external
``plotApeConfig`` dependency (the missing-dependency bug from the old code).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    pass

# Named brand colors — the ex-``plotApeConfig`` set (blueAPE / grayConcrete),
# carried inside the package so plotting is self-contained.
BLUE = "#1f4e79"
GRAY = "#7f7f7f"

# Ordered palette for multi-series / multi-model overlays. Color cycling is
# the caller's job (ADR 0004 §3): index into PALETTE in your loop or pass
# ``color=``; the functions keep no hidden cross-call color state.
PALETTE: list[str] = [
    BLUE,
    "#c00000",   # brick red
    "#2e7d32",   # green
    "#ed7d31",   # orange
    "#7030a0",   # purple
    "#0097a7",   # teal
    GRAY,
]

# APE rcParams overlay. Kept minimal and applied only via apply()/theme().
_RCPARAMS: dict[str, object] = {
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.prop_cycle": None,        # filled in lazily (needs cycler at call time)
    "figure.autolayout": False,     # layout stays the caller's choice (§5)
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.frameon": False,
}


def _rcparams() -> dict[str, object]:
    """Build the rcParams dict, resolving the prop_cycle lazily.

    Importing ``cycler`` only here keeps this module free of import-time
    matplotlib work; nothing happens until apply()/theme() is called.
    """
    from cycler import cycler

    params = dict(_RCPARAMS)
    params["axes.prop_cycle"] = cycler(color=PALETTE)
    return params


def apply() -> None:
    """Set the APE rcParams globally (an explicit, caller-requested mutation)."""
    import matplotlib as mpl

    mpl.rcParams.update(_rcparams())


@contextmanager
def theme() -> Iterator[None]:
    """Apply the APE rcParams for the duration of the ``with`` block.

    Restores the caller's previous rcParams on exit, so a one-off styled plot
    never leaks into the user's global matplotlib state.
    """
    import matplotlib as mpl

    with mpl.rc_context(_rcparams()):
        yield
