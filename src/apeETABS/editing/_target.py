"""``_Target`` — resolve a targeting form into a name + ``eItemType``.

Bulk edit/assign operations (ADR 0005 §4) accept exactly one of three
targeting forms, mapping to the OAPI ``eItemType`` enum:

* ``name="B12"``      -> ``eItemType.Objects`` (0): a single named object.
* ``group="Beams"``   -> ``eItemType.Group`` (1): every object in a group.
* ``selected=True``   -> ``eItemType.SelectedObjects`` (2): the GUI selection.

Exactly one form must be supplied; zero or more than one is ambiguous and
raises ``ValueError`` (per ADR 0005 §4: "ambiguous combinations raise").
The resolved ``.name``/``.item_type`` pass straight through to the COM call.
"""

from __future__ import annotations

from dataclasses import dataclass

# eItemType codes (.claude/skills/etabs-oapi/reference/enums.md).
_OBJECTS = 0
_GROUP = 1
_SELECTED = 2


@dataclass(frozen=True)
class _Target:
    """A resolved edit/assign target: the OAPI ``Name`` + ``eItemType`` code.

    For ``eItemType.Objects`` ``name`` is the object's unique name; for
    ``Group`` it is the group name; for ``SelectedObjects`` the name is
    ignored by ETABS and is left as ``""``.
    """

    name: str
    item_type: int

    @classmethod
    def resolve(
        cls,
        name: str | None = None,
        *,
        group: str | None = None,
        selected: bool = False,
    ) -> "_Target":
        """Resolve exactly one targeting form into a :class:`_Target`.

        Args:
            name: A single object's unique name (``eItemType.Objects``).
            group: A group name (``eItemType.Group``).
            selected: Target the current GUI selection
                (``eItemType.SelectedObjects``).

        Raises:
            ValueError: If zero, or more than one, targeting form is given
                (ambiguous — ADR 0005 §4).
        """
        chosen = [
            ("name", name is not None),
            ("group", group is not None),
            ("selected", bool(selected)),
        ]
        active = [label for label, on in chosen if on]
        if len(active) != 1:
            raise ValueError(
                "Specify exactly one of name=, group= or selected=True "
                f"(got {active or 'none'})."
            )

        if name is not None:
            return cls(name=str(name), item_type=_OBJECTS)
        if group is not None:
            return cls(name=str(group), item_type=_GROUP)
        return cls(name="", item_type=_SELECTED)
