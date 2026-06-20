"""``New`` composite — model templates (the starting point for creation).

The ``e.new`` surface (ADR 0006 §6): wrap ``cFile.New*`` to start a fresh model
from a template — ``blank``, ``grid_only``, ``steel_deck``. A new model is
**unlocked**, so the ADR 0005 lock guard is naturally satisfied; these template
calls therefore do *not* assert unlocked (they reset the model, not mutate a
locked one) — but ``e.create`` / ``e.define`` still guard, to stay safe on a
reused session.

When ``units`` is supplied, the present units are set *after* the template is
created (templates author their geometry in their own default units; setting
present units afterward only changes the reporting/authoring contract — ADR
0006 §3). ``units`` is forwarded straight to ``e.units.set`` so it accepts the
same readable-name / enum / int forms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from ..errors import ok

if TYPE_CHECKING:
    from .._session import _SessionBase

# (force, length[, temperature]) accepted by ``e.units.set``.
_Units = Sequence[object]


class New:
    """Model-template starters wrapping ``cFile.NewBlank/NewGridOnly/NewSteelDeck``."""

    def __init__(self, parent: "_SessionBase") -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_units(self, units: _Units | None) -> None:
        """Set present units from a ``(force, length[, temp])`` tuple, if given."""
        if units is None:
            return
        self._parent.units.set(*units)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def blank(self, *, units: _Units | None = None) -> "_SessionBase":
        """Create a new blank model via ``cFile.NewBlank``.

        Args:
            units: Optional ``(force, length[, temperature])`` to set as the
                present units after creating the model (ADR 0006 §3/§6).

        Returns:
            The parent session (for chaining).
        """
        ok(self._parent.SapModel.File.NewBlank(), "NewBlank")
        self._apply_units(units)
        if self._parent._verbose:
            print("Created new blank model.")
        return self._parent

    def grid_only(
        self,
        *,
        stories: int = 1,
        story_height: float = 3.0,
        bottom_height: float = 3.0,
        lines_x: int = 2,
        lines_y: int = 2,
        spacing_x: float = 6.0,
        spacing_y: float = 6.0,
        units: _Units | None = None,
    ) -> "_SessionBase":
        """Create a new grid-only model via ``cFile.NewGridOnly``.

        Dimensional arguments (``story_height``, ``spacing_x`` …) are in the
        template's own default units; pass ``units`` to set the present units
        afterward (ADR 0006 §3/§6).

        Args:
            stories: Number of stories (``NumberStorys``).
            story_height: Typical story height (``TypicalStoryHeight``).
            bottom_height: Bottom story height (``BottomStoryHeight``).
            lines_x, lines_y: Grid line counts (``NumberLinesX/Y``).
            spacing_x, spacing_y: Grid spacings (``SpacingX/Y``).
            units: Optional present units to set after creation.

        Returns:
            The parent session (for chaining).
        """
        ok(
            self._parent.SapModel.File.NewGridOnly(
                int(stories),
                float(story_height),
                float(bottom_height),
                int(lines_x),
                int(lines_y),
                float(spacing_x),
                float(spacing_y),
            ),
            "NewGridOnly",
        )
        self._apply_units(units)
        if self._parent._verbose:
            print("Created new grid-only model.")
        return self._parent

    def steel_deck(
        self,
        *,
        stories: int = 1,
        story_height: float = 3.0,
        bottom_height: float = 3.0,
        lines_x: int = 2,
        lines_y: int = 2,
        spacing_x: float = 6.0,
        spacing_y: float = 6.0,
        units: _Units | None = None,
    ) -> "_SessionBase":
        """Create a new steel-deck model via ``cFile.NewSteelDeck``.

        Same arguments as :meth:`grid_only` (the ``cFile.NewSteelDeck`` template
        shares the grid signature). ``units`` sets present units afterward.

        Returns:
            The parent session (for chaining).
        """
        ok(
            self._parent.SapModel.File.NewSteelDeck(
                int(stories),
                float(story_height),
                float(bottom_height),
                int(lines_x),
                int(lines_y),
                float(spacing_x),
                float(spacing_y),
            ),
            "NewSteelDeck",
        )
        self._apply_units(units)
        if self._parent._verbose:
            print("Created new steel-deck model.")
        return self._parent
