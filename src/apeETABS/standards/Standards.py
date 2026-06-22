"""Standards — the ``e.standards`` opinionated-preset composite (ADR 0008).

A peer of the builder composites that holds **conventions only**: standard
materials, seismic load patterns, response spectra, load combinations, and mass
sources, keyed by design code (NEC, ASCE/ACI, …). It issues **no COM calls of
its own** — every method composes the neutral ``e.define`` / ``e.assign``
primitives through the ADR 0002 Parent Contract, so the lock guard (ADR 0005)
and present-units contract (ADR 0006 §3) are inherited unchanged.

    e.standards.materials(code="NEC")        # -> e.define.material(...) xN
    e.standards.seismic_patterns(...)        # -> e.define.load_pattern(...) xN
    e.standards.spectrum(code="NEC-SE-DS")   # -> e.define.response_spectrum_function(...)
    e.standards.combos(code="NEC")           # -> e.define.combo(...) xN
    e.standards.mass_source(...)             # -> e.define.mass_source(...)

SCAFFOLD ONLY: every method below is a stub (raises ``NotImplementedError``),
mirroring the deferred-builder convention in ``Define``. The opinionated logic
lands per design code in a later phase; the compile targets are the neutral
``e.define`` primitives named in each docstring (some of which — e.g.
``response_spectrum_function`` / ``mass_source`` — are themselves still to be
added per ADR 0008 §2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .._session import _SessionBase


class Standards:
    """Opinionated, code-keyed presets composed from the neutral builders."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    def materials(self, *args: Any, **kwargs: Any) -> Any:
        """Create the standard material set for a design ``code``.

        Composes :meth:`Define.material` / :meth:`Define.material_from_catalog`.
        Not implemented yet (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.materials is not implemented yet (ADR 0008 scaffold)."
        )

    # ------------------------------------------------------------------
    # Load patterns & loadings
    # ------------------------------------------------------------------

    def seismic_patterns(self, *args: Any, **kwargs: Any) -> Any:
        """Create the standard seismic load-pattern set (Sx/Sy/Ex/Ey…).

        Composes :meth:`Define.load_pattern`. Not implemented yet
        (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.seismic_patterns is not implemented yet (ADR 0008 scaffold)."
        )

    def gravity_loads(self, *args: Any, **kwargs: Any) -> Any:
        """Apply the standard gravity loadings (dead/live distributions).

        Composes :meth:`Assign.loads` over the relevant objects. Not
        implemented yet (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.gravity_loads is not implemented yet (ADR 0008 scaffold)."
        )

    # ------------------------------------------------------------------
    # Spectra (native formula OR external-library adapter -> Define sink)
    # ------------------------------------------------------------------

    def spectrum(self, *args: Any, **kwargs: Any) -> Any:
        """Create a response-spectrum function from a code formula or library.

        Producer side (code formula / external-library adapter, lazily
        imported) -> consumer :meth:`Define.response_spectrum_function`
        (ADR 0008 §4). Not implemented yet (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.spectrum is not implemented yet (ADR 0008 scaffold)."
        )

    # ------------------------------------------------------------------
    # Load combinations
    # ------------------------------------------------------------------

    def combos(self, *args: Any, **kwargs: Any) -> Any:
        """Create the standard load-combination set for a design ``code``.

        Composes :meth:`Define.combo`. Not implemented yet (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.combos is not implemented yet (ADR 0008 scaffold)."
        )

    # ------------------------------------------------------------------
    # Mass source
    # ------------------------------------------------------------------

    def mass_source(self, *args: Any, **kwargs: Any) -> Any:
        """Set the standard mass source (e.g. Dead + a fraction of Live).

        Composes :meth:`Define.mass_source`. Not implemented yet
        (ADR 0008 scaffold).
        """
        raise NotImplementedError(
            "Standards.mass_source is not implemented yet (ADR 0008 scaffold)."
        )
