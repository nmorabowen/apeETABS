"""Results layer (ADR 0003): the ``Results`` composite + typed snapshots.

Public surface:

* :class:`~apeETABS.results.Results.Results` — the ``e.results`` factory.
* :class:`~apeETABS.results.Displacements.Displacements`,
  :class:`~apeETABS.results.StoryDrifts.StoryDrifts` — detached snapshots.
* :class:`~apeETABS.results.Profile.Profile` — the shared profile dataclass.
"""

from __future__ import annotations

from .Displacements import Displacements
from .Profile import Profile
from .Results import Results
from .StoryDrifts import StoryDrifts

__all__ = ["Results", "Displacements", "StoryDrifts", "Profile"]
