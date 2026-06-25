"""Export composite (``e.export``) — serialize the model to ``.sm.json``.

The exporter assembles a neutral :class:`StructuralModel` from the
``e.geometry`` enumerator and writes the versioned ``*.sm.json`` interchange
document apeGmsh consumes (ADR 0009). Read-only with respect to ETABS — it
never mutates the model.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ._builder import build_structural_model
from .StructuralModel import StructuralModel

if TYPE_CHECKING:
    from .._session import _SessionBase


class Export:
    """Serialize the connected model to the neutral interchange document."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    def structural_model(
        self, path: str | Path | None = None, *, validate: bool = True
    ) -> StructuralModel:
        """Assemble the :class:`StructuralModel`; write it to ``path`` if given.

        Returns the assembled model (whether or not a path is written), so
        callers can inspect counts/contents. When ``path`` is provided the
        document is validated (unless ``validate=False``) and written there.
        """
        model = build_structural_model(self._parent)
        if path is not None:
            model.write(path, validate=validate)
        elif validate:
            model.validate()
        return model
