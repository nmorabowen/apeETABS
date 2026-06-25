"""Geometry composite (``e.geometry``) — read-only model enumeration.

The geometry-read layer ADR 0009 calls for: it walks the ETABS *object* API
(not display tables) and returns plain dict records — joints, frames, areas,
restraints, diaphragms, and the section/material property bags they reference.
This is the source the :mod:`export` composite assembles into a neutral
``StructuralModel`` document.

Every method returns lists of plain dicts (JSON-ready). Records are read live
each call; there is no caching — wrap in your own snapshot if you need one.
All values are in the model's *present units* (set them via ``e.units`` first).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import _areas, _diaphragms, _frames, _points, _props, _restraints

if TYPE_CHECKING:
    from .._session import _SessionBase


class Geometry:
    """Read-only enumerator over an ETABS model's analytical geometry."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    @property
    def _sap(self):
        return self._parent.SapModel

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def points(self) -> list[dict]:
        """All joints: ``[{id, x, y, z}]`` in present length units."""
        return _points.read_points(self._sap)

    def frames(self) -> list[dict]:
        """All frames: ``[{id, i, j, section, rotation, kind, releases_*}]``."""
        return _frames.read_frames(self._sap)

    def areas(self) -> list[dict]:
        """All areas: ``[{id, nodes, section, local_axis_deg, is_opening}]``."""
        return _areas.read_areas(self._sap)

    def restraints(self) -> list[dict]:
        """Restrained joints: ``[{node, dofs}]`` (6-int 0/1 masks)."""
        return _restraints.read_restraints(self._sap, self._point_names())

    def diaphragms(self) -> list[dict]:
        """Defined diaphragms: ``[{name, nodes}]`` grouped by joint assignment."""
        return _diaphragms.read_diaphragms(self._sap, self._point_names())

    # ------------------------------------------------------------------
    # Properties (only the sections/materials actually referenced)
    # ------------------------------------------------------------------

    def sections(self) -> list[dict]:
        """Sections referenced by frames/areas.

        Frame sections carry a ``props`` bag; shell sections carry
        ``thickness`` and an internal ``area_kind`` (wall/slab/shell) used to
        label the referencing areas.
        """
        sap = self._sap
        sections: list[dict] = []
        for name in _unique(f["section"] for f in self.frames()):
            sections.append(_props.read_frame_section(sap, name))
        for name in _unique(a["section"] for a in self.areas()):
            sections.append(_props.read_shell_section(sap, name))
        return sections

    def materials(self) -> list[dict]:
        """Materials referenced by the sections: ``[{name, E, nu, rho}]``."""
        sap = self._sap
        names = _unique(
            s["material"] for s in self.sections() if s.get("material")
        )
        return [_props.read_material(sap, name) for name in names]

    # -- single-record getters (used by the builder / ad-hoc queries) ---

    def frame_section(self, name: str) -> dict:
        return _props.read_frame_section(self._sap, name)

    def shell_section(self, name: str) -> dict:
        return _props.read_shell_section(self._sap, name)

    def material(self, name: str) -> dict:
        return _props.read_material(self._sap, name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _point_names(self) -> list[str]:
        return [p["id"] for p in self.points()]


def _unique(values) -> list[str]:
    """Unique values preserving first-seen order."""
    seen: dict[str, None] = {}
    for v in values:
        if v not in seen:
            seen[v] = None
    return list(seen)
