"""``Define`` composite — the model dictionary (materials, sections, loads).

The ``e.define`` surface (ADR 0006 §2): the *define* half of creation —
materials (``cPropMaterial``), frame sections (``cPropFrame``), load patterns
(``cLoadPatterns``), and later cases/combos/diaphragms/grids. Geometry lives on
``e.create``; assignments share ``e.assign`` with editing (ADR 0005).

Units are **present-units-as-contract** (ADR 0006 §3): numeric arguments
(``depth``, ``width``, ``E``, ``fc`` …) are interpreted in the model's *present*
units. The recommended way to author them is the ``baseUnits`` library so the
intent is explicit — e.g. with present units ``("kN", "m")``::

    e.units.set("kN", "m")
    e.define.material("C30", kind="Concrete", E=30e6, nu=0.2)  # E in kN/m^2
    e.define.frame_rect("R1", material="C30", depth=0.6, width=0.3)  # metres

Every mutating method first calls ``self._parent._require_unlocked(...)`` (ADR
0005 §2 / ADR 0006 §6: never unlock implicitly, and stay safe on reused/locked
sessions) and routes each COM return through ``ok()`` (fail-loud, no rollback).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums import eMatType
from ..errors import ETABSError, ok

if TYPE_CHECKING:
    from .._session import _SessionBase


def _coerce_mat(kind: str | eMatType | int) -> eMatType:
    """Coerce a material kind name / int / enum member into :class:`eMatType`."""
    if isinstance(kind, eMatType):
        return kind
    if isinstance(kind, str):
        try:
            return eMatType[kind]
        except KeyError:
            valid = ", ".join(m.name for m in eMatType)
            raise ETABSError(
                f"Unknown material kind '{kind}'. Valid: {valid}."
            ) from None
    return eMatType(int(kind))


class Define:
    """Model-dictionary definitions (materials, frame sections, load patterns)."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    def material(
        self,
        name: str,
        *,
        kind: str | eMatType | int = "Concrete",
        E: float | None = None,
        nu: float | None = None,
        alpha: float = 0.0,
        **_unused,
    ) -> str:
        """Define an isotropic material via ``cPropMaterial.SetMaterial``.

        Initializes the material of the given ``kind`` and, when the isotropic
        mechanical properties are supplied, assigns them with
        ``SetMPIsotropic(E, nu, alpha)``. ``E`` is interpreted in the present
        force/length^2 units (ADR 0006 §3).

        Args:
            name: The material property name.
            kind: Material type — ``"Concrete"`` (default), ``"Steel"``,
                ``"Rebar"``, … (a name, int code, or :class:`eMatType`).
            E: Modulus of elasticity (present units). When given, ``nu`` is
                required and ``SetMPIsotropic`` is called.
            nu: Poisson's ratio (required when ``E`` is given).
            alpha: Coefficient of thermal expansion (present units, default 0).

        Returns:
            The material name (ADR 0006 §4).
        """
        self._parent._require_unlocked(f"define material {name!r}")
        mat_type = _coerce_mat(kind)
        # SetMaterial is soft-DEPRECATED in the OAPI, but it remains the correct
        # primitive for *custom* user-defined-property materials: it creates a
        # blank named material of a type so SetMPIsotropic can stamp arbitrary
        # E/nu/alpha. AddMaterial is catalog-driven and cannot express arbitrary
        # E/nu — see material_from_catalog for that path.
        ok(
            self._parent.SapModel.PropMaterial.SetMaterial(name, int(mat_type)),
            f"SetMaterial {name!r}",
        )
        if E is not None:
            if nu is None:
                raise ValueError(
                    f"material({name!r}): nu is required when E is given "
                    "(SetMPIsotropic needs E and nu)."
                )
            ok(
                self._parent.SapModel.PropMaterial.SetMPIsotropic(
                    name, float(E), float(nu), float(alpha)
                ),
                f"SetMPIsotropic {name!r}",
            )
        if self._parent._verbose:
            print(f"Defined material {name!r} ({mat_type.name}).")
        return name

    def material_from_catalog(
        self,
        *,
        kind: str | eMatType | int = "Concrete",
        region: str,
        standard: str,
        grade: str,
        name: str | None = None,
    ) -> str:
        """Add a material FROM THE ETABS CATALOG via ``cPropMaterial.AddMaterial``.

        Unlike :meth:`material` (which builds a *custom* material and stamps
        arbitrary ``E``/``nu`` via the deprecated ``SetMaterial``), this picks a
        predefined material out of the ETABS catalog identified by a
        ``Region``/``Standard``/``Grade`` triple, and returns the
        program-assigned material name. It cannot express arbitrary ``E``/``nu``.

        Args:
            kind: Material type — ``"Concrete"`` (default), ``"Steel"``,
                ``"Rebar"``, … (a name, int code, or :class:`eMatType`).
            region: Catalog region (e.g. ``"United States"``).
            standard: Catalog standard (e.g. ``"ASTM A615"``).
            grade: Catalog grade (e.g. ``"Grade 60"``).
            name: Optional ``UserName`` for the material; when omitted ETABS
                assigns the name.

        .. note::
            The ``region``/``standard``/``grade`` strings are
            **ETABS-catalog-specific** — their valid values depend on the
            installed ETABS version and are validated only against a live
            model, not by apeETABS.

        Returns:
            The program-assigned material name (ADR 0006 §4).
        """
        self._parent._require_unlocked("define material from catalog")
        mat_type = _coerce_mat(kind)
        # AddMaterial's Name is a ref/out param: it comes back as the first
        # element of the ok() result alongside the status return.
        assigned = ok(
            self._parent.SapModel.PropMaterial.AddMaterial(
                "", int(mat_type), region, standard, grade, name or ""
            ),
            f"AddMaterial ({region}/{standard}/{grade})",
        )
        if self._parent._verbose:
            print(f"Added catalog material {assigned!r} ({mat_type.name}).")
        return assigned

    # ------------------------------------------------------------------
    # Frame sections
    # ------------------------------------------------------------------

    def frame_rect(
        self,
        name: str,
        *,
        material: str,
        depth: float,
        width: float,
    ) -> str:
        """Define a solid rectangular frame section via ``cPropFrame.SetRectangle``.

        ``depth`` (T3, along the section's local 3-axis) and ``width`` (T2,
        along the local 2-axis) are interpreted in the present length units
        (ADR 0006 §3 — author with ``baseUnits``, e.g. ``depth=0.6`` metres).

        Args:
            name: The frame section property name.
            material: The name of an existing material property.
            depth: Section depth T3 (present length units).
            width: Section width T2 (present length units).

        Returns:
            The section name (ADR 0006 §4).
        """
        self._parent._require_unlocked(f"define frame section {name!r}")
        ok(
            self._parent.SapModel.PropFrame.SetRectangle(
                name, material, float(depth), float(width)
            ),
            f"SetRectangle {name!r}",
        )
        if self._parent._verbose:
            print(f"Defined rectangular section {name!r} ({material}).")
        return name

    # ------------------------------------------------------------------
    # Load patterns
    # ------------------------------------------------------------------

    def load_pattern(
        self,
        name: str,
        *,
        kind: str = "Other",
        self_wt: float = 0.0,
        add: bool = True,
    ) -> str:
        """Define a load pattern via ``cLoadPatterns.Add``.

        Args:
            name: The load pattern name.
            kind: Load pattern type — ``"Other"`` (default), ``"Dead"``,
                ``"Live"``, ``"Quake"``, … (mapped to ``eLoadPatternType``).
            self_wt: Self-weight multiplier (``SelfWTMultiplier``, default 0).
            add: Whether to add a matching analysis case (``AddAnalysisCase``,
                default True).

        Returns:
            The load pattern name (ADR 0006 §4).
        """
        # Imported lazily to keep the module's import surface minimal and to
        # mirror the per-call coercion style used for materials.
        from ..enums import eLoadPatternType

        self._parent._require_unlocked(f"define load pattern {name!r}")
        try:
            pat_type = eLoadPatternType[kind]
        except KeyError:
            valid = ", ".join(m.name for m in eLoadPatternType)
            raise ETABSError(
                f"Unknown load pattern kind '{kind}'. Valid: {valid}."
            ) from None
        ok(
            self._parent.SapModel.LoadPatterns.Add(
                name, int(pat_type), float(self_wt), bool(add)
            ),
            f"LoadPatterns.Add {name!r}",
        )
        if self._parent._verbose:
            print(f"Defined load pattern {name!r} ({pat_type.name}).")
        return name

    # ------------------------------------------------------------------
    # Stubs — documented, not yet implemented (ADR 0006 §2).
    # ------------------------------------------------------------------

    def section(self, *args, **kwargs):
        """Define non-rectangular frame/area section types (I, channel, tube…).

        Not implemented yet — P7 ships ``frame_rect`` only; the other
        ``cPropFrame`` / ``cPropArea`` section initializers land later.
        """
        raise NotImplementedError(
            "Define.section is not implemented yet (P7 ships frame_rect only)."
        )

    def combo(self, *args, **kwargs):
        """Define a load combination (wraps ``cCombo.Add`` / ``SetCaseList``).

        Not implemented yet — P7 ships material/frame_rect/load_pattern only.
        """
        raise NotImplementedError(
            "Define.combo is not implemented yet (P7 ships the core defines)."
        )

    def diaphragm(self, *args, **kwargs):
        """Define a diaphragm (wraps ``cDiaphragm.SetDiaphragm``).

        Not implemented yet — P7 ships material/frame_rect/load_pattern only.
        """
        raise NotImplementedError(
            "Define.diaphragm is not implemented yet (P7 ships the core defines)."
        )
