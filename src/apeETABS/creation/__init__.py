"""Creation layer (ADR 0006): the imperative builder tier.

Public surface:

* :class:`~apeETABS.creation.New.New` — the ``e.new`` template starters
  (``blank`` / ``grid_only`` / ``steel_deck``) wrapping ``cFile.New*``.
* :class:`~apeETABS.creation.Define.Define` — the ``e.define`` model dictionary
  (material / frame_rect / load_pattern implemented; section/combo/diaphragm
  stubbed).
* :class:`~apeETABS.creation.Create.Create` — the ``e.create`` geometry creator
  (point / frame_by_coord implemented; area stubbed).
* :class:`~apeETABS.creation.FrameHandle.FrameHandle` — the thin value handle
  returned by ``create.frame_by_coord`` (name + resolved I/J point names).

Inbound numbers are **present-units-as-contract** (ADR 0006 §3): values are in
the model's present units; authoring them with ``baseUnits`` (e.g. ``depth=0.6``
metres) is the recommended way to make intent explicit. Every mutating
define/create method guards via ``e._require_unlocked`` (ADR 0005 §2).

The declarative ``ModelSpec`` tier (ADR 0006 §1/§5 — ``validate``/``plan``/
``run``/serialization) is **DEFERRED**: only the imperative engine ships here.

.. TODO(ADR 0006 §5 — ModelSpec, deferred): add the declarative ``@dataclass``
   tree (template/materials/sections/members/assigns) that *compiles to* these
   builders via ``ModelSpec.run(e)`` / ``plan(e)`` / ``validate()``. It is the
   front door, not a second engine — do not duplicate builder logic here.
"""

from __future__ import annotations

from .Create import Create
from .Define import Define
from .FrameHandle import FrameHandle
from .New import New

__all__ = [
    "Define",
    "Create",
    "New",
    "FrameHandle",
]
