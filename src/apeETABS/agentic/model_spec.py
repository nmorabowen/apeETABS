"""``ModelSpec`` — the create-tier model spec (skeleton, ADR 0007 §7).

Greenfield model creation: an agent emits a ``ModelSpec`` describing materials,
sections, grids and members; the engine validates references, plans the build
order, then runs it via the creation layer (ADR 0006). Only the *shape* is
fixed here — the field-level schema is deferred (ADR 0007 intro). The verbs
raise :class:`NotImplementedError` where unimplemented so the seam is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .outcomes import Outcome
from .spec import Spec

if TYPE_CHECKING:
    from .._session import _SessionBase


@dataclass
class ModelSpec(Spec):
    """Declarative greenfield model (create tier). Skeleton — verbs stubbed.

    Attributes:
        definitions: Placeholder for materials/sections/load-patterns (the
            ``e.define`` surface, ADR 0006). Schema deferred.
        members: Placeholder for points/frames/areas to create. Schema deferred.
    """

    tier: ClassVar[str] = "create"
    kind: ClassVar[str] = "model"

    definitions: dict = field(default_factory=dict)
    members: list[dict] = field(default_factory=list)

    def validate(self, e: "_SessionBase") -> Outcome:
        """Check material/section references resolve before any creation call.

        Not implemented yet — P8 ships the create-tier *skeleton*; the
        reference-resolution rules (e.g. ``UNKNOWN_SECTION`` + remediation
        hint, ADR 0007 §4) land with the creation layer (ADR 0006).
        """
        raise NotImplementedError(
            "ModelSpec.validate is not implemented yet (P8 ships the "
            "create-tier skeleton; creation lands with ADR 0006)."
        )

    def plan(self, e: "_SessionBase") -> Outcome:
        """Dry-run the ordered build (define -> grids -> members), as data.

        Not implemented yet (see :meth:`validate`).
        """
        raise NotImplementedError(
            "ModelSpec.plan is not implemented yet (P8 ships the create-tier "
            "skeleton)."
        )

    def run(self, e: "_SessionBase", *, policy) -> Outcome:
        """Build the model via the creation layer, then save.

        Not implemented yet (see :meth:`validate`).
        """
        raise NotImplementedError(
            "ModelSpec.run is not implemented yet (P8 ships the create-tier "
            "skeleton)."
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "tier": self.tier,
            "definitions": dict(self.definitions),
            "members": [dict(m) for m in self.members],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelSpec":
        return cls(
            definitions=dict(data.get("definitions", {})),
            members=[dict(m) for m in data.get("members", [])],
        )
