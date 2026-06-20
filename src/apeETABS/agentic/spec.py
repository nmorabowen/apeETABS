"""The abstract :class:`Spec` — the declarative agent interface (ADR 0007 §1).

Agents author and edit **serializable specs**, never raw composites or COM.
A spec is simultaneously the agent's output, the human review surface and the
safety boundary. Every concrete spec implements the same three verbs against a
connected session ``e`` and declares a risk :attr:`tier` (ADR 0007 §3):

* :meth:`validate` — references / units / invariants, *before any ETABS call*.
* :meth:`plan`     — a dry-run: the ordered operations as data, nothing applied.
* :meth:`run`      — execute via the imperative results/creation/editing layers.

All three return a typed, JSON-serializable :class:`~apeETABS.agentic.outcomes.Outcome`
(ADR 0007 §4). :meth:`to_dict` / :meth:`from_dict` make the spec itself
serializable — the reserved schema/manifest seam (ADR 0007 §5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from .outcomes import Outcome

if TYPE_CHECKING:
    from .._session import _SessionBase


class Spec(ABC):
    """Abstract base for every agentic spec (report / model / edit).

    Subclasses set :attr:`tier` to one of ``read`` / ``create`` / ``edit`` /
    ``destructive`` (the gating tier, ADR 0007 §3) and implement the three
    verbs plus :meth:`to_dict` / :meth:`from_dict`.
    """

    #: Risk tier for the approval gate; overridden per concrete spec.
    tier: ClassVar[str] = "read"

    #: Stable spec-type tag for the (reserved) capability manifest / round-trip.
    kind: ClassVar[str] = "spec"

    # ------------------------------------------------------------------
    # Pipeline verbs (ADR 0007 §2). Each returns a structured Outcome.
    # ------------------------------------------------------------------

    @abstractmethod
    def validate(self, e: "_SessionBase") -> Outcome:
        """Check references / units / invariants *before any ETABS mutation*.

        Returns an :class:`Outcome` whose ``ok`` is False (with structured
        findings) on any problem; no ETABS state is changed.
        """
        raise NotImplementedError

    @abstractmethod
    def plan(self, e: "_SessionBase") -> Outcome:
        """Dry-run: return the ordered operations / diff as data, applying nothing."""
        raise NotImplementedError

    @abstractmethod
    def run(self, e: "_SessionBase", *, policy) -> Outcome:
        """Execute the spec via the imperative layer (results/creation/editing).

        Called by the pipeline only after validate + plan + the gate pass.
        ``policy`` is the governing :class:`~apeETABS.agentic.policy.AgentPolicy`.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Serialization (reserved schema/manifest seam, ADR 0007 §5).
    # ------------------------------------------------------------------

    @abstractmethod
    def to_dict(self) -> dict:
        """Return a JSON-serializable view of this spec (includes ``kind``/``tier``)."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "Spec":
        """Rebuild a spec from its :meth:`to_dict` form."""
        raise NotImplementedError
