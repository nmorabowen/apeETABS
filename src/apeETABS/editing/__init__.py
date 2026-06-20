"""Editing layer (ADR 0005): the ``e.edit`` / ``e.assign`` composites.

Public surface:

* :class:`~apeETABS.editing.Edit.Edit` — the ``e.edit`` geometry/topology
  editor (rename/delete implemented; move/divide/replicate stubbed).
* :class:`~apeETABS.editing.Assign.Assign` — the ``e.assign`` property/load
  assigner (restraint implemented; modifiers/releases/loads stubbed).

Both guard every mutation via ``e._require_unlocked`` (ADR 0005 §2) — the
model is never unlocked implicitly.
"""

from __future__ import annotations

from .Assign import Assign
from .Edit import Edit

__all__ = [
    "Edit",
    "Assign",
]
