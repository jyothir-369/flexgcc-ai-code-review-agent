"""Tests for the schemas module."""

"""Unit tests for output schemas."""

import pytest
from pydantic import ValidationError

from diff_review_agent.schemas import (
    Finding,
    ReviewResult,
    ReviewMetadata,
    Severity,
    Category,
)


def test_finding_valid():
    f = Finding(
        category=Category.bug,
        severity=Severity.critical,
        title="Test finding",
        description="Description",
        evidence="Evidence",
        recommendation="Recommendation",
        confidence=0.9,
        is_speculative=False,
    )
    assert f.category == Category.bug
    assert f.severity == Severity.critical
    assert f.confidence == 0.9


def test_finding_invalid_confidence():
    with pytest.raises(ValidationError):
        Finding(
            category=Category.bug,
            severity=Severity.critical,
            title="Test",
            description="Description",
            evidence="Evidence",
            recommendation="Recommendation",
            confidence=1.5,
        )


def test_finding_invalid_category():
    with pytest.raises(ValidationError):
        Finding(
            category="invalid",
            severity=Severity.critical,
            title="Test",
            description="Description",
            evidence="Evidence",
            recommendation="Recommendation",
            confidence=0.9,
        )


def test_review_result_valid():
    r = ReviewResult(
        summary="Summary",
        overall_risk="low",
        findings=[],
        review_metadata=ReviewMetadata(
            input_type="file",
            reviewed_file_count=0,
            model_provider_mode="demo",
        ),
    )
    assert r.overall_risk == "low"


def test_review_result_invalid_overall_risk():
    with pytest.raises(ValidationError):
        ReviewResult(
            summary="Summary",
            overall_risk="invalid",
            findings=[],
            review_metadata=ReviewMetadata(
                input_type="file",
                reviewed_file_count=0,
                model_provider_mode="demo",
            ),
        )


def test_finding_with_line_numbers():
    f = Finding(
        category=Category.risk,
        severity=Severity.high,
        title="Risk",
        description="Description",
        file="foo.py",
        line_start=10,
        line_end=15,
        evidence="Evidence",
        recommendation="Recommendation",
        confidence=0.8,
    )
    assert f.file == "foo.py"
    assert f.line_start == 10
    assert f.line_end == 15