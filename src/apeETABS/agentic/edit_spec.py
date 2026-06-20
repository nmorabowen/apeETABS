"""``EditSpec`` — the edit-tier spec (skeleton, ADR 0007 §7).

Mutating an existing model: an agent emits an ``EditSpec`` describing edits to
named objects (rename / move / assign / delete); the engine validates targets,
plans a diff/preview, and — behind the mandatory edit-tier gate (ADR 0007 §3)
plus a consented unlock if results would be discarded (ADR 0005) — applies them
via the editing layer. Destructive edits (delete, results-discarding unlock)
push the effective tier to ``destructive`` and are never auto-approved.

Only the *shape* is fixed here; verbs raise :class:`NotImplementedError` where
unimplemented so the seam is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .outcomes import Outcome
from .spec import Spec

if TYPE_CHECKING:
    from .._session import _SessionBase


@dataclass
class EditSpec(Spec):
    """Declarative edits to an existing model (edit tier). Skeleton — stubbed.

    Attributes:
        target: Placeholder for the object selection (name/kind/group; the
            ``eItemType`` targeting of ADR 0005). Schema deferred.
        edits: Placeholder for the ordered edits to apply. Schema deferred.
    """

    tier: ClassVar[str] = "edit"
    kind: ClassVar[str] = "edit"

    target: dict = field(default_factory=dict)
    edits: list[dict] = field(default_factory=list)

    def validate(self, e: "_SessionBase") -> Outcome:
        """Check edit targets exist and flag results-discarding unlocks.

        Not implemented yet — P8 ships the edit-tier *skeleton*. The target
        resolution and the destructive-tier escalation (delete / unlock with
        results loss, ADR 0005 §2) land with the editing layer.
        """
        raise NotImplementedError(
            "EditSpec.validate is not implemented yet (P8 ships the edit-tier "
            "skeleton; edits land via ADR 0005)."
        )

    def plan(self, e: "_SessionBase") -> Outcome:
        """Produce a diff/preview of the edits, as data, applying nothing.

        Not implemented yet (see :meth:`validate`).
        """
        raise NotImplementedError(
            "EditSpec.plan is not implemented yet (P8 ships the edit-tier "
            "skeleton)."
        )

    def run(self, e: "_SessionBase", *, policy) -> Outcome:
        """Apply the edits via the editing layer (consented unlock if needed).

        Not implemented yet (see :meth:`validate`).
        """
        raise NotImplementedError(
            "EditSpec.run is not implemented yet (P8 ships the edit-tier "
            "skeleton)."
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "tier": self.tier,
            "target": dict(self.target),
            "edits": [dict(ed) for ed in self.edits],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EditSpec":
        return cls(
            target=dict(data.get("target", {})),
            edits=[dict(ed) for ed in data.get("edits", [])],
        )
