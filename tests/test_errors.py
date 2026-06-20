"""Tests for ``errors.ok`` — the checked-return / status-stripping helper."""

from __future__ import annotations

import pytest

from apeETABS.errors import ETABSError, ok


def test_bare_status_zero_returns_none():
    assert ok(0, "set units") is None


def test_bare_status_nonzero_raises():
    with pytest.raises(ETABSError):
        ok(1, "set units")


def test_seq_no_outputs_returns_none():
    assert ok([0]) is None


def test_seq_single_output_returned_unwrapped():
    assert ok(["value", 0]) == "value"


def test_seq_multiple_outputs_returned_as_list():
    assert ok([1, 2, 3, 0]) == [1, 2, 3]


def test_seq_nonzero_status_raises():
    with pytest.raises(ETABSError):
        ok([1, 2, 3, 7])


def test_unpack_failure_raises_etabserror():
    # Empty sequence cannot yield a status -> wrapped as ETABSError.
    with pytest.raises(ETABSError):
        ok([])
