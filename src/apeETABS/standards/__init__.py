"""Standards layer (ADR 0008): the ``e.standards`` opinionated-preset tier.

Public surface:

* :class:`~apeETABS.standards.Standards.Standards` — the ``e.standards``
  composite of code-keyed presets (materials / seismic_patterns / spectrum /
  combos / mass_source). It composes the neutral ``e.define`` / ``e.assign``
  builders (ADR 0006) and issues no COM of its own.

SCAFFOLD ONLY: all methods are stubbed (raise ``NotImplementedError``). The
per-code opinionated logic, and the missing ``e.define`` compile targets
(``response_spectrum_function`` / ``load_case`` / ``mass_source``) land in a
later phase per ADR 0008.
"""

from __future__ import annotations

from .Standards import Standards

__all__ = [
    "Standards",
]
