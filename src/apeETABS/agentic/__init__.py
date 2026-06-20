"""Agentic scaffolding (ADR 0007): specs as the agent interface, one pipeline.

The public surface for LLM-driven use of apeETABS. Agents author serializable
**specs** (:class:`ReportSpec`, :class:`ModelSpec`, :class:`EditSpec`) and the
single gated :func:`run_spec` pipeline executes them
(``propose -> validate -> plan -> [gate] -> run -> record``). Verbs return
structured, JSON-serializable :class:`Outcome` / :class:`Finding` objects so an
agent can self-correct (ADR 0007 §4); the :class:`AgentPolicy` governs the
approval gate by risk tier (ADR 0007 §3).

This is a **top-level** API, not a session composite — it is *not* wired into
``apeETABS._COMPOSITES``. Import it directly::

    from apeETABS.agentic import ReportSpec, AgentPolicy, run_spec
"""

from __future__ import annotations

from .edit_spec import EditSpec
from .model_spec import ModelSpec
from .outcomes import Finding, Outcome
from .pipeline import run_spec
from .policy import TIERS, AgentPolicy, UnknownTierError
from .report_spec import ReportSpec
from .spec import Spec

__all__ = [
    "Finding",
    "Outcome",
    "AgentPolicy",
    "UnknownTierError",
    "TIERS",
    "Spec",
    "ReportSpec",
    "ModelSpec",
    "EditSpec",
    "run_spec",
]
