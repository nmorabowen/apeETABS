"""Structured, machine-readable outcomes (ADR 0007 §4).

The agentic verbs (``validate``/``plan``/``run``) never return bare booleans
or raise prose-only exceptions across the boundary: they return typed,
JSON-serializable :class:`Outcome` objects. An :class:`Outcome` carries a
success flag, the ordered list of operations (the plan / run record) and a
list of structured :class:`Finding` objects — each with a machine ``code``
and a remediation ``hint`` — so an agent can *read* the result and
self-correct instead of parsing English (ADR 0007 §4, alternative 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    """A single structured diagnostic — a coded error/warning, not prose.

    Attributes:
        code: A stable machine code (e.g. ``"UNKNOWN_CASE"``) an agent can
            branch on. UPPER_SNAKE by convention.
        message: A human-readable description of what went wrong.
        hint: A remediation hint (e.g. "define section 'R1' first"); empty
            when none applies.
        severity: ``"error"`` (blocks success), ``"warning"`` or ``"info"``.
    """

    code: str
    message: str
    hint: str = ""
    severity: str = "error"

    def to_dict(self) -> dict:
        """JSON-serializable view of this finding."""
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "severity": self.severity,
        }


@dataclass
class Outcome:
    """The typed result of a pipeline verb (validate/plan/run).

    Attributes:
        ok: Whether the verb succeeded (no blocking findings).
        operations: Ordered operation/diff list — the plan (dry-run) or the
            run record, as plain strings/data.
        findings: Structured diagnostics (see :class:`Finding`).
        data: Free-form, JSON-serializable payload (e.g. produced figure
            handles, the resolved case list, a record id).
    """

    ok: bool
    operations: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[Finding]:
        """Findings whose severity is ``"error"`` (the blocking ones)."""
        return [f for f in self.findings if f.severity == "error"]

    def to_dict(self) -> dict:
        """JSON-serializable view of this outcome (findings recursed)."""
        return {
            "ok": self.ok,
            "operations": list(self.operations),
            "findings": [f.to_dict() for f in self.findings],
            "data": dict(self.data),
        }
