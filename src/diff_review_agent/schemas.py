"""Pydantic schemas for the structured review output contract."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class Category(str, Enum):
    bug = "bug"
    risk = "risk"
    missing_test = "missing_test"
    style = "style"


class Finding(BaseModel):
    category: Category
    severity: Severity
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    file: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    evidence: str = Field(..., min_length=1, max_length=2000)
    recommendation: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_speculative: bool = False

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class ReviewMetadata(BaseModel):
    input_type: str
    reviewed_file_count: int
    model_provider_mode: str
    limitations: List[str] = []


class ReviewResult(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)
    overall_risk: str
    findings: List[Finding] = []
    review_metadata: ReviewMetadata

    @field_validator("overall_risk")
    @classmethod
    def validate_overall_risk(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "unknown"}
        if v not in allowed:
            raise ValueError(f"overall_risk must be one of {allowed}")
        return v


class DiffSummary(BaseModel):
    changed_files: int
    added_lines: int
    removed_lines: int
    total_hunks: int
    files: List[str] = []