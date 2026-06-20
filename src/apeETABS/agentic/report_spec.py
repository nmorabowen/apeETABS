"""``ReportSpec`` — the read-tier report spec (ADR 0007 §7, the first target).

A minimal-but-real read-tier spec: a list of requested **figures**, each a
small dict describing what to render and for which case. It exercises the full
pipeline against live read-only data:

* :meth:`validate` — confirm each requested ``case`` exists in the model
  (via ``e.results`` / the underlying ``e.tables``) *before* any rendering;
  a miss is reported as a structured :class:`~.outcomes.Finding`.
* :meth:`plan` — list the figures it would render, as data, rendering nothing.
* :meth:`run` — call ``e.results.*`` + ``apeETABS.plotting`` (via ``e.plot``)
  to produce each figure, collecting the ``(fig, ax)`` handles.

Report *assembly* (docx/pdf) is out of scope for the scaffold — this stops at
producing the figures. Read tier: the pipeline auto-runs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .outcomes import Finding, Outcome
from .spec import Spec

if TYPE_CHECKING:
    from .._session import _SessionBase

# figure-kind -> the e.plot sugar method that renders it. Each takes case=.
_FIGURE_KINDS = {
    "drift": "drift",
    "displacement": "displacement",
    "story_shear": "story_shear",
    "story_forces": "story_forces",
}


@dataclass
class ReportSpec(Spec):
    """A read-only report: a set of figures to render for the connected model.

    Attributes:
        figures: List of figure specs. Each is a dict like
            ``{"kind": "drift", "case": "EQX", "direction": "X"}``. ``kind``
            must be one of :data:`_FIGURE_KINDS`; ``case`` names an output
            case/combo that must exist.
        source: Optional model identifier (path/handle) for the run record.
        units: Optional ``(force, length)`` report-unit hint for assembly.
    """

    tier: ClassVar[str] = "read"
    kind: ClassVar[str] = "report"

    figures: list[dict] = field(default_factory=list)
    source: str | None = None
    units: tuple[str, str] | None = None

    # ------------------------------------------------------------------
    # Pipeline verbs
    # ------------------------------------------------------------------

    def validate(self, e: "_SessionBase") -> Outcome:
        """Check every figure's ``kind`` is known and its ``case`` exists."""
        findings: list[Finding] = []
        available = _available_cases(e)
        for i, fig in enumerate(self.figures):
            kind = fig.get("kind")
            if kind not in _FIGURE_KINDS:
                findings.append(
                    Finding(
                        code="UNKNOWN_FIGURE_KIND",
                        message=f"figures[{i}]: unknown kind {kind!r}.",
                        hint=f"Use one of {sorted(_FIGURE_KINDS)}.",
                    )
                )
            case = fig.get("case")
            if case is not None and available is not None and case not in available:
                findings.append(
                    Finding(
                        code="UNKNOWN_CASE",
                        message=(
                            f"figures[{i}]: case {case!r} is not in the model."
                        ),
                        hint=f"Available cases: {sorted(available)}.",
                    )
                )
        ok = not any(f.severity == "error" for f in findings)
        return Outcome(ok=ok, findings=findings, data={"available_cases": sorted(available or [])})

    def plan(self, e: "_SessionBase") -> Outcome:
        """List the figures that would be rendered (no rendering)."""
        ops = [
            f"render {fig.get('kind')} for case={fig.get('case')!r}"
            for fig in self.figures
        ]
        return Outcome(ok=True, operations=ops, data={"figure_count": len(self.figures)})

    def run(self, e: "_SessionBase", *, policy) -> Outcome:
        """Render each figure via ``e.plot.*`` (which uses ``e.results.*``)."""
        ops: list[str] = []
        handles: list = []
        for fig in self.figures:
            method = getattr(e.plot, _FIGURE_KINDS[fig["kind"]])
            kwargs = {k: v for k, v in fig.items() if k != "kind"}
            handles.append(method(**kwargs))
            ops.append(f"rendered {fig['kind']} for case={fig.get('case')!r}")
        return Outcome(
            ok=True,
            operations=ops,
            data={"figures_rendered": len(handles), "source": self.source},
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "tier": self.tier,
            "figures": [dict(f) for f in self.figures],
            "source": self.source,
            "units": list(self.units) if self.units is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReportSpec":
        units = data.get("units")
        return cls(
            figures=[dict(f) for f in data.get("figures", [])],
            source=data.get("source"),
            units=tuple(units) if units is not None else None,
        )


def _available_cases(e: "_SessionBase") -> set[str] | None:
    """Best-effort set of output-case names known to the model.

    Reads the ``OutputCase`` column off the result tables the report can draw
    from. Returns ``None`` (skip the existence check) only if no such table is
    readable, so validate never blocks on a discovery gap.
    """
    cases: set[str] = set()
    found = False
    for table in ("Story Drifts", "Joint Displacements", "Story Forces"):
        try:
            df = e.tables.get(table, numeric=False)
        except Exception:  # noqa: BLE001 — a missing table must not crash validate.
            continue
        if "OutputCase" in df.columns:
            found = True
            cases.update(str(c) for c in df["OutputCase"].unique())
    return cases if found else None
