"""Live validation — resolve every ``# LIVE-CONFIRM`` against a real model.

This is the MANUAL P5/P9 validation juncture (BUILD_PLAN). On a single live run
against a real (ideally analyzed) ETABS model it:

1. Connects — either by ATTACHing to a running instance (default), or by
   LAUNCHing ETABS and opening a ``.EDB`` (``--model PATH``).
2. Reports whether the model is locked (a proxy for "analysis has been run", so
   the result tables exist).
3. Dumps the FULL available-tables list (``TableKey`` vs ``TableName``) — this
   resolves the P5/med follow-up: the display name we use as the
   ``GetTableForDisplayArray`` key may differ from the real table KEY.
4. For each table of interest (the existing read stack + the new P9 seismic-
   irregularity tables), prints the ACTUAL column headers and row count, so the
   ``_COLUMN_MAP`` / ``_TABLE`` guesses marked ``# LIVE-CONFIRM`` can be
   confirmed or corrected in one pass.
5. Builds and exercises the P9 snapshots (CM/CR, story stiffness, torsion) and
   saves the four irregularity figures.

It is deliberately forgiving: every section is guarded, so a missing case/table
or an un-analyzed model prints guidance and keeps going rather than aborting.

Usage
-----
Attach to a model already open in ETABS::

    cd "C:\\Users\\nmb\\Documents\\Github\\apeETABS" && LADRUNO_OPENSEES_QUIET=1 "C:\\Users\\nmb\\venv\\opensees_env\\Scripts\\python.exe" scripts\\live_validate.py [--case EQx]

Or let the script launch ETABS and open a reference model::

    ... scripts\\live_validate.py --model "reference models\\Casa 17B RevA.EDB"

Figures are written to ``scripts/out/`` (matplotlib Agg backend; no display).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: only ever save figures

from apeETABS import apeETABS  # noqa: E402 — must follow the backend selection
from apeETABS.results.CentersMassRigidity import CentersMassRigidity  # noqa: E402
from apeETABS.results.StoryStiffness import StoryStiffness  # noqa: E402
from apeETABS.results.TorsionIrregularity import TorsionIrregularity  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "out"

# Tables whose column maps carry # LIVE-CONFIRM (P9) plus the existing read
# stack. The values are the display-name keys the code currently uses; the run
# prints the real headers so they can be confirmed/fixed.
_TABLES_OF_INTEREST = [
    "Story Drifts",
    "Joint Displacements",
    "Story Forces",
    # --- P9 seismic-irregularity tables (all # LIVE-CONFIRM) ---
    "Centers of Mass and Rigidity",
    "Story Stiffness",
    "Story Max Over Avg Drifts",
]


def _rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _dump_available(e: apeETABS) -> list[tuple[str, str]]:
    """Print the full TableKey/TableName list; return the (key, name) pairs."""
    _rule("AVAILABLE TABLES  (real TableKey  vs  human TableName)")
    try:
        df = e.tables.available()
    except Exception as exc:  # noqa: BLE001
        print(f"  Could not list available tables: {exc}")
        return []
    pairs = list(zip((str(k) for k in df["TableKey"]),
                     (str(n) for n in df["TableName"])))
    print(f"  {len(pairs)} tables available:")
    for key, name in pairs:
        flag = "  <-- key != name" if key != name else ""
        print(f"    {key!r:50} {name!r}{flag}")
    return pairs


def _resolve_key(pairs: list[tuple[str, str]], wanted: str) -> str | None:
    """Find the real TableKey whose key OR name case-insensitively matches."""
    w = wanted.lower()
    for key, name in pairs:
        if key.lower() == w or name.lower() == w:
            return key
    # fall back: substring match on the human name
    for key, name in pairs:
        if w in name.lower() or w in key.lower():
            return key
    return None


def _dump_schema(e: apeETABS, pairs: list[tuple[str, str]]) -> None:
    """For each table of interest, print the ACTUAL headers + row count."""
    _rule("TABLE SCHEMAS  (confirm/correct the # LIVE-CONFIRM column maps)")
    for wanted in _TABLES_OF_INTEREST:
        key = _resolve_key(pairs, wanted) if pairs else wanted
        if key is None:
            print(f"\n  '{wanted}': NOT FOUND in available tables "
                  f"(name/key may differ — see the list above).")
            continue
        try:
            df = e.tables.get(key, numeric=False)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  '{wanted}' (key={key!r}): could not read — {exc}")
            continue
        note = "" if key == wanted else f"  [code uses {wanted!r}]"
        print(f"\n  '{wanted}' -> key={key!r}{note}")
        print(f"    rows: {len(df)}")
        print(f"    columns ({len(df.columns)}): {list(df.columns)}")
        if not df.empty:
            print("    first row:")
            print(df.head(1).to_string(index=False).replace("\n", "\n      "))


def _maybe_analyze(e: apeETABS, *, requested: bool) -> None:
    """Run analysis IFF requested and the model is not already analyzed.

    ``is_locked`` is ETABS's proxy for "analysis has been run" (it locks the
    model on a successful run). We only trigger a run when the user opted in
    AND the model is currently unlocked, so an already-analyzed model is never
    needlessly re-run. ``RunAnalysis()`` needs the model saved to disk — which
    a reference ``.EDB`` opened from disk already is.
    """
    if not requested:
        return
    _rule("ANALYSIS")
    try:
        if e.is_locked:
            print("  Model already locked (analyzed) — skipping the run.")
            return
    except Exception as exc:  # noqa: BLE001
        print(f"  Could not read lock state ({exc}); attempting a run anyway.")
    print("  Model not analyzed — running analysis (this can take a while)...")
    try:
        ret = e.SapModel.Analyze.RunAnalysis()
        if ret != 0:
            print(f"  RunAnalysis returned nonzero ({ret}); results may be absent.")
        else:
            print("  Analysis complete.")
    except Exception as exc:  # noqa: BLE001
        print(f"  RunAnalysis failed: {exc}")
        print("  (Save the model in ETABS first, then retry.)")


def _discover_case(e: apeETABS) -> str | None:
    """Pull one OutputCase from Story Drifts (best effort)."""
    try:
        df = e.tables.get("Story Drifts", numeric=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  Could not auto-discover a case: {exc}")
        return None
    if df.empty or "OutputCase" not in df.columns:
        print("  'Story Drifts' empty — analyze the model or pass --case.")
        return None
    case = str(df["OutputCase"].iloc[0])
    print(f"  Auto-discovered case: {case!r}")
    return case


def _save(fig, stem: str) -> Path:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{stem}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return path


def _validate_cm_cr(e: apeETABS) -> None:
    """Build the CM/CR snapshot; print eccentricity + mass check; save plots."""
    _rule("P9 — CENTERS OF MASS & RIGIDITY  (+ mass irregularity)")
    try:
        snap = CentersMassRigidity.from_table(e)
    except Exception as exc:  # noqa: BLE001
        print(f"  Unavailable: {exc}")
        print("  (Centers of Mass/Rigidity needs analysis results — analyze first.)")
        return
    try:
        print("  Eccentricity (ex, ey) per story:")
        print(snap.eccentricity().to_string(index=False).replace("\n", "\n    "))
    except Exception as exc:  # noqa: BLE001
        print(f"  eccentricity() failed: {exc}")
    try:
        print("\n  Mass check (Type 2):")
        print(snap.mass_check().to_string(index=False).replace("\n", "\n    "))
    except Exception as exc:  # noqa: BLE001
        print(f"  mass_check() failed: {exc}")
    for kind in ("cm_cr", "mass_irregularity"):
        try:
            fig, _ = getattr(e.plot, kind)(snap)
            print(f"  Saved figure -> {_save(fig, f'p9_{kind}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Could not render {kind}: {exc}")


def _score_case(name: str, axis: str) -> int:
    """Rank an OutputCase as a lateral case in ``axis`` (higher = better).

    Prefers a plain static/RS seismic case in the axis (``Sx``, ``EQx``, ``Ex``)
    over eccentric ``+/-`` variants, and rejects modal/gravity cases outright.
    """
    low = name.lower()
    a = axis.lower()
    if a not in low or "modal" in low:
        return -1
    score = 0
    if low in (f"s{a}", f"eq{a}", f"e{a}", f"sismo{a}", f"q{a}"):
        score += 100  # exact directional seismic case
    if low.startswith(("s", "e", "q")):
        score += 20
    if low.endswith(("+", "-")):
        score -= 30  # eccentric variant — deprioritise
    if any(t in low for t in ("elast", "din", "din", "resp")):
        score += 5
    score -= len(name)  # prefer the simplest name
    return score


def _lateral_cases(e: apeETABS, table: str) -> dict[str, str | None]:
    """Best-effort pick of an X and a Y lateral case from ``table``.

    Soft story / torsion are per-direction-per-case (``StiffY`` reads ~0 under an
    X case), so we need the X lateral case for X and the Y case for Y. Cases are
    scored by :func:`_score_case`; modal/gravity cases are rejected.
    """
    out: dict[str, str | None] = {"X": None, "Y": None}
    try:
        df = e.tables.get(table, numeric=True)
    except Exception:  # noqa: BLE001
        return out
    if df.empty or "OutputCase" not in df.columns:
        return out
    cases = [str(c) for c in df["OutputCase"].unique()]
    for axis in ("X", "Y"):
        ranked = sorted(((c, _score_case(c, axis)) for c in cases),
                        key=lambda kv: kv[1], reverse=True)
        out[axis] = ranked[0][0] if ranked and ranked[0][1] >= 0 else None
    print(f"  Lateral cases picked from '{table}': {out}  (all: {cases})")
    return out


def _validate_soft_story(e: apeETABS, *, case: str | None, combo: str | None) -> None:
    _rule("P9 — STORY STIFFNESS  (soft story Type 1a/1b)")
    # Soft story is per-direction-per-case; pick Sx for X and Sy for Y unless the
    # caller forced an explicit case/combo.
    picks = _lateral_cases(e, "Story Stiffness")
    for direction in ("X", "Y"):
        sel_case = case or picks.get(direction)
        sel_combo = combo
        if sel_case is None and sel_combo is None:
            print(f"  No lateral case found for {direction}; skipping.")
            continue
        try:
            snap = StoryStiffness.from_table(e, case=sel_case, combo=sel_combo)
            print(f"\n  Soft story, direction {direction} (case={snap.case!r}):")
            print(snap.soft_story(direction=direction)
                  .to_string(index=False).replace("\n", "\n    "))
            fig, _ = e.plot.soft_story(snap, direction=direction)
            print(f"  Saved figure -> {_save(fig, f'p9_soft_story_{direction}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  soft_story({direction}) failed: {exc}")


def _validate_torsion(e: apeETABS, *, case: str | None, combo: str | None) -> None:
    _rule("P9 — TORSIONAL IRREGULARITY  (TIR Type 1a/1b)")
    picks = _lateral_cases(e, "Story Max Over Avg Drifts")
    for direction in ("X", "Y"):
        sel_case = case or picks.get(direction)
        sel_combo = combo
        if sel_case is None and sel_combo is None:
            print(f"  No lateral case found for {direction}; skipping.")
            continue
        try:
            snap = TorsionIrregularity.from_table(e, case=sel_case, combo=sel_combo)
            print(f"\n  Torsion ratios, direction {direction} (case={snap.case!r}):")
            print(snap.ratios(direction=direction)
                  .to_string(index=False).replace("\n", "\n    "))
            fig, _ = e.plot.torsional_irregularity(snap, direction=direction)
            print(f"  Saved figure -> "
                  f"{_save(fig, f'p9_torsional_irregularity_{direction}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ratios({direction}) failed: {exc}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live validation of the read + P9 stack.")
    p.add_argument("--model", default=None,
                   help="Path to a .EDB to LAUNCH+open. Omit to attach to a "
                        "running ETABS instance.")
    p.add_argument("--pid", type=int, default=None,
                   help="Attach to a specific ETABS process id (use when the "
                        "active-object attach returns None, a known ETABS quirk).")
    p.add_argument("--analyze", action="store_true",
                   help="Run analysis first if the model is not yet analyzed "
                        "(unlocked). No-op on an already-analyzed model.")
    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--case", default=None, help="OutputCase (fuzzy-matched).")
    sel.add_argument("--combo", default=None, help="Load combination (fuzzy).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    _rule("CONNECT")
    try:
        if args.model:
            print(f"  Launching ETABS and opening: {args.model}")
            e = apeETABS(path=args.model, verbose=True).connect()
        elif args.pid is not None:
            print(f"  Attaching to ETABS process id {args.pid}...")
            e = apeETABS(process_id=args.pid, verbose=True).connect()
        else:
            print("  Attaching to the running ETABS instance...")
            e = apeETABS(attach=True, verbose=True).connect()
    except Exception as exc:  # noqa: BLE001
        print(f"  Could not connect to ETABS: {exc}")
        print("  Open a model in ETABS and retry, or pass --model PATH.")
        return 1

    try:
        try:
            print(f"  Model locked (analysis run?): {e.is_locked}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Could not read lock state: {exc}")

        _maybe_analyze(e, requested=args.analyze)
        e.units.use_report_system()

        pairs = _dump_available(e)
        _dump_schema(e, pairs)

        # Only an EXPLICIT --case/--combo overrides the per-direction lateral
        # pick; the auto-discovered case (often 'Modal') must NOT poison the
        # soft-story / torsion checks, which need the seismic case per axis.
        _rule("CASE DISCOVERY (informational only)")
        _discover_case(e)

        _validate_cm_cr(e)
        _validate_soft_story(e, case=args.case, combo=args.combo)
        _validate_torsion(e, case=args.case, combo=args.combo)

        _rule("DONE")
        print(f"  Figures (if any) saved under {_OUT_DIR}")
        print("  Compare the printed schemas against the # LIVE-CONFIRM column "
              "maps in results/CentersMassRigidity.py, StoryStiffness.py, "
              "TorsionIrregularity.py.")
    finally:
        # We launched it only if --model was given; end() closes ours, leaves
        # an attached instance running. Never save (read-only validation).
        e.end(save=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
