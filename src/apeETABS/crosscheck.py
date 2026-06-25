"""Solve cross-check — compare two joint-keyed result sets (ADR 0009).

A dependency-free comparator for validating the apeGmsh solver against ETABS'
own analysis: both sides expose ``{joint_id: (d1..d6)}`` (displacements or
reactions) keyed by the shared ETABS joint id, and :func:`compare` reports the
per-DOF agreement and an overall pass/fail.

Pure numerics — no pandas, no COM. The orchestration that produces the two
inputs (live ETABS via ``e.results`` + apeGmsh ``solve_and_extract``) lives in
``scripts/live_compare.py``; this module is what it (and the tests) call.

Both inputs must be in the **same unit system** (the ``.sm.json`` units the
model was exported in) — the comparator does not convert.
"""

from __future__ import annotations

from dataclasses import dataclass

JointMap = dict[str, tuple[float, ...]]

DISP_DOFS = ("Ux", "Uy", "Uz", "Rx", "Ry", "Rz")
REACTION_DOFS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


@dataclass(frozen=True)
class DofError:
    """Per-DOF agreement across the common joints."""
    dof: str
    max_abs: float          # largest |candidate - reference|
    max_rel: float          # largest relative error (inf if ref~0 and cand isn't)
    worst_joint: str        # joint driving max_rel
    n_fail: int             # joints failing BOTH atol and rtol


@dataclass(frozen=True)
class ComparisonReport:
    """Outcome of comparing a candidate result set against a reference."""
    quantity: str
    dof_labels: tuple[str, ...]
    errors: list[DofError]
    n_compared: int
    missing: list[str]      # reference joints absent from the candidate
    extra: list[str]        # candidate joints absent from the reference
    rtol: float
    atol: float

    @property
    def passed(self) -> bool:
        """All DOFs within tolerance on every common joint, none missing."""
        return not self.missing and all(e.n_fail == 0 for e in self.errors)

    def __str__(self) -> str:
        head = (
            f"{self.quantity}: {'PASS' if self.passed else 'FAIL'}  "
            f"({self.n_compared} joints, rtol={self.rtol:g}, atol={self.atol:g})"
        )
        rows = [
            f"  {e.dof:>3}  max_abs={e.max_abs:.4g}  max_rel={e.max_rel:.4g}"
            f"  worst={e.worst_joint or '-'}  fail={e.n_fail}"
            for e in self.errors
        ]
        if self.missing:
            rows.append(f"  missing {len(self.missing)} joint(s): {self.missing[:10]}")
        if self.extra:
            rows.append(f"  extra {len(self.extra)} joint(s): {self.extra[:10]}")
        return "\n".join([head, *rows])


def compare(
    reference: JointMap,
    candidate: JointMap,
    *,
    dof_labels: tuple[str, ...] = DISP_DOFS,
    rtol: float = 0.02,
    atol: float = 1e-9,
    quantity: str = "result",
) -> ComparisonReport:
    """Compare ``candidate`` against ``reference``, both ``{joint: (d1..dn)}``.

    A joint/DOF passes when ``|cand - ref| <= atol`` (negligible) OR
    ``|cand - ref| / |ref| <= rtol``. ``reference`` is the trusted side (ETABS);
    its zero entries make the relative error undefined, so there the absolute
    ``atol`` governs. Joints present on only one side are reported, never
    silently compared; any missing reference joint fails the report.
    """
    common = sorted(set(reference) & set(candidate))
    ndof = len(dof_labels)
    errors: list[DofError] = []
    for d in range(ndof):
        max_abs = 0.0
        max_rel = 0.0
        worst = ""
        n_fail = 0
        for k in common:
            rv = float(reference[k][d])
            cv = float(candidate[k][d])
            ad = abs(cv - rv)
            if abs(rv) > atol:
                rd = ad / abs(rv)
            else:
                rd = 0.0 if ad <= atol else float("inf")
            max_abs = max(max_abs, ad)
            if rd > max_rel:
                max_rel, worst = rd, k
            if ad > atol and rd > rtol:
                n_fail += 1
        errors.append(DofError(dof_labels[d], max_abs, max_rel, worst, n_fail))

    return ComparisonReport(
        quantity=quantity,
        dof_labels=tuple(dof_labels),
        errors=errors,
        n_compared=len(common),
        missing=sorted(set(reference) - set(candidate)),
        extra=sorted(set(candidate) - set(reference)),
        rtol=rtol,
        atol=atol,
    )
