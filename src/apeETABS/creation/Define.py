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

from typing import TYPE_CHECKING, Sequence

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

    def response_spectrum_function(
        self,
        name: str,
        periods: Sequence[float],
        values: Sequence[float],
        *,
        damping: float = 0.05,
    ) -> str:
        """Define a user response-spectrum function via ``cFunctionRS.SetUser``.

        Args:
            name: The function name.
            periods: Period ordinates in seconds (paired with ``values``).
            values: Spectral acceleration ordinates — **normalized/unitless**;
                ETABS applies the units via the scale factor on the response-
                spectrum load case that references this function.
            damping: Damping ratio (default ``0.05`` = 5%).

        Returns:
            The function name (ADR 0006 §4).
        """
        # LIVE-CONFIRM: access path SapModel.Func.FuncRS (ETABSv1; cFunction
        # exposes FuncRS) and SetUser(Name, NumberItems, Period[], Value[],
        # DampRatio) — confirmed via CSI docs, not the (partial) bundled
        # reference. Verify on a live model.
        self._parent._require_unlocked(
            f"define response spectrum function {name!r}"
        )
        per = [float(p) for p in periods]
        val = [float(v) for v in values]
        if len(per) != len(val):
            raise ETABSError(
                f"response_spectrum_function {name!r}: periods ({len(per)}) and "
                f"values ({len(val)}) must be the same length."
            )
        if len(per) < 2:
            raise ETABSError(
                f"response_spectrum_function {name!r} needs at least 2 points."
            )
        ok(
            self._parent.SapModel.Func.FuncRS.SetUser(
                name, len(per), per, val, float(damping)
            ),
            f"FuncRS.SetUser {name!r}",
        )
        if self._parent._verbose:
            print(f"Defined RS function {name!r} ({len(per)} pts, "
                  f"damping={damping}).")
        return name

    def modal_case(
        self,
        name: str,
        *,
        max_modes: int = 12,
        min_modes: int = 1,
    ) -> str:
        """Define a modal (eigen) load case via ``cCaseModalEigen``.

        Creates/initializes the case (``SetCase``) and sets the mode count
        (``SetNumberModes``); other modal parameters keep ETABS defaults.

        Returns:
            The case name (ADR 0006 §4).
        """
        self._parent._require_unlocked(f"define modal case {name!r}")
        modal = self._parent.SapModel.LoadCases.ModalEigen
        ok(modal.SetCase(name), f"ModalEigen.SetCase {name!r}")
        ok(
            modal.SetNumberModes(name, int(max_modes), int(min_modes)),
            f"ModalEigen.SetNumberModes {name!r}",
        )
        if self._parent._verbose:
            print(f"Defined modal case {name!r} ({min_modes}..{max_modes} modes).")
        return name

    def response_spectrum_case(
        self,
        name: str,
        *,
        modal_case: str,
        loads: dict[str, tuple[str, float]],
        csys: str = "Global",
        angle: float = 0.0,
    ) -> str:
        """Define a response-spectrum load case via ``cCaseResponseSpectrum``.

        Args:
            name: The case name.
            modal_case: The modal case this RS case uses (must already exist).
            loads: ``{direction: (function_name, scale_factor)}`` where
                ``direction`` is an ETABS RS direction (``"U1"``/``"U2"``/
                ``"U3"``/``"R1"``…) and ``function_name`` is a defined RS
                function (see :meth:`response_spectrum_function`).
            csys: Coordinate system for the loads (default Global).
            angle: Load angle in degrees (default 0).

        Modal/directional combination and damping keep ETABS defaults (CQC /
        SRSS / the function damping); explicit control is a follow-up (those
        setters are absent from the bundled OAPI reference).

        Returns:
            The case name (ADR 0006 §4).
        """
        # LIVE-CONFIRM: SapModel.LoadCases.ResponseSpectrum.{SetCase,SetLoads,
        # SetModalCase} access path + SetLoads parallel-array marshalling.
        self._parent._require_unlocked(
            f"define response spectrum case {name!r}"
        )
        if not loads:
            raise ETABSError(
                f"RS case {name!r} needs at least one direction in `loads`."
            )
        dirs = list(loads)
        funcs = [str(loads[d][0]) for d in dirs]
        sfs = [float(loads[d][1]) for d in dirs]
        csys_list = [csys] * len(dirs)
        angs = [float(angle)] * len(dirs)
        rs = self._parent.SapModel.LoadCases.ResponseSpectrum
        ok(rs.SetCase(name), f"ResponseSpectrum.SetCase {name!r}")
        ok(
            rs.SetLoads(name, len(dirs), dirs, funcs, sfs, csys_list, angs),
            f"ResponseSpectrum.SetLoads {name!r}",
        )
        ok(
            rs.SetModalCase(name, str(modal_case)),
            f"ResponseSpectrum.SetModalCase {name!r}",
        )
        if self._parent._verbose:
            print(f"Defined RS case {name!r} (modal={modal_case!r}, "
                  f"{len(dirs)} directions).")
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

    def combo(
        self,
        name: str,
        cases: dict[str, float],
        *,
        kind: str = "LinearAdditive",
        case_type: str = "LoadCase",
    ) -> str:
        """Define a load combination via ``cCombo.Add`` + ``SetCaseList_1``.

        Args:
            name: The combination name.
            cases: ``{case_or_combo_name: scale_factor}`` — the contributing
                cases/combos and their factors. Must be non-empty.
            kind: Combination type (``eComboType``): ``"LinearAdditive"``
                (default), ``"Envelope"``, ``"AbsoluteAdditive"``, ``"SRSS"``,
                ``"RangeAdditive"``.
            case_type: Whether the ``cases`` keys are load ``"LoadCase"``
                (default) or ``"LoadCombo"`` names (``eCNameType``).

        Returns:
            The combination name (ADR 0006 §4).
        """
        from ..enums import eCNameType, eComboType

        self._parent._require_unlocked(f"define combo {name!r}")
        if not cases:
            raise ETABSError(
                f"Combo {name!r} needs at least one case in `cases`."
            )
        try:
            combo_type = eComboType[kind]
        except KeyError:
            valid = ", ".join(m.name for m in eComboType)
            raise ETABSError(
                f"Unknown combo kind '{kind}'. Valid: {valid}."
            ) from None
        try:
            cname_type = eCNameType[case_type]
        except KeyError:
            valid = ", ".join(m.name for m in eCNameType)
            raise ETABSError(
                f"Unknown case_type '{case_type}'. Valid: {valid}."
            ) from None

        combo = self._parent.SapModel.RespCombo
        ok(combo.Add(name, int(combo_type)), f"RespCombo.Add {name!r}")
        for cname, sf in cases.items():
            # SetCaseList_1(Name, CNameType, CName, ModeNumber, SF); ModeNumber
            # is unused for case/combo contributions (0).
            ok(
                combo.SetCaseList_1(name, int(cname_type), str(cname), 0, float(sf)),
                f"RespCombo.SetCaseList_1 {name!r} <- {cname!r}",
            )
        if self._parent._verbose:
            print(f"Defined combo {name!r} ({combo_type.name}, {len(cases)} cases).")
        return name

    def mass_source(
        self,
        *,
        from_loads: dict[str, float] | None = None,
        include_elements: bool = True,
        include_added_mass: bool = True,
    ) -> None:
        """Set the model mass source via ``cPropMaterial.SetMassSource_1``.

        Args:
            from_loads: ``{load_pattern: scale_factor}`` contributing to mass
                (e.g. ``{"Dead": 1.0, "Live": 0.25}``). Omit/empty to include no
                load-derived mass.
            include_elements: Include element self-mass (``IncludeElements``).
            include_added_mass: Include assigned added mass (``IncludeAddedMass``).
        """
        self._parent._require_unlocked("set mass source")
        loads = from_loads or {}
        pats = [str(p) for p in loads]
        sfs = [float(s) for s in loads.values()]
        ok(
            self._parent.SapModel.PropMaterial.SetMassSource_1(
                bool(include_elements),
                bool(include_added_mass),
                bool(bool(loads)),  # IncludeLoads: true iff any load contributes
                len(pats),
                pats,
                sfs,
            ),
            "PropMaterial.SetMassSource_1",
        )
        if self._parent._verbose:
            src = ", ".join(f"{p}×{s}" for p, s in loads.items()) or "(no loads)"
            print(f"Set mass source: elements={include_elements}, "
                  f"added={include_added_mass}, loads=[{src}].")

    def diaphragm(self, *args, **kwargs):
        """Define a diaphragm (wraps ``cDiaphragm.SetDiaphragm``).

        Not implemented yet — P7 ships material/frame_rect/load_pattern only.
        """
        raise NotImplementedError(
            "Define.diaphragm is not implemented yet (P7 ships the core defines)."
        )
