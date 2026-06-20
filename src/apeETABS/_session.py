"""
_SessionBase — shared base for objects that own an ETABS OAPI connection.
=========================================================================

Composite Parent Contract
-------------------------
Composites receive the session as ``self._parent`` and may access:

* ``_parent.SapModel``    — the ``cSapModel`` object (the model)
* ``_parent.etabs``       — the ``cOAPI`` object (the application)
* ``_parent._verbose: bool`` — logging verbosity flag
* ``_parent.is_active: bool`` — True once connected
* sibling composites — a composite may read ``units``, ``tables``,
  ``stories``, ``results``, ``plot`` on the parent (e.g. ``units`` to
  convert; the ``e.plot`` sugar fetches snapshots via ``_parent.results``
  per ADR 0001 §plotting and ADR 0004 §4). Composites collaborate only
  through this contract — never by inheritance.

Subclasses MUST define ``_COMPOSITES`` as a class-level tuple of
``(attr_name, relative_module, class_name, is_optional)`` entries, mirroring
the apeGmsh convention. Composites are instantiated lazily in
:meth:`begin` and each is handed ``self``.

Connection modes (resolved in :meth:`begin`)
--------------------------------------------
* ``process_id=<pid>``  — attach to a specific running ETABS instance.
* ``attach=True``       — attach to the active running ETABS instance.
* otherwise             — launch a new ETABS (``program_path`` if given,
  else the latest installed version), then open ``path`` if provided.

Sessions we *launched* are closed on :meth:`end`; sessions we *attached*
to are left running (you are borrowing the user's open program).
"""

from __future__ import annotations

import importlib
import warnings
from pathlib import Path
from typing import ClassVar

from .errors import ConnectionError, ModelLockedError, ok

# ETABS COM identifiers.
_PROGID = "CSI.ETABS.API.ETABSObject"
_HELPER = "ETABSv1.Helper"


class _SessionBase:
    """Base for objects that own an ETABS OAPI connection and composites."""

    _COMPOSITES: ClassVar[tuple[tuple[str, str, str, bool], ...]] = ()

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        attach: bool = False,
        process_id: int | None = None,
        program_path: str | Path | None = None,
        visible: bool = True,
        verbose: bool = False,
    ) -> None:
        self.path: Path | None = Path(path) if path else None
        self.attach: bool = attach
        self.process_id: int | None = process_id
        self.program_path: Path | None = Path(program_path) if program_path else None
        self.visible: bool = visible
        self._verbose: bool = verbose

        # Connection state, populated by begin().
        self.etabs = None        # cOAPI  (the application object)
        self.SapModel = None     # cSapModel  (the model)
        self._active: bool = False
        self._started_by_us: bool = False

        # Pre-declare composite slots as None.
        for attr_name, _, _, _ in self._COMPOSITES:
            setattr(self, attr_name, None)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True once a SapModel connection is established."""
        return self._active

    # ------------------------------------------------------------------
    # Model lock cycle (ADR 0005 §2) — SAFETY-CRITICAL.
    #
    # ETABS locks the model after analysis. Unlocking to edit *deletes all
    # analysis results*, so we never unlock implicitly: mutating composites
    # call ``_require_unlocked()``, which raises and tells the user to call
    # ``e.unlock()`` — making the destruction of results a conscious choice.
    # ------------------------------------------------------------------

    @property
    def is_locked(self) -> bool:
        """Whether the model is locked (locked after analysis runs)."""
        return bool(ok(self.SapModel.GetModelIsLocked(), "GetModelIsLocked"))

    def lock(self) -> "_SessionBase":
        """Lock the model (``SetModelIsLocked(True)``). Returns ``self``."""
        ok(self.SapModel.SetModelIsLocked(True), "SetModelIsLocked(True)")
        if self._verbose:
            print("Model locked.")
        return self

    def unlock(self) -> "_SessionBase":
        """Unlock the model so it can be edited. Returns ``self``.

        WARNING: unlocking **discards all analysis results** (ETABS deletes
        them on ``SetModelIsLocked(False)``). This is irreversible; we warn
        loudly so the loss is never silent. Re-run the analysis afterwards.
        """
        # Warn even when not verbose — the results loss must never be silent.
        warnings.warn(
            "Unlocking the ETABS model DISCARDS all analysis results; "
            "re-run the analysis after editing.",
            stacklevel=2,
        )
        if self._verbose:
            print("Unlocking model — analysis results are being discarded.")
        ok(self.SapModel.SetModelIsLocked(False), "SetModelIsLocked(False)")
        return self

    def _require_unlocked(self, op: str) -> None:
        """Guard a mutating ``op``; raise :class:`ModelLockedError` if locked.

        Mutating composites (``e.edit``, ``e.assign``) call this before any
        write. We never unlock implicitly — the user must call ``e.unlock()``.
        """
        if self.is_locked:
            raise ModelLockedError(
                f"Cannot {op}: the model is locked (analysis has been run). "
                "Call e.unlock() first — note that unlocking discards all "
                "analysis results."
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> "_SessionBase":
        """Establish the ETABS connection and create composites.

        Returns ``self`` for chaining. Raises :class:`ConnectionError`
        if no instance can be attached/launched or the model cannot open.
        """
        if self._active:
            raise ConnectionError(f"{type(self).__name__} is already connected.")

        helper = self._make_helper()
        self.etabs = self._resolve_etabs(helper)
        self.SapModel = self.etabs.SapModel
        if self.SapModel is None:
            raise ConnectionError("Connected to ETABS but SapModel is None.")

        if self.path is not None:
            self._open_model(self.path)

        self._create_composites()
        self._active = True
        if self._verbose:
            print(repr(self))
        return self

    # Alias — reads naturally for a connection.
    connect = begin

    def end(self, *, save: bool = False) -> None:
        """Close the connection.

        If we launched ETABS, the application is exited (saving first when
        ``save=True``). If we attached to an already-running instance, the
        program is left open and only the local references are dropped.
        """
        if not self._active:
            return
        if self._started_by_us and self.etabs is not None:
            try:
                self.etabs.ApplicationExit(bool(save))
            except Exception as exc:  # noqa: BLE001 — never raise on teardown
                if self._verbose:
                    print(f"ApplicationExit raised on end(): {exc!r}")
        self.SapModel = None
        self.etabs = None
        self._active = False

    # Context-manager support.
    def __enter__(self) -> "_SessionBase":
        return self.begin()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end()

    # ------------------------------------------------------------------
    # Connection internals
    # ------------------------------------------------------------------

    @staticmethod
    def _make_helper():
        """Create the ETABS COM helper, cast to ``cHelper``."""
        import comtypes.client

        try:
            helper = comtypes.client.CreateObject(_HELPER)
            return helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
        except Exception as exc:  # noqa: BLE001
            raise ConnectionError(
                "Could not create the ETABSv1 COM helper. Is ETABS installed "
                "and has its API been registered?"
            ) from exc

    def _resolve_etabs(self, helper):
        """Attach to or launch ETABS per the configured mode."""
        # 1) Attach to a specific running instance by process id.
        if self.process_id is not None:
            try:
                etabs = helper.GetObjectProcess(_PROGID, self.process_id)
            except Exception as exc:  # noqa: BLE001
                raise ConnectionError(
                    f"No ETABS instance with process id {self.process_id}."
                ) from exc
            self._started_by_us = False
            return etabs

        # 2) Attach to the active running instance.
        if self.attach:
            try:
                etabs = helper.GetObject(_PROGID)
            except Exception as exc:  # noqa: BLE001
                raise ConnectionError(
                    "No running ETABS instance found to attach to."
                ) from exc
            self._started_by_us = False
            return etabs

        # 3) Launch a new instance (specific exe, else latest installed).
        try:
            if self.program_path is not None:
                etabs = helper.CreateObject(str(self.program_path))
            else:
                etabs = helper.CreateObjectProgID(_PROGID)
            etabs.ApplicationStart()
        except Exception as exc:  # noqa: BLE001
            where = self.program_path or "the latest installed version"
            raise ConnectionError(f"Could not start ETABS from {where}.") from exc
        self._started_by_us = True
        if not self.visible:
            try:
                etabs.Hide()
            except Exception:  # noqa: BLE001 — visibility is best-effort
                pass
        return etabs

    def _open_model(self, path: Path) -> None:
        """Open an existing model file in the connected application."""
        if not path.exists():
            raise ConnectionError(f"Model file not found: {path}")
        # Route the COM return through ok() (the "every COM return goes through
        # ok()" invariant); ok() raises ETABSError on a nonzero status.
        ok(self.SapModel.File.OpenFile(str(path)), f"open model {path}")

    # ------------------------------------------------------------------
    # Composite creation
    # ------------------------------------------------------------------

    def _create_composites(self) -> None:
        """Instantiate each composite declared in ``_COMPOSITES``."""
        for attr_name, module_path, class_name, is_optional in self._COMPOSITES:
            try:
                mod = importlib.import_module(module_path, package=__package__)
                cls = getattr(mod, class_name)
                setattr(self, attr_name, cls(self))
            except ImportError:
                if not is_optional:
                    raise
                setattr(self, attr_name, None)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        if not self._active:
            return f"{type(self).__name__}(disconnected)"
        mode = (
            f"pid={self.process_id}" if self.process_id is not None
            else "attached" if self.attach
            else "launched"
        )
        model = self.path.name if self.path else "<current>"
        return f"{type(self).__name__}({mode}, model={model})"
