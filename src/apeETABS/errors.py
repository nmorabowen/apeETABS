"""Errors and the checked-return helper for the ETABS OAPI.

Every ETABS OAPI function returns an integer status code as the *last*
element of its result: ``0`` means success, any nonzero value means the
call failed. In Python (comtypes) a function with ``ref``/``out``
parameters returns a list ``[out1, out2, ..., ret]`` — the outputs first,
the status last. :func:`ok` centralizes that convention so call sites read
cleanly and always raise on failure instead of silently continuing.
"""

from __future__ import annotations

from typing import Any


class ETABSError(RuntimeError):
    """Raised when the ETABS application or an OAPI call fails."""


class ConnectionError(ETABSError):
    """Raised when attaching to or launching ETABS fails."""


def ok(result: Any, what: str = "ETABS API call") -> Any:
    """Validate an ETABS OAPI return and strip the trailing status code.

    Args:
        result: The raw value returned by an OAPI method. Either a bare
            ``int`` status (for functions with no out-parameters) or a
            sequence ``[out1, ..., ret]`` whose last element is the status.
        what: Short label for the call, used in the error message.

    Returns:
        ``None`` when the call had no out-parameters (bare status int);
        the single output when there was exactly one; otherwise the list
        of outputs (status removed).

    Raises:
        ETABSError: If the status code is nonzero.

    Example:
        >>> ok(SapModel.SetPresentUnits_2(4, 6, 2), "set units")      # -> None
        >>> name = ok(SapModel.FrameObj.AddByCoord(0,0,0, 0,0,10, ' ', 'R1'),
        ...           "add frame")                                     # -> name
    """
    # Bare status int: functions with no out-parameters.
    if isinstance(result, int):
        if result != 0:
            raise ETABSError(f"{what} failed (ret={result}).")
        return None

    # Sequence form: [out1, ..., ret].
    try:
        *outputs, ret = result
    except (TypeError, ValueError) as exc:  # not unpackable / empty
        raise ETABSError(
            f"{what} returned an unexpected value: {result!r}"
        ) from exc

    if ret != 0:
        raise ETABSError(f"{what} failed (ret={ret}).")

    if not outputs:
        return None
    if len(outputs) == 1:
        return outputs[0]
    return outputs
