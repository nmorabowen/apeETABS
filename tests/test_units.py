"""Tests for the Units composite: present units + baseUnits bridge."""

from __future__ import annotations

import baseUnits as u
import pytest

from apeETABS.enums import eForce, eLength, eTemperature
from apeETABS.errors import ETABSError


def test_get_returns_enum_triple(etabs):
    f, ln, t = etabs.units.get()
    assert (f, ln, t) == (eForce.kN, eLength.m, eTemperature.C)


def test_set_by_name_updates_present_units(etabs):
    etabs.units.set("kip", "inch")
    f, ln, t = etabs.units.get()
    assert f is eForce.kip
    assert ln is eLength.inch
    assert t is eTemperature.C  # unspecified -> unchanged


def test_set_by_enum(etabs):
    etabs.units.set(force=eForce.N, length=eLength.mm)
    assert etabs.units.force is eForce.N
    assert etabs.units.length is eLength.mm


def test_set_unknown_name_raises(etabs):
    with pytest.raises(ETABSError):
        etabs.units.set("furlong")


def test_force_and_length_factors(etabs):
    # Default report system is N-mm based; present units kN, m.
    etabs.units.set("kN", "m")
    assert etabs.units.force_factor == pytest.approx(u.kN)
    assert etabs.units.length_factor == pytest.approx(u.m)


def test_derived_factors(etabs):
    etabs.units.set("kN", "m")
    f, ln = u.kN, u.m
    assert etabs.units.factor("moment") == pytest.approx(f * ln)
    assert etabs.units.factor("stress") == pytest.approx(f / ln**2)
    assert etabs.units.factor("area") == pytest.approx(ln**2)
    assert etabs.units.factor("disp") == pytest.approx(ln)


def test_factor_unknown_dim_raises(etabs):
    with pytest.raises(ETABSError):
        etabs.units.factor("torque")


def test_to_base_converts(etabs):
    etabs.units.set("kN", "m")
    # 10 kN (present) -> base units (N) == 10 * u.kN
    assert etabs.units.to_base(10.0, "force") == pytest.approx(10.0 * u.kN)
