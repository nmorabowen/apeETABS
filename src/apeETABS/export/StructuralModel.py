"""StructuralModel — apeETABS-side writer for the neutral interchange document.

Emits the ``*.sm.json`` contract consumed by apeGmsh (see ADR 0009 and
``schema/structural_model.schema.json``). This is the *mirror* of apeGmsh's
reader dataclasses: the canonical spec is the JSON Schema, and each repo owns
its own (de)serialization layer (ADR 0009, "schema dataclasses duplicated per
repo").

The dataclasses are write-oriented: ``to_dict`` omits unset optionals so the
document stays minimal and clean against the schema's ``additionalProperties:
false`` objects. :meth:`StructuralModel.validate` checks the document against
the schema — structurally always, and against the full JSON Schema when
``jsonschema`` is importable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "0.1"

Vec3 = tuple[float, float, float]
Dof6 = tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    x: float
    y: float
    z: float
    story: str | None = None

    def to_dict(self) -> dict:
        d = {"id": self.id, "x": self.x, "y": self.y, "z": self.z}
        if self.story is not None:
            d["story"] = self.story
        return d


@dataclass(frozen=True, slots=True)
class Frame:
    id: str
    i: str
    j: str
    section: str
    material: str | None = None
    kind: str | None = None
    rotation: float | None = None
    releases_i: Dof6 | None = None
    releases_j: Dof6 | None = None

    def to_dict(self) -> dict:
        d = {"id": self.id, "i": self.i, "j": self.j, "section": self.section}
        if self.material is not None:
            d["material"] = self.material
        if self.kind is not None:
            d["kind"] = self.kind
        if self.rotation is not None:
            d["rotation"] = self.rotation
        if self.releases_i is not None:
            d["releases_i"] = list(self.releases_i)
        if self.releases_j is not None:
            d["releases_j"] = list(self.releases_j)
        return d


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    nodes: tuple[str, ...]
    section: str
    material: str | None = None
    thickness: float | None = None
    kind: str | None = None
    local_axis_deg: float | None = None
    openings: tuple[tuple[str, ...], ...] | None = None

    def to_dict(self) -> dict:
        d = {"id": self.id, "nodes": list(self.nodes), "section": self.section}
        if self.material is not None:
            d["material"] = self.material
        if self.thickness is not None:
            d["thickness"] = self.thickness
        if self.kind is not None:
            d["kind"] = self.kind
        if self.local_axis_deg is not None:
            d["local_axis_deg"] = self.local_axis_deg
        if self.openings:
            d["openings"] = [list(loop) for loop in self.openings]
        return d


@dataclass(frozen=True, slots=True)
class Section:
    name: str
    kind: str  # "frame" | "shell"
    material: str | None = None
    thickness: float | None = None
    props: dict[str, float] | None = None

    def to_dict(self) -> dict:
        d = {"name": self.name, "kind": self.kind}
        if self.material is not None:
            d["material"] = self.material
        if self.thickness is not None:
            d["thickness"] = self.thickness
        if self.props:
            d["props"] = dict(self.props)
        return d


@dataclass(frozen=True, slots=True)
class Material:
    name: str
    E: float
    nu: float
    rho: float | None = None
    fy: float | None = None

    def to_dict(self) -> dict:
        d = {"name": self.name, "E": self.E, "nu": self.nu}
        if self.rho is not None:
            d["rho"] = self.rho
        if self.fy is not None:
            d["fy"] = self.fy
        return d


@dataclass(frozen=True, slots=True)
class Restraint:
    node: str
    dofs: Dof6

    def to_dict(self) -> dict:
        return {"node": self.node, "dofs": list(self.dofs)}


@dataclass(frozen=True, slots=True)
class Diaphragm:
    name: str
    nodes: tuple[str, ...]
    story: str | None = None

    def to_dict(self) -> dict:
        d = {"name": self.name, "nodes": list(self.nodes)}
        if self.story is not None:
            d["story"] = self.story
        return d


@dataclass(frozen=True, slots=True)
class NodalLoad:
    node: str
    force_xyz: Vec3 = (0.0, 0.0, 0.0)
    moment_xyz: Vec3 = (0.0, 0.0, 0.0)

    def to_dict(self) -> dict:
        d: dict = {"node": self.node}
        if any(self.force_xyz):
            d["force_xyz"] = list(self.force_xyz)
        if any(self.moment_xyz):
            d["moment_xyz"] = list(self.moment_xyz)
        return d


@dataclass(frozen=True, slots=True)
class FrameLoad:
    frame: str
    direction: int | str
    value: float

    def to_dict(self) -> dict:
        return {"frame": self.frame, "direction": self.direction, "value": self.value}


@dataclass(frozen=True, slots=True)
class AreaLoad:
    area: str
    direction: int | str
    value: float

    def to_dict(self) -> dict:
        return {"area": self.area, "direction": self.direction, "value": self.value}


@dataclass(frozen=True, slots=True)
class LoadPattern:
    name: str
    nodal: tuple[NodalLoad, ...] = ()
    frame: tuple[FrameLoad, ...] = ()
    area: tuple[AreaLoad, ...] = ()

    def to_dict(self) -> dict:
        d: dict = {}
        if self.nodal:
            d["nodal"] = [n.to_dict() for n in self.nodal]
        if self.frame:
            d["frame"] = [f.to_dict() for f in self.frame]
        if self.area:
            d["area"] = [a.to_dict() for a in self.area]
        return d


@dataclass
class StructuralModel:
    units: dict[str, str]
    nodes: list[Node]
    frames: list[Frame]
    areas: list[Area] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    restraints: list[Restraint] = field(default_factory=list)
    diaphragms: list[Diaphragm] = field(default_factory=list)
    loads: list[LoadPattern] = field(default_factory=list)
    source: dict = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d: dict = {
            "schema_version": self.schema_version,
            "units": dict(self.units),
        }
        if self.source:
            d["source"] = dict(self.source)
        d["nodes"] = [n.to_dict() for n in self.nodes]
        d["frames"] = [f.to_dict() for f in self.frames]
        if self.areas:
            d["areas"] = [a.to_dict() for a in self.areas]
        if self.sections:
            d["sections"] = [s.to_dict() for s in self.sections]
        if self.materials:
            d["materials"] = [m.to_dict() for m in self.materials]
        if self.restraints:
            d["restraints"] = [r.to_dict() for r in self.restraints]
        if self.diaphragms:
            d["diaphragms"] = [dp.to_dict() for dp in self.diaphragms]
        if self.loads:
            d["loads"] = {p.name: p.to_dict() for p in self.loads}
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, path: str | Path, *, validate: bool = True) -> Path:
        """Write the document to ``path`` (``.sm.json``); validate first."""
        if validate:
            self.validate()
        path = Path(path)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    def validate(self) -> "StructuralModel":
        """Validate the document against the schema; raise on any violation."""
        validate_document(self.to_dict())
        return self


# ----------------------------------------------------------------------
# Validation — schema path + a dependency-free structural fallback
# ----------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema" / "structural_model.schema.json"


class SchemaError(ValueError):
    """Raised when a StructuralModel document violates the schema."""


def validate_document(doc: dict) -> None:
    """Validate a ``StructuralModel`` dict against the contract.

    Always runs a dependency-free structural check (required fields, DOF-mask
    shape, and node/section/material referential integrity). When the
    ``jsonschema`` package is importable it additionally validates against the
    full JSON Schema for complete coverage.
    """
    _structural_check(doc)
    _jsonschema_check(doc)


def _structural_check(doc: dict) -> None:
    ver = doc.get("schema_version")
    if ver != SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version must be {SCHEMA_VERSION!r}, got {ver!r}."
        )

    units = doc.get("units")
    if not isinstance(units, dict) or "length" not in units or "force" not in units:
        raise SchemaError("units must define both 'length' and 'force'.")

    nodes = doc.get("nodes")
    frames = doc.get("frames")
    if not isinstance(nodes, list) or not isinstance(frames, list):
        raise SchemaError("'nodes' and 'frames' are required arrays.")

    node_ids: set[str] = set()
    for n in nodes:
        for key in ("id", "x", "y", "z"):
            if key not in n:
                raise SchemaError(f"node missing required field {key!r}: {n!r}")
        node_ids.add(n["id"])

    section_names = {s["name"] for s in doc.get("sections", [])}

    def need_node(nid: str, where: str) -> None:
        if nid not in node_ids:
            raise SchemaError(f"{where} references unknown node id {nid!r}.")

    for f in frames:
        for key in ("id", "i", "j", "section"):
            if key not in f:
                raise SchemaError(f"frame missing required field {key!r}: {f!r}")
        need_node(f["i"], f"frame {f['id']!r} (i)")
        need_node(f["j"], f"frame {f['id']!r} (j)")
        if section_names and f["section"] not in section_names:
            raise SchemaError(
                f"frame {f['id']!r} references unknown section {f['section']!r}."
            )
        for key in ("releases_i", "releases_j"):
            if key in f:
                _check_dof_mask(f[key], f"frame {f['id']!r} {key}")

    for a in doc.get("areas", []):
        for key in ("id", "nodes", "section"):
            if key not in a:
                raise SchemaError(f"area missing required field {key!r}: {a!r}")
        if len(a["nodes"]) < 3:
            raise SchemaError(f"area {a['id']!r} needs >= 3 boundary nodes.")
        for nid in a["nodes"]:
            need_node(nid, f"area {a['id']!r}")
        if section_names and a["section"] not in section_names:
            raise SchemaError(
                f"area {a['id']!r} references unknown section {a['section']!r}."
            )

    for s in doc.get("sections", []):
        if s.get("kind") not in ("frame", "shell"):
            raise SchemaError(f"section {s.get('name')!r} kind must be frame|shell.")
        # Note: section -> material refs are intentionally NOT enforced — a
        # referenced material may be unreadable (non-isotropic/uniaxial exotic)
        # and legitimately dropped from the materials array.

    for r in doc.get("restraints", []):
        need_node(r["node"], "restraint")
        _check_dof_mask(r["dofs"], f"restraint on {r['node']!r}")

    for dp in doc.get("diaphragms", []):
        for nid in dp.get("nodes", []):
            need_node(nid, f"diaphragm {dp.get('name')!r}")


def _check_dof_mask(mask, where: str) -> None:
    if len(mask) != 6 or any(v not in (0, 1) for v in mask):
        raise SchemaError(f"{where} must be a 6-entry 0/1 mask, got {mask!r}.")


def _jsonschema_check(doc: dict) -> None:
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return  # structural check already ran; full schema check is best-effort
    if not _SCHEMA_PATH.exists():
        return  # schema file not alongside the install (e.g. wheel); skip
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:  # noqa: PERF203
        raise SchemaError(f"JSON Schema validation failed: {exc.message}") from exc
