"""Correlation ID middleware tests."""

import pytest
from middleware.correlation import correlation_id_var, get_correlation_id


def test_default_correlation_id():
    assert get_correlation_id() == ""


def test_set_and_get_correlation_id():
    token = correlation_id_var.set("test-corr-123")
    try:
        assert get_correlation_id() == "test-corr-123"
    finally:
        correlation_id_var.reset(token)
