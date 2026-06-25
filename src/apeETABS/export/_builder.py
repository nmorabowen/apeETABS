"""Assemble a :class:`StructuralModel` from the ``e.geometry`` enumerator.

Pulls the plain-dict records, maps them onto the write-side dataclasses, pins
the units block from the model's present units, and resolves each area's
wall/slab kind from its (shell) section. Loads are assembled by
:mod:`._loads`.
"""

from __future__ import annotations

from . import _loads
from .StructuralModel import (
    Area,
    Diaphragm,
    Frame,
    LoadPattern,
    Material,
    Node,
    Restraint,
    Section,
    Spring,
    StructuralModel,
)

# ETABS enum member name -> short schema unit label (only where they differ).
_LENGTH_LABEL = {"inch": "in"}


def build_structural_model(e) -> StructuralModel:
    """Build a :class:`StructuralModel` from a connected apeETABS session ``e``."""
    geo = e.geometry
    point_recs = geo.points()
    frame_recs = geo.frames()
    area_recs = geo.areas()
    section_recs = geo.sections()
    material_recs = geo.materials()

    # area section name -> wall|slab|shell (from the shell-section classifier).
    area_kind = {
        s["name"]: s.get("area_kind")
        for s in section_recs
        if s["kind"] == "shell"
    }

    nodes = [
        Node(id=r["id"], x=r["x"], y=r["y"], z=r["z"]) for r in point_recs
    ]
    frames = [
        Frame(
            id=r["id"],
            i=r["i"],
            j=r["j"],
            section=r["section"],
            kind=r.get("kind"),
            rotation=r["rotation"] if r.get("rotation") else None,
            releases_i=_mask(r.get("releases_i")),
            releases_j=_mask(r.get("releases_j")),
        )
        for r in frame_recs
    ]
    areas = [
        Area(
            id=r["id"],
            nodes=tuple(r["nodes"]),
            section=r["section"],
            kind=area_kind.get(r["section"]),
            local_axis_deg=r["local_axis_deg"] if r.get("local_axis_deg") else None,
        )
        for r in area_recs
    ]
    sections = [
        Section(
            name=s["name"],
            kind=s["kind"],
            material=s.get("material"),
            thickness=s.get("thickness"),
            props=s.get("props"),
        )
        for s in section_recs
    ]
    materials = [
        Material(name=m["name"], E=m["E"], nu=m["nu"], rho=m.get("rho"))
        for m in material_recs
    ]
    restraints = [
        Restraint(node=r["node"], dofs=tuple(r["dofs"])) for r in geo.restraints()
    ]
    springs = [Spring(node=s["node"], k=tuple(s["k"])) for s in geo.springs()]
    diaphragms = [
        Diaphragm(name=d["name"], nodes=tuple(d["nodes"])) for d in geo.diaphragms()
    ]

    point_names = [r["id"] for r in point_recs]
    frame_names = [r["id"] for r in frame_recs]
    area_names = [r["id"] for r in area_recs]
    loads = _loads.read_loads(e.SapModel, e.tables, point_names, frame_names, area_names)

    nodes, restraints, springs, diaphragms, loads = _drop_orphan_nodes(
        nodes, frames, areas, restraints, springs, diaphragms, loads
    )

    return StructuralModel(
        units=_units_block(e),
        source=_source(e),
        nodes=nodes,
        frames=frames,
        areas=areas,
        sections=sections,
        materials=materials,
        restraints=restraints,
        springs=springs,
        diaphragms=diaphragms,
        loads=loads,
    )


def _drop_orphan_nodes(nodes, frames, areas, restraints, springs, diaphragms, loads):
    """Drop joints used by no frame or area, and scrub references to them.

    ETABS carries analysis-only joints — most notably rigid-diaphragm
    center-of-mass master joints — that connect to no member. apeGmsh is
    geometry-first: such joints have no element to sit on, so they become
    free (singular) nodes in the solver. The neutral document should hold only
    meshable geometry, so they are removed here along with any restraint /
    spring / diaphragm membership / nodal load that referenced them.
    """
    used = {f.i for f in frames} | {f.j for f in frames}
    for a in areas:
        used.update(a.nodes)

    nodes = [n for n in nodes if n.id in used]
    restraints = [r for r in restraints if r.node in used]
    springs = [s for s in springs if s.node in used]

    kept_diaphragms = []
    for d in diaphragms:
        members = tuple(n for n in d.nodes if n in used)
        if len(members) >= 2:  # schema minimum
            kept_diaphragms.append(Diaphragm(name=d.name, nodes=members, story=d.story))

    kept_loads = []
    for p in loads:
        nodal = tuple(ld for ld in p.nodal if ld.node in used)
        if nodal or p.frame or p.area:
            kept_loads.append(LoadPattern(name=p.name, nodal=nodal, frame=p.frame, area=p.area))

    return nodes, restraints, springs, kept_diaphragms, kept_loads


def _units_block(e) -> dict[str, str]:
    force, length, _temp = e.units.get()
    return {
        "length": _LENGTH_LABEL.get(length.name, length.name),
        "force": force.name,
    }


def _source(e) -> dict:
    source = {"tool": "ETABS"}
    if getattr(e, "path", None) is not None:
        source["model"] = e.path.name
    return source


def _mask(values):
    return tuple(int(v) for v in values) if values else None
