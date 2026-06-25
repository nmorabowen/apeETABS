"""Live gate for the geometry extractor + exporter (ADR 0009, W1+W2).

Launches ETABS, opens a reference ``.EDB``, and:

1. **Count gate** — compares ``e.geometry`` point/frame/area counts against
   ETABS' own ``Count()`` (the authoritative object counts). This is the
   ADR 0009 Phase-1 verification.
2. **Full export** — assembles the ``StructuralModel``, validates it against the
   schema, and writes ``<model>.sm.json``. Reported separately so a fidelity
   edge (e.g. an unsupported section) never masks the count gate.

Run with the venv python that has apeETABS + comtypes, against an installed,
licensed ETABS (no live ETABS in CI — this is a manual run):

    python scripts/live_export.py "reference models/Casa 17B RevA.EDB"
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from apeETABS import apeETABS

DEFAULT_MODEL = "reference models/Casa 17B RevA.EDB"


def count_gate(e) -> bool:
    sap = e.SapModel
    geo = e.geometry
    checks = [
        ("points", len(geo.points()), int(sap.PointObj.Count())),
        ("frames", len(geo.frames()), int(sap.FrameObj.Count("All"))),
        ("areas", len(geo.areas()), int(sap.AreaObj.Count())),
    ]
    print(f"\n{'object':<10}{'extracted':>12}{'ETABS.Count':>14}{'':>4}")
    print("-" * 40)
    ok_all = True
    for name, extracted, etabs in checks:
        match = extracted == etabs
        ok_all &= match
        print(f"{name:<10}{extracted:>12}{etabs:>14}{'  OK' if match else '  ✗ MISMATCH'}")
    print("-" * 40)
    print("COUNT GATE:", "PASS" if ok_all else "FAIL")
    return ok_all


def full_export(e, out: Path):
    try:
        model = e.export.structural_model(out)  # validates + writes
        dia_nodes = sum(len(d.nodes) for d in model.diaphragms)
        print(
            f"\nFULL EXPORT: PASS -> {out.name}\n"
            f"  sections={len(model.sections)} materials={len(model.materials)} "
            f"restraints={len(model.restraints)} springs={len(model.springs)} "
            f"diaphragms={len(model.diaphragms)} (nodes={dia_nodes}) "
            f"loads={len(model.loads)}"
        )
        # Per-pattern load breakdown + area-load join-key integrity.
        area_ids = {a.id for a in model.areas}
        for p in model.loads:
            bad = sorted({a.area for a in p.area if a.area not in area_ids})
            flag = f"  ✗ unknown areas: {bad}" if bad else ""
            print(
                f"    {p.name!r}: nodal={len(p.nodal)} frame={len(p.frame)} "
                f"area={len(p.area)}{flag}"
            )
        return model
    except Exception as exc:  # noqa: BLE001 — report, don't mask the count gate
        print(f"\nFULL EXPORT: FAILED ({type(exc).__name__}: {exc})")
        traceback.print_exc()
        return None


def loads_probe(e) -> None:
    """Characterize what loads the object-API getters see (diagnostic)."""
    sap = e.SapModel
    pats = sap.LoadPatterns.GetNameList(0, [])[1]
    print(f"\nLOADS PROBE: {len(pats)} load patterns: {list(pats)}")
    geo = e.geometry
    n_pt = sum(
        int(sap.PointObj.GetLoadForce(p["id"], 0, [], [], [], [], [], [], [], [], [], [])[0])
        for p in geo.points()
    )
    n_fr = sum(
        int(sap.FrameObj.GetLoadDistributed(f["id"], 0, [], [], [], [], [], [], [], [], [], [])[0])
        for f in geo.frames()
    )
    n_ar = sum(
        int(sap.AreaObj.GetLoadUniform(a["id"], 0, [], [], [], [])[0])
        for a in geo.areas()
    )
    print(f"  assigned items -> point-force={n_pt} frame-distributed={n_fr} area-uniform={n_ar}")


def main() -> int:
    model_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL).resolve()
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return 2

    out = model_path.with_suffix(".sm.json")
    print(f"Opening {model_path.name} (launching ETABS)...")
    with apeETABS(path=model_path, verbose=True) as e:
        e.units.set("kN", "m")
        gate = count_gate(e)
        full_export(e, out)
        loads_probe(e)
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
