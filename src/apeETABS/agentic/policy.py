"""Agent policy + the risk-tier gate (ADR 0007 §3).

A single :class:`AgentPolicy` governs the approval gate by **risk tier**.
Every spec declares a tier (``read`` / ``create`` / ``edit`` /
``destructive``); :meth:`AgentPolicy.gate` answers one question — *may this
tier run automatically, without explicit human approval?*

The tiering is the safety boundary (ADR 0007, alternative 3):

* ``read``        — read-only (report creation): auto-run.
* ``create``      — greenfield model: auto-run allowed (approval optional).
* ``edit``        — mutate an existing model: gated unless ``allow_edit`` and
                    approval is not required.
* ``destructive`` — delete / unlock-with-results-loss: **never** auto,
                    regardless of policy.
"""

from __future__ import annotations

from dataclasses import dataclass

# The recognized risk tiers, lowest to highest. ``destructive`` is special:
# it is never auto-gateable (see :meth:`AgentPolicy.gate`).
TIERS = ("read", "create", "edit", "destructive")


class UnknownTierError(ValueError):
    """Raised when a spec declares a tier outside :data:`TIERS`."""


@dataclass
class AgentPolicy:
    """Policy controlling the pipeline's approval gate (ADR 0007 §3).

    Attributes:
        allow_edit: Permit the ``edit`` tier to auto-run. Off by default —
            editing is mutating and gated unless explicitly allowed.
        require_approval: When True, only ``read`` (and ``create``) may
            auto-run; ``edit`` always needs explicit approval even if
            ``allow_edit`` is set.
        dry_run_default: Whether callers should default to plan-only (no
            mutation) when unspecified. The pipeline honors this as guidance.
    """

    allow_edit: bool = False
    require_approval: bool = True
    dry_run_default: bool = True

    def gate(self, tier: str) -> bool:
        """Return whether ``tier`` may run automatically (no human approval).

        ``destructive`` always returns ``False`` (ADR 0007 §3: never auto,
        regardless of policy). ``read`` and ``create`` auto-run. ``edit``
        auto-runs only when ``allow_edit`` is set *and* approval is not
        required.

        Raises:
            UnknownTierError: If ``tier`` is not one of :data:`TIERS`.
        """
        if tier not in TIERS:
            raise UnknownTierError(
                f"Unknown risk tier {tier!r}; expected one of {list(TIERS)}."
            )
        if tier == "destructive":
            return False  # never auto — always confirmed.
        if tier == "edit":
            return self.allow_edit and not self.require_approval
        # read / create: auto-run.
        return True
