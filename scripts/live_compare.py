"""Live gate for the solve cross-check (ADR 0009): apeGmsh vs ETABS.

Opens a reference ``.EDB``, runs the ETABS analysis, then for one load case:

1. **ETABS side** — pins units, exports ``<model>.sm.json``, and reads ETABS'
   own joint **displacements** and **reactions** (``e.results``).
2. **apeGmsh side** — solves the exported ``.sm.json`` for the same case
   (``apeGmsh.interop.solve_and_extract``) and reads back the same quantities,
   keyed by the shared ETABS joint id.
3. **Compare** — prints a per-DOF agreement report for each quantity
   (``apeETABS.crosscheck``).

Both sides are in the ``.sm.json`` units (kN, m here); the comparator does not
convert. apeGmsh meshes the shells/frames finer than ETABS' own elements, so
expect discretization-level differences — read the reported ``max_rel``, don't
over-trust a single tolerance.

Manual run (needs a licensed, installed ETABS + the apeGmsh package; no live
ETABS in CI):

    python scripts/live_compare.py "reference models/Casa 17B RevA.EDB" \
        --case "Carga Muerta" --rtol 0.05 --size 1.0
"""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from apeETABS import apeETABS
from apeETABS.crosscheck import DISP_DOFS, REACTION_DOFS, compare

DEFAULT_MODEL = "reference models/Casa 17B RevA.EDB"


def _run_analysis(e) -> None:
    """Run the ETABS analysis if results aren't already available."""
    sap = e.SapModel
    try:
        sap.Analyze.RunAnalysis()
    except Exception as exc:  # noqa: BLE001 — report, keep going (may be analyzed)
        print(f"  (RunAnalysis raised {type(exc).__name__}: {exc}; "
              f"assuming the model is already analyzed)")


def _etabs_results(e, case: str):
    """ETABS joint displacements + reactions for ``case`` as ``{id: vec6}``."""
    disp = e.results.displacements(case=case).by_joint()
    react = e.results.reactions(case=case).by_joint()
    return disp, react


def _apegmsh_results(sm_json: Path, case: str, size: float):
    """apeGmsh solve of the exported model for ``case``."""
    from apeGmsh.interop import solve_and_extract

    res = solve_and_extract(sm_json, case=case, global_size=size)
    if not res.converged:
        print("  ✗ apeGmsh solve did NOT converge")
    print(f"  apeGmsh: {res.n_mesh_nodes} mesh nodes, "
          f"{len(res.displacements)} joints, {len(res.reactions)} reactions")
    return res.displacements, res.reactions


def main() -> int:
    ap = argparse.ArgumentParser(description="apeGmsh-vs-ETABS solve cross-check")
    ap.add_argument("model", nargs="?", default=DEFAULT_MODEL)
    ap.add_argument("--case", required=True, help="load pattern/case name (both sides)")
    ap.add_argument("--rtol", type=float, default=0.05, help="relative tolerance")
    ap.add_argument("--atol", type=float, default=1e-6, help="absolute tolerance")
    ap.add_argument("--size", type=float, default=1.0, help="apeGmsh mesh size")
    args = ap.parse_args()

    model_path = Path(args.model).resolve()
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return 2
    out = model_path.with_suffix(".sm.json")

    print(f"Opening {model_path.name} (launching ETABS)...")
    with apeETABS(path=model_path, verbose=True) as e:
        e.units.set("kN", "m")
        print("Running ETABS analysis...")
        _run_analysis(e)

        print(f"Exporting {out.name}...")
        e.export.structural_model(out)

        try:
            etabs_disp, etabs_react = _etabs_results(e, args.case)
        except Exception as exc:  # noqa: BLE001
            print(f"ETABS results extraction FAILED ({type(exc).__name__}: {exc})")
            traceback.print_exc()
            return 1

    print("Solving in apeGmsh...")
    try:
        ag_disp, ag_react = _apegmsh_results(out, args.case, args.size)
    except Exception as exc:  # noqa: BLE001
        print(f"apeGmsh solve FAILED ({type(exc).__name__}: {exc})")
        traceback.print_exc()
        return 1

    disp_report = compare(
        etabs_disp, ag_disp, dof_labels=DISP_DOFS,
        rtol=args.rtol, atol=args.atol, quantity="displacements",
    )
    react_report = compare(
        etabs_react, ag_react, dof_labels=REACTION_DOFS,
        rtol=args.rtol, atol=args.atol, quantity="reactions",
    )
    print(f"\n=== Cross-check (case {args.case!r}) ===")
    print(disp_report)
    print(react_report)
    return 0 if (disp_report.passed and react_report.passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
