"""Live smoke test — exercise the apeETABS read stack against a real model.

This is the MANUAL P5 validation juncture (BUILD_PLAN): it ATTACHES to a model
already open in ETABS and drives units -> tables -> stories -> results -> plot
end to end, printing a short report and saving two figures. It is deliberately
forgiving: if a case/combo or a table is missing it prints guidance and keeps
going rather than crashing, so a single un-analyzed model never aborts the run.

Unlike the automated suite (which runs against the mock SapModel), this script
needs a live ETABS + license and is therefore never imported by CI: the live
work is guarded behind ``if __name__ == "__main__"`` so the module imports
cleanly with no ETABS present.

Usage
-----
1. Open ETABS and load one of the reference models, e.g.::

       reference models\\*.EDB

   (the model should ideally already be analyzed, so result tables exist).

2. Run, optionally naming the seismic case/combo to profile::

       cd "C:\\Users\\nmb\\Documents\\Github\\apeETABS" && LADRUNO_OPENSEES_QUIET=1 "C:\\Users\\nmb\\venv\\opensees_env\\Scripts\\python.exe" scripts\\live_smoke.py [--case EQx]

   Selectors are fuzzy-matched by the results layer, so ``--case EQx`` will
   resolve a close ``OutputCase`` name. Pass ``--combo`` instead for a load
   combination. When neither is given the script auto-discovers a case from the
   ``"Story Drifts"`` table.

Figures are written to ``scripts/out/`` using the matplotlib Agg backend (no
display required).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Agg backend BEFORE pyplot is imported anywhere downstream: this script runs
# headless and only ever saves figures, never shows them.
import matplotlib

matplotlib.use("Agg")

from apeETABS import apeETABS  # noqa: E402 — must follow the backend selection

# Figures land here; created on demand so a fresh checkout just works.
_OUT_DIR = Path(__file__).resolve().parent / "out"


def _rule(title: str) -> None:
    """Print a titled section divider (purely cosmetic report structure)."""
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


def _discover_case(e: apeETABS) -> str | None:
    """Best-effort pull of one OutputCase name from the Story Drifts table.

    Returns ``None`` (with guidance) when the table is empty or unreadable, so
    callers can degrade gracefully instead of raising. Used only when the user
    did not pass an explicit ``--case``/``--combo``.
    """
    try:
        df = e.tables.get("Story Drifts", numeric=True)
    except Exception as exc:  # noqa: BLE001 — discovery must never abort the run
        print(f"  Could not read 'Story Drifts' to auto-discover a case: {exc}")
        return None
    if df.empty or "OutputCase" not in df.columns:
        print("  'Story Drifts' has no rows/OutputCase — analyze the model, or")
        print("  pass --case/--combo explicitly.")
        return None
    case = str(df["OutputCase"].iloc[0])
    print(f"  Auto-discovered case from Story Drifts: {case!r}")
    return case


def _report_units(e: apeETABS) -> None:
    """Print present units and pin the baseUnits report system."""
    _rule("UNITS")
    force, length, temp = e.units.get()
    print(f"  Present units: force={force.name}, length={length.name}, "
          f"temperature={temp.name}")
    e.units.use_report_system()  # default N-mm-tonne-s baseUnits system
    print(f"  Report system pinned: {e.units.report!r}")


def _report_tables(e: apeETABS, *, limit: int = 8) -> None:
    """List a handful of available tables (sanity-check the DB bridge)."""
    _rule("TABLES")
    try:
        df = e.tables.available()
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash
        print(f"  Could not list available tables: {exc}")
        return
    print(f"  {len(df)} tables available; first {min(limit, len(df))}:")
    for key, name in zip(df["TableKey"].head(limit), df["TableName"].head(limit)):
        print(f"    - {key}  —  {name}")


def _report_stories(e: apeETABS) -> None:
    """Show the stories snapshot table (roof->base)."""
    _rule("STORIES")
    try:
        print(e.stories.table.to_string(index=False))
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash
        print(f"  Could not read stories: {exc}")


def _report_drifts(e: apeETABS, *, case: str | None, combo: str | None) -> None:
    """Pull story drifts and print the per-direction peaks; save a profile."""
    _rule("STORY DRIFTS")
    try:
        drifts = e.results.story_drifts(case=case, combo=combo)
    except Exception as exc:  # noqa: BLE001 — missing case/table -> guidance
        print(f"  Story drifts unavailable: {exc}")
        print("  (Has the model been analyzed for this case? Try --case/--combo.)")
        return
    print(f"  Resolved case: {drifts.case!r}")
    for direction in ("X", "Y"):
        try:
            value, story = drifts.peak(direction=direction)
            print(f"  Peak drift {direction}: {value:.5g} at story {story!r}")
        except Exception as exc:  # noqa: BLE001 — a missing direction is fine
            print(f"  No drift in direction {direction}: {exc}")

    try:
        fig, _ax = e.plot.drift(drifts, direction="X")
        path = _save(fig, "drift_profile_X")
        print(f"  Saved drift profile -> {path}")
    except Exception as exc:  # noqa: BLE001 — plotting is best-effort
        print(f"  Could not render drift profile: {exc}")


def _report_displacements(
    e: apeETABS, *, case: str | None, combo: str | None
) -> None:
    """Pull joint displacements and print the per-direction peaks."""
    _rule("JOINT DISPLACEMENTS")
    try:
        disp = e.results.displacements(case=case, combo=combo)
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash
        print(f"  Displacements unavailable: {exc}")
        return
    print(f"  Resolved case: {disp.case!r}")
    for direction in ("X", "Y", "Z"):
        try:
            value, story = disp.peak(direction=direction)
            unit = disp.units.get({"X": "Ux", "Y": "Uy", "Z": "Uz"}[direction], "")
            print(f"  Peak U{direction.lower()}: {value:.5g} {unit} at story {story!r}")
        except Exception as exc:  # noqa: BLE001 — a missing direction is fine
            print(f"  No displacement in direction {direction}: {exc}")


def _report_forces(e: apeETABS, *, case: str | None, combo: str | None) -> None:
    """Pull story forces, print the base-shear peaks, save a shear figure."""
    _rule("STORY FORCES")
    try:
        forces = e.results.story_forces(case=case, combo=combo)
    except Exception as exc:  # noqa: BLE001 — missing case/table -> guidance
        print(f"  Story forces unavailable: {exc}")
        print("  (Run the analysis, or pass a valid --case/--combo.)")
        return
    print(f"  Resolved case: {forces.case!r}")
    for direction in ("X", "Y"):
        try:
            profile = forces.shear(direction=direction)
            value, story = profile.peak
            unit = profile.unit
            print(f"  Peak shear {direction}: {value:.5g} {unit}"
                  f"{f' at {story!r}' if story else ''}")
        except Exception as exc:  # noqa: BLE001 — a missing direction is fine
            print(f"  No shear in direction {direction}: {exc}")

    try:
        fig, _ax = e.plot.story_shear(forces, direction="X")
        path = _save(fig, "story_shear_X")
        print(f"  Saved story-shear figure -> {path}")
    except Exception as exc:  # noqa: BLE001 — plotting is best-effort
        print(f"  Could not render story-shear figure: {exc}")


def _save(fig, stem: str) -> Path:
    """Write a matplotlib figure to ``scripts/out/<stem>.png`` and close it."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{stem}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live read-stack smoke test against an open ETABS model.",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--case",
        default=None,
        help="OutputCase to profile (fuzzy-matched), e.g. --case EQx.",
    )
    selector.add_argument(
        "--combo",
        default=None,
        help="Load combination to profile (fuzzy-matched), e.g. --combo 1.2D+1.6L.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    _rule("CONNECT")
    print("  Attaching to the running ETABS instance...")
    try:
        e = apeETABS(attach=True, verbose=True).connect()
    except Exception as exc:  # noqa: BLE001 — a clear message beats a traceback
        print(f"  Could not attach to ETABS: {exc}")
        print("  Open a model in ETABS (e.g. one of 'reference models\\\\*.EDB')"
              " and retry.")
        return 1

    try:
        _report_units(e)
        _report_tables(e)
        _report_stories(e)

        case, combo = args.case, args.combo
        if case is None and combo is None:
            _rule("CASE DISCOVERY")
            case = _discover_case(e)
            if case is None:
                print("  No case to profile; printing units/tables/stories only.")

        if case is not None or combo is not None:
            _report_drifts(e, case=case, combo=combo)
            _report_displacements(e, case=case, combo=combo)
            _report_forces(e, case=case, combo=combo)

        _rule("DONE")
        print(f"  Figures (if any) saved under {_OUT_DIR}")
    finally:
        # Attached session: end() drops local refs but leaves ETABS running.
        e.end()
    return 0


if __name__ == "__main__":
    sys.exit(main())
