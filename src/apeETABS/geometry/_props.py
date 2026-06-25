"""Section and material property bags.

Frame sections come from ``cPropFrame`` (material + computed sectional
properties); shell sections from ``cPropArea`` (material + thickness, with the
wall/slab/shell distinction); materials from ``cPropMaterial`` (isotropic E/nu
+ mass density). All in present units.
"""

from __future__ import annotations

from ..errors import ETABSError, ok

# cPropFrame.GetSectProps out order -> schema prop keys. ETABS local 2/3 axes
# map to y/z; Torsion is J.
_SECT_PROP_KEYS = (
    "A", "As2", "As3", "J", "Iy", "Iz", "Sy", "Sz", "Zy", "Zz", "ry", "rz",
)


def read_frame_section(sap, name: str) -> dict:
    """A frame section as ``{name, kind:'frame', material, props{...}}``."""
    material = ok(sap.PropFrame.GetMaterial(name, ""), "PropFrame.GetMaterial")
    values = ok(sap.PropFrame.GetSectProps(name, *([0.0] * 12)), "GetSectProps")
    props = {key: float(v) for key, v in zip(_SECT_PROP_KEYS, values)}
    return {"name": name, "kind": "frame", "material": str(material), "props": props}


def read_shell_section(sap, name: str) -> dict:
    """A shell section as ``{name, kind:'shell', material, thickness, area_kind}``.

    ``area_kind`` is ``wall`` | ``slab`` | ``shell`` (the wall/slab distinction
    ETABS draws), used to label the area objects that reference the section.
    """
    area_kind, material, thickness = _classify_shell(sap, name)
    section = {"name": name, "kind": "shell", "material": material, "area_kind": area_kind}
    if thickness is not None:
        section["thickness"] = thickness
    return section


def read_material(sap, name: str) -> dict:
    """A material as ``{name, E, nu, rho}`` (isotropic + mass density)."""
    # GetMPIsotropic out order: E, U (Poisson), A (thermal), G (shear).
    E, nu, _a, _g = ok(
        sap.PropMaterial.GetMPIsotropic(name, 0.0, 0.0, 0.0, 0.0), "GetMPIsotropic"
    )
    material = {"name": name, "E": float(E), "nu": float(nu)}
    # GetWeightAndMass out order: W (weight/vol), M (mass/vol). rho = mass/vol.
    _w, mass = ok(
        sap.PropMaterial.GetWeightAndMass(name, 0.0, 0.0), "GetWeightAndMass"
    )
    material["rho"] = float(mass)
    return material


def _classify_shell(sap, name: str) -> tuple[str, str, float | None]:
    """Resolve ``(area_kind, material, thickness)`` for a shell section."""
    try:
        # GetSlab out order: SlabType, ShellType, MatProp, Thickness, ...
        _st, _shell, mat, thickness, *_rest = ok(
            sap.PropArea.GetSlab(name, 0, 0, "", 0.0, 0, "", ""), "GetSlab"
        )
        return "slab", str(mat), float(thickness)
    except ETABSError:
        pass
    try:
        # GetWall out order: WallPropType, ShellType, MatProp, Thickness, ...
        _wt, _shell, mat, thickness, *_rest = ok(
            sap.PropArea.GetWall(name, 0, 0, "", 0.0, 0, "", ""), "GetWall"
        )
        return "wall", str(mat), float(thickness)
    except ETABSError:
        pass
    # Generic shell: material only (no single thickness, e.g. layered/deck).
    mat, *_rest = ok(
        sap.PropArea.GetShellDesign(name, "", 0, 0.0, 0.0, 0.0, 0.0), "GetShellDesign"
    )
    return "shell", str(mat), None
