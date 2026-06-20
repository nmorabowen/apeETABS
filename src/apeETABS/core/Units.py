"""Units composite — present units + a bridge to the ``baseUnits`` library.

Two responsibilities:

1. **Present units.** Read and set the model's present units via
   ``cSapModel.GetPresentUnits_2`` / ``SetPresentUnits_2`` using readable
   names, enums, or integer codes.

2. **Reporting bridge.** ETABS returns numbers in whatever present units
   are active. For consistent calculations and reports we convert those
   into a chosen ``baseUnits`` system. The factors below take an ETABS
   value *in present units* into the report system's base units:

       V_base = V_etabs * units.force_factor          # a force
       M_base = M_etabs * units.factor("moment")      # a moment [F·L]

   then format out by dividing by any ``baseUnits`` unit::

       import baseUnits as u
       V_kip = V_base / u.kip
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..enums import eForce, eLength, eTemperature
from ..errors import ETABSError, ok

if TYPE_CHECKING:
    from .._session import _SessionBase

# ETABS enum member name -> baseUnits attribute name (they differ in spots).
_FORCE_TO_BASEUNITS = {
    "lb": "lbf", "kip": "kip", "N": "N", "kN": "kN", "kgf": "kgf", "tonf": "tf",
}
_LENGTH_TO_BASEUNITS = {
    "inch": "inches", "ft": "ft", "micron": None, "mm": "mm", "cm": "cm", "m": "m",
}


class Units:
    """Present-units management and conversion into a baseUnits report system."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent
        self._report: Any = None  # a baseUnits system namespace/module

    # ------------------------------------------------------------------
    # Present units
    # ------------------------------------------------------------------

    def get(self) -> tuple[eForce, eLength, eTemperature]:
        """Return the model's present (force, length, temperature) units."""
        f, l, t = ok(
            self._parent.SapModel.GetPresentUnits_2(0, 0, 0),
            "get present units",
        )
        return eForce(f), eLength(l), eTemperature(t)

    def set(
        self,
        force: str | eForce | int | None = None,
        length: str | eLength | int | None = None,
        temperature: str | eTemperature | int | None = None,
    ) -> "Units":
        """Set present units; unspecified dimensions keep their current value.

        Accepts readable names (``"kN"``, ``"m"``, ``"C"``), enum members,
        or integer codes. Returns ``self`` for chaining.

        Example:
            >>> e.units.set("kN", "m")            # leaves temperature as-is
            >>> e.units.set(force=eForce.kip, length=eLength.inch)
        """
        cur_f, cur_l, cur_t = self.get()
        f = cur_f if force is None else _coerce(force, eForce)
        l = cur_l if length is None else _coerce(length, eLength)
        t = cur_t if temperature is None else _coerce(temperature, eTemperature)
        ok(self._parent.SapModel.SetPresentUnits_2(int(f), int(l), int(t)), "set units")
        if self._parent._verbose:
            print(f"Present units set to {f.name}, {l.name}, {t.name}.")
        return self

    @property
    def force(self) -> eForce:
        return self.get()[0]

    @property
    def length(self) -> eLength:
        return self.get()[1]

    @property
    def temperature(self) -> eTemperature:
        return self.get()[2]

    # ------------------------------------------------------------------
    # baseUnits reporting bridge
    # ------------------------------------------------------------------

    def use_report_system(self, system: Any = None) -> "Units":
        """Choose the ``baseUnits`` system that conversions resolve against.

        Args:
            system: A ``baseUnits`` system namespace/module exposing unit
                attributes (e.g. ``baseUnits.systems.kN_m_s``), or ``None``
                to use the default top-level ``baseUnits`` system
                (``N-mm-tonne-s``).

        Returns ``self`` for chaining.
        """
        if system is None:
            try:
                import baseUnits as system  # type: ignore[no-redef]
            except ImportError as exc:
                raise ETABSError(
                    "baseUnits is not installed; pass an explicit `system` or "
                    "`pip install baseUnits`."
                ) from exc
        self._report = system
        return self

    @property
    def report(self) -> Any:
        """The active baseUnits report system (defaulting on first access)."""
        if self._report is None:
            self.use_report_system(None)
        return self._report

    @property
    def force_factor(self) -> float:
        """Multiply an ETABS force (present units) to get report base units."""
        name = self.force.name
        bu = _FORCE_TO_BASEUNITS.get(name)
        if bu is None:
            raise ETABSError(f"No baseUnits mapping for force unit '{name}'.")
        return float(getattr(self.report, bu))

    @property
    def length_factor(self) -> float:
        """Multiply an ETABS length (present units) to get report base units."""
        name = self.length.name
        bu = _LENGTH_TO_BASEUNITS.get(name)
        if bu is None:
            raise ETABSError(f"No baseUnits mapping for length unit '{name}'.")
        return float(getattr(self.report, bu))

    def factor(self, dim: str) -> float:
        """Conversion factor (ETABS present units -> report base) for ``dim``.

        Supported dims: ``force``, ``length``/``disp``, ``moment``,
        ``stress``/``pressure``, ``area``.
        """
        f, l = self.force_factor, self.length_factor
        table = {
            "force": f,
            "length": l,
            "disp": l,
            "displacement": l,
            "moment": f * l,
            "stress": f / l**2,
            "pressure": f / l**2,
            "area": l**2,
        }
        try:
            return table[dim]
        except KeyError:
            raise ETABSError(
                f"Unknown dimension '{dim}'. Use one of {sorted(table)}."
            ) from None

    def to_base(self, value: float, dim: str = "force") -> float:
        """Convert an ETABS value (present units) into report base units."""
        return value * self.factor(dim)

    def __repr__(self) -> str:
        try:
            f, l, t = self.get()
            return f"Units({f.name}, {l.name}, {t.name})"
        except Exception:  # noqa: BLE001 — repr must never raise
            return "Units(<unavailable>)"


def _coerce(value: str | int, enum_cls: type) -> Any:
    """Coerce a name / int / enum member into ``enum_cls``."""
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls[value]
        except KeyError:
            valid = ", ".join(m.name for m in enum_cls if m.value != 0)
            raise ETABSError(
                f"Unknown {enum_cls.__name__} '{value}'. Valid: {valid}."
            ) from None
    return enum_cls(int(value))
