"""Tests for the standards scaffold (P11, ADR 0008).

`e.standards` is wired onto the session and every preset method is a documented
stub (raises NotImplementedError) until the per-code logic lands. These tests
lock the wiring + the stub contract, mirroring the creation-stub tests.
"""

from __future__ import annotations

import pytest

from apeETABS.standards import Standards

from .conftest import bind, make_mock


def test_standards_is_wired_on_the_session():
    e = bind(make_mock(locked=False))
    assert isinstance(e.standards, Standards)
    assert e.standards._parent is e


@pytest.mark.parametrize(
    ("method", "match"),
    [
        ("materials", "Standards.materials"),
        ("seismic_patterns", "Standards.seismic_patterns"),
        ("gravity_loads", "Standards.gravity_loads"),
        ("spectrum", "Standards.spectrum"),
        ("combos", "Standards.combos"),
        ("mass_source", "Standards.mass_source"),
    ],
)
def test_standards_stub_raises(method, match):
    e = bind(make_mock(locked=False))
    with pytest.raises(NotImplementedError, match=match):
        getattr(e.standards, method)()
