"""Results layer (ADR 0003): the ``Results`` composite + typed snapshots.

Public surface:

* :class:`~apeETABS.results.Results.Results` — the ``e.results`` factory.
* :class:`~apeETABS.results.Displacements.Displacements`,
  :class:`~apeETABS.results.StoryDrifts.StoryDrifts`,
  :class:`~apeETABS.results.StoryForces.StoryForces`,
  :class:`~apeETABS.results.WallForces.WallForces` — detached snapshots.
* :class:`~apeETABS.results.CentersMassRigidity.CentersMassRigidity`,
  :class:`~apeETABS.results.StoryStiffness.StoryStiffness`,
  :class:`~apeETABS.results.TorsionIrregularity.TorsionIrregularity` —
  seismic-irregularity snapshots (CM/CR + mass, soft story, TIR).
* :class:`~apeETABS.results.Profile.Profile` — the shared profile dataclass.
"""

from __future__ import annotations

from .CentersMassRigidity import CentersMassRigidity
from .Displacements import Displacements
from .Profile import Profile
from .Reactions import Reactions
from .Results import Results
from .StoryDrifts import StoryDrifts
from .StoryForces import StoryForces
from .StoryStiffness import StoryStiffness
from .TorsionIrregularity import TorsionIrregularity
from .WallForces import WallForces

__all__ = [
    "Results",
    "Displacements",
    "Reactions",
    "StoryDrifts",
    "StoryForces",
    "WallForces",
    "CentersMassRigidity",
    "StoryStiffness",
    "TorsionIrregularity",
    "Profile",
]
