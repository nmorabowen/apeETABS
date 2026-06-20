"""The one gated execution pipeline (ADR 0007 §2).

Every agentic action — read, create, edit, destructive — flows through the
same sequence::

    propose(spec) -> validate() -> plan() -> [approval gate] -> run() -> record

:func:`run_spec` implements it. It short-circuits on a failed ``validate``,
always produces a ``plan``, then consults the policy gate. On a gated tier
*without* approval it **stops after plan** and returns an Outcome explaining
that approval is required — it does NOT call ``run``. On an auto-run tier (or
when ``approve`` grants it) it runs and folds the plan + run record into the
returned Outcome.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from .outcomes import Finding, Outcome

if TYPE_CHECKING:
    from .._session import _SessionBase
    from .policy import AgentPolicy
    from .spec import Spec


def run_spec(
    spec: "Spec",
    e: "_SessionBase",
    *,
    policy: "AgentPolicy",
    approve: Optional[Callable[["Spec", Outcome], bool]] = None,
) -> Outcome:
    """Drive ``spec`` through the full pipeline against session ``e``.

    Args:
        spec: The spec to execute (declares its risk :attr:`~.spec.Spec.tier`).
        e: The connected session.
        policy: Governs the approval gate (ADR 0007 §3).
        approve: Optional callback ``(spec, plan_outcome) -> bool``. Consulted
            only when the policy gate does *not* auto-allow the tier; returning
            True grants explicit approval. ``None`` means "no approver" — a
            gated tier then stops after plan.

    Returns:
        An :class:`Outcome` carrying the plan operations and, when run, the run
        record. ``data["stage"]`` is the last stage reached
        (``"validate"`` / ``"plan"`` / ``"run"``); ``data["plan"]`` always
        holds the plan operations once produced.
    """
    # 1. validate — before any ETABS call. A failure short-circuits.
    val = spec.validate(e)
    if not val.ok:
        val.data.setdefault("stage", "validate")
        return val

    # 2. plan — dry-run; nothing applied.
    plan = spec.plan(e)
    plan.data.setdefault("stage", "plan")
    plan.data.setdefault("plan", list(plan.operations))
    if not plan.ok:
        return plan

    # 3. approval gate.
    allowed = policy.gate(spec.tier)
    if not allowed and approve is not None:
        allowed = bool(approve(spec, plan))

    if not allowed:
        # Stop after plan: return the plan + a structured "approval required"
        # finding. We deliberately do NOT run.
        return Outcome(
            ok=False,
            operations=list(plan.operations),
            findings=[
                Finding(
                    code="APPROVAL_REQUIRED",
                    message=(
                        f"The {spec.tier!r} tier requires explicit approval; "
                        f"the plan was produced but not run."
                    ),
                    hint=(
                        "Re-run with an approve= callback that returns True, "
                        "or adjust the AgentPolicy (note: the 'destructive' "
                        "tier is never auto-approved)."
                    ),
                    severity="error",
                ),
            ],
            data={"stage": "plan", "plan": list(plan.operations), "gated": True},
        )

    # 4. run — execute via the imperative layer.
    record = spec.run(e, policy=policy)
    record.data.setdefault("stage", "run")
    record.data.setdefault("plan", list(plan.operations))
    return record
