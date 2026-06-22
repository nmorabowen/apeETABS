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

from ..errors import ETABSError, ok
from ._target import _Target

if TYPE_CHECKING:
    from .._session import _SessionBase

# ETABS load direction codes (cFrameObj/cAreaObj/cPointObj ``Dir`` argument).
_DIR = {
    "Local1": 1, "Local2": 2, "Local3": 3,
    "X": 4, "Y": 5, "Z": 6,
    "ProjX": 7, "ProjY": 8, "ProjZ": 9,
    "Gravity": 10, "ProjGravity": 11,
}
# Distributed-load value type (cFrameObj.SetLoadDistributed ``MyType``).
_LOAD_TYPE = {"force": 1, "moment": 2}


def _resolve_dir(direction: "int | str") -> int:
    """Map a direction name (``"Gravity"``, ``"X"``…) or raw code to its int."""
    if isinstance(direction, int):
        return direction
    try:
        return _DIR[str(direction)]
    except KeyError:
        valid = ", ".join(_DIR)
        raise ETABSError(
            f"Unknown direction '{direction}'. Use one of: {valid} (or an int)."
        ) from None


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

    def point_force(
        self,
        target: str | None = None,
        *,
        pattern: str,
        fx: float = 0.0,
        fy: float = 0.0,
        fz: float = 0.0,
        mx: float = 0.0,
        my: float = 0.0,
        mz: float = 0.0,
        replace: bool = True,
        csys: str = "Global",
        group: str | None = None,
        selected: bool = False,
    ) -> None:
        """Assign a point force/moment to ``pattern`` via ``SetLoadForce``.

        ``fx..mz`` are the six load components ``[Fx,Fy,Fz,Mx,My,Mz]`` in
        ``csys`` (default Global). Target one ``target`` name, a ``group``, or
        the ``selected`` objects (exactly one).
        """
        value = [float(fx), float(fy), float(fz), float(mx), float(my), float(mz)]
        tgt = _Target.resolve(target, group=group, selected=selected)
        self._parent._require_unlocked(
            f"assign point load to {tgt.name or 'selection'!r}"
        )
        ok(
            self._parent.SapModel.PointObj.SetLoadForce(
                tgt.name, pattern, value, bool(replace), csys, tgt.item_type
            ),
            f"SetLoadForce {tgt.name or 'selection'!r}",
        )

    def frame_distributed(
        self,
        target: str | None = None,
        *,
        pattern: str,
        value: float,
        direction: "int | str" = "Gravity",
        kind: str = "force",
        dist1: float = 0.0,
        dist2: float = 1.0,
        val_start: float | None = None,
        val_end: float | None = None,
        rel_dist: bool = True,
        replace: bool = True,
        csys: str = "Global",
        group: str | None = None,
        selected: bool = False,
    ) -> None:
        """Assign a distributed frame load via ``SetLoadDistributed``.

        Uniform by default (``val_start``/``val_end`` default to ``value``);
        pass both for a trapezoidal load over ``dist1``..``dist2`` (relative
        distance when ``rel_dist``). ``direction`` is a name (``"Gravity"``,
        ``"X"``…) or raw ETABS code; ``kind`` is ``"force"`` or ``"moment"``.
        """
        my_type = _LOAD_TYPE.get(str(kind).lower())
        if my_type is None:
            raise ETABSError(
                f"Unknown load kind '{kind}'. Use 'force' or 'moment'."
            )
        d = _resolve_dir(direction)
        v1 = float(value if val_start is None else val_start)
        v2 = float(value if val_end is None else val_end)
        tgt = _Target.resolve(target, group=group, selected=selected)
        self._parent._require_unlocked(
            f"assign frame load to {tgt.name or 'selection'!r}"
        )
        ok(
            self._parent.SapModel.FrameObj.SetLoadDistributed(
                tgt.name, pattern, my_type, d, float(dist1), float(dist2),
                v1, v2, csys, bool(rel_dist), bool(replace), tgt.item_type
            ),
            f"SetLoadDistributed {tgt.name or 'selection'!r}",
        )

    def area_uniform(
        self,
        target: str | None = None,
        *,
        pattern: str,
        value: float,
        direction: "int | str" = "Gravity",
        replace: bool = True,
        csys: str = "Global",
        group: str | None = None,
        selected: bool = False,
    ) -> None:
        """Assign a uniform area load via ``SetLoadUniform``.

        ``value`` in ``direction`` (name or raw code; default downward
        ``"Gravity"``). Target one ``target`` name, a ``group``, or the
        ``selected`` objects (exactly one).
        """
        d = _resolve_dir(direction)
        tgt = _Target.resolve(target, group=group, selected=selected)
        self._parent._require_unlocked(
            f"assign area load to {tgt.name or 'selection'!r}"
        )
        ok(
            self._parent.SapModel.AreaObj.SetLoadUniform(
                tgt.name, pattern, float(value), d, bool(replace), csys,
                tgt.item_type
            ),
            f"SetLoadUniform {tgt.name or 'selection'!r}",
        )
