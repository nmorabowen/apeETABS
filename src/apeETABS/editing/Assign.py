"""``Assign`` composite — property/load assignments on existing objects.

The ``e.assign`` surface (ADR 0005 §5): set restraints, releases, modifiers,
loads, etc. on objects that already exist. This same surface is shared with
model creation (ADR 0006) — the API is identical whether the object was just
created or already existed.

Bulk operations target via :class:`_Target` (name / group / selection ->
``eItemType``, ADR 0005 §4). Every mutating method calls
``self._parent._require_unlocked(...)`` (ADR 0005 §2: never unlock
implicitly) and routes each COM return through ``ok()`` (§6, fail-loud).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from ..errors import ok
from ._target import _Target

if TYPE_CHECKING:
    from .._session import _SessionBase


class Assign:
    """Property/load assignments (restraints, …) on existing objects."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Implemented assignments
    # ------------------------------------------------------------------

    def restraint(
        self,
        target: str | None = None,
        dofs: Sequence[bool] | None = None,
        *,
        group: str | None = None,
        selected: bool = False,
    ) -> None:
        """Assign point restraints via ``cPointObj.SetRestraint``.

        Args:
            target: A single point's unique name (``eItemType.Objects``).
            dofs: The six restraint flags ``[Ux, Uy, Uz, Rx, Ry, Rz]``;
                ``True`` = restrained. Required.
            group: Target a group of points instead (``eItemType.Group``).
            selected: Target the GUI selection (``eItemType.SelectedObjects``).

        Exactly one of ``target`` / ``group`` / ``selected`` must be given.
        """
        if dofs is None:
            raise ValueError("restraint() requires dofs=[Ux,Uy,Uz,Rx,Ry,Rz].")
        values = [bool(d) for d in dofs]
        if len(values) != 6:
            raise ValueError(
                f"dofs must have 6 entries [Ux,Uy,Uz,Rx,Ry,Rz], got {len(values)}."
            )
        tgt = _Target.resolve(target, group=group, selected=selected)
        self._parent._require_unlocked(f"assign restraint to {tgt.name or 'selection'!r}")
        ok(
            self._parent.SapModel.PointObj.SetRestraint(
                tgt.name, values, tgt.item_type
            ),
            f"SetRestraint {tgt.name or 'selection'!r}",
        )

    # ------------------------------------------------------------------
    # Stubs — documented, not yet implemented (ADR 0005 §5).
    # ------------------------------------------------------------------

    def modifiers(self, *args, **kwargs):
        """Assign property modifiers (wraps ``cFrameObj/cAreaObj.SetModifiers``).

        Not implemented yet — P6 ships ``restraint`` only.
        """
        raise NotImplementedError(
            "Assign.modifiers is not implemented yet (P6 ships restraint only)."
        )

    def releases(self, *args, **kwargs):
        """Assign frame end releases (wraps ``cFrameObj.SetReleases``).

        Not implemented yet — P6 ships ``restraint`` only.
        """
        raise NotImplementedError(
            "Assign.releases is not implemented yet (P6 ships restraint only)."
        )

    def loads(self, *args, **kwargs):
        """Assign point/frame/area loads (wraps the ``Set*Load*`` setters).

        Not implemented yet — P6 ships ``restraint`` only.
        """
        raise NotImplementedError(
            "Assign.loads is not implemented yet (P6 ships restraint only)."
        )
