"""Profile — a small, self-contained vertical profile snapshot.

A :class:`Profile` is the shared currency between the results layer and the
plotting layer: a value-per-elevation series in report units, already
detached from any ETABS session (no live COM, conversions baked). Both
:class:`~apeETABS.results.Displacements.Displacements` and
:class:`~apeETABS.results.StoryDrifts.StoryDrifts` emit one via ``.profile()``,
and the pure plotting functions consume it directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Profile:
    """A value-per-elevation series, roof->base ordered, in report units.

    Attributes:
        elevation: Elevations in report length units (roof first, base last).
        value: The profiled quantity (report units, or dimensionless for
            drift), aligned with ``elevation``.
        stories: Story names aligned with ``elevation``.
        label: Optional series label (e.g. a joint label or case name).
        unit: Axis-label unit string, e.g. ``"m"``; ``""`` for dimensionless.
    """

    elevation: np.ndarray   # report length units, roof->base order
    value: np.ndarray       # report units (or dimensionless for drift)
    stories: list[str]
    label: str | None = None
    unit: str = ""          # axis label, e.g. "m" or "" for drift

    @property
    def peak(self) -> tuple[float, str]:
        """The largest-magnitude value and the story where it occurs.

        Returns ``(max |value|, story)`` — magnitude-based so it works for
        signed responses (the larger of +/- wins). The returned value keeps
        its original sign.
        """
        if self.value.size == 0:
            return 0.0, ""
        idx = int(np.argmax(np.abs(self.value)))
        return float(self.value[idx]), self.stories[idx]
