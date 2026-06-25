"""Area (subgrade) spring enumeration — distributed Winkler support on areas.

``cAreaObj.GetSpringAssignment`` returns the name of the area-spring property
(``cPropAreaSpring``) assigned to an area — empty when none. That property's
``GetAreaSpringProp`` gives the per-unit-area stiffnesses ``[U1,U2,U3]`` in the
area local system (``U3`` is the out-of-plane / subgrade-modulus direction).
This is the real base-support mechanism in foundation models, which carry the
slab on soil via area springs rather than rigid restraints or point springs
(``GetSpring`` — handled by :mod:`._springs`).

Best-effort, like the section/material reads: an area whose assignment or whose
spring property can't be read is skipped rather than aborting the enumeration.
"""

from __future__ import annotations

from ..errors import ETABSError, ok


def read_area_springs(sap, area_names) -> list[dict]:
    """Subgrade-supported areas as ``[{area, property, k}]`` (``k=[U1,U2,U3]``).

    Areas with no spring assignment (empty property name) are omitted, as are
    those whose named property's stiffnesses can't be read or are all zero.
    The property read is cached so a soil property shared across many areas is
    fetched once.
    """
    springs: list[dict] = []
    cache: dict[str, list[float] | None] = {}
    for name in area_names:
        name = str(name)
        try:
            # GetSpringAssignment out: SpringProp (property name, "" if none).
            prop = ok(sap.AreaObj.GetSpringAssignment(name, ""), "GetSpringAssignment")
        except ETABSError:
            continue
        prop = str(prop)
        if not prop:
            continue
        k = _read_prop(sap, prop, cache)
        if not k or not any(k):
            continue
        springs.append({"area": name, "property": prop, "k": k})
    return springs


def _read_prop(sap, prop: str, cache: dict) -> list[float] | None:
    """Per-unit-area stiffnesses ``[U1,U2,U3]`` for a spring property, cached."""
    if prop in cache:
        return cache[prop]
    try:
        # GetAreaSpringProp out order: U1, U2, U3, NonlinearOption3,
        # SpringOption, SoilProfile, EndLengthRatio, Period, color, notes, iGUID.
        out = ok(
            sap.PropAreaSpring.GetAreaSpringProp(
                prop, 0.0, 0.0, 0.0, 0, 1, "", 0.0, 0.0, 0, "", ""
            ),
            "GetAreaSpringProp",
        )
        k = [float(out[0]), float(out[1]), float(out[2])]
    except ETABSError:
        k = None
    cache[prop] = k
    return k
