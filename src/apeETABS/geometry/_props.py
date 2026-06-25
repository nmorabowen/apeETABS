"""Section and material property bags.

Frame sections come from ``cPropFrame`` (material + computed sectional
properties); shell sections from ``cPropArea`` (material + thickness, with the
wall/slab/shell distinction); materials from ``cPropMaterial`` (isotropic or
uniaxial E/nu + mass density). All in present units.

Real models carry sections and materials the basic getters don't support —
auto-select lists and nonprismatic frame sections have no single material or
computed properties, and rebar/tendon materials are uniaxial, not isotropic.
Every getter here is therefore best-effort: a property that can't be read is
omitted, never fatal, so one exotic object can't abort the whole export.
"""

from __future__ import annotations

from ..errors import ETABSError, ok

# cPropFrame.GetSectProps out order -> schema prop keys. ETABS local 2/3 axes
# map to y/z; Torsion is J.
_SECT_PROP_KEYS = (
    "A", "As2", "As3", "J", "Iy", "Iz", "Sy", "Sz", "Zy", "Zz", "ry", "rz",
)


def read_frame_section(sap, name: str) -> dict:
    """A frame section as ``{name, kind:'frame', [material], props{...}}``.

    ``material`` is omitted for sections without a single material (e.g. an
    auto-select list); ``props`` is empty when the section has no computed
    properties (e.g. nonprismatic).
    """
    section: dict = {"name": name, "kind": "frame", "props": {}}
    material = _try(sap.PropFrame.GetMaterial, name, "")
    if material:
        section["material"] = str(material)
    values = _try(sap.PropFrame.GetSectProps, name, *([0.0] * 12))
    if values:
        section["props"] = {k: float(v) for k, v in zip(_SECT_PROP_KEYS, values)}
    return section


def read_shell_section(sap, name: str) -> dict:
    """A shell section as ``{name, kind:'shell', [material], [thickness], area_kind}``."""
    area_kind, material, thickness = _classify_shell(sap, name)
    section: dict = {"name": name, "kind": "shell", "area_kind": area_kind}
    if material:
        section["material"] = material
    if thickness is not None:
        section["thickness"] = thickness
    return section


def read_material(sap, name: str) -> dict | None:
    """A material as ``{name, E, nu, [rho]}``, or ``None`` if unreadable.

    Tries isotropic first, then uniaxial (rebar/tendon — E only, ``nu`` 0).
    Materials whose mechanics can't be read at all are dropped.
    """
    iso = _try(sap.PropMaterial.GetMPIsotropic, name, 0.0, 0.0, 0.0, 0.0)
    if iso:
        E, nu, _a, _g = iso
    else:
        # GetMPUniaxial out order: E, A (no Poisson).
        uni = _try(sap.PropMaterial.GetMPUniaxial, name, 0.0, 0.0)
        if not uni:
            return None
        E, _a = uni
        nu = 0.0
    material = {"name": name, "E": float(E), "nu": float(nu)}
    # GetWeightAndMass out order: W (weight/vol), M (mass/vol). rho = mass/vol.
    wm = _try(sap.PropMaterial.GetWeightAndMass, name, 0.0, 0.0)
    if wm:
        material["rho"] = float(wm[1])
    return material


def _classify_shell(sap, name: str) -> tuple[str, str | None, float | None]:
    """Resolve ``(area_kind, material, thickness)`` for a shell section."""
    # GetSlab out order: SlabType, ShellType, MatProp, Thickness, ...
    slab = _try(sap.PropArea.GetSlab, name, 0, 0, "", 0.0, 0, "", "")
    if slab:
        _st, _shell, mat, thickness, *_rest = slab
        return "slab", str(mat), float(thickness)
    # GetWall out order: WallPropType, ShellType, MatProp, Thickness, ...
    wall = _try(sap.PropArea.GetWall, name, 0, 0, "", 0.0, 0, "", "")
    if wall:
        _wt, _shell, mat, thickness, *_rest = wall
        return "wall", str(mat), float(thickness)
    # Generic shell: material only (no single thickness, e.g. layered/deck).
    design = _try(sap.PropArea.GetShellDesign, name, "", 0, 0.0, 0.0, 0.0, 0.0)
    if design:
        mat, *_rest = design
        return "shell", (str(mat) or None), None
    return "shell", None, None


def _try(method, *args):
    """Call an OAPI getter; return the ok() result, or ``None`` on failure."""
    try:
        return ok(method(*args))
    except ETABSError:
        return None
