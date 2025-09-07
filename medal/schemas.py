from typing import Literal, Optional
from pydantic import BaseModel, Field


Answer = Literal["Yes", "No", "No Evidence"]
EvidenceQuality = Literal["High", "Moderate", "Low", "Very Low", "Missing"]
Discrepancy = Literal["Yes", "No", "Missing"]


class QAPair(BaseModel):
    doi: str
    question: str
    answer: Answer
    evidence_quality: EvidenceQuality = Field(alias="evidence-quality")
    discrepancy: Discrepancy
    notes: Optional[str] = ""
    publication_year: Optional[int] = None
    abstract: Optional[str] = None

    class Config:
        populate_by_name = True


class EvalRecord(BaseModel):
    id: str
    doi: Optional[str] = None
    question: str
    model_answer: str
    model_evidence_quality: str = Field(alias="model_evidence-quality")
    model_discrepancy: str
    model_notes: Optional[str] = ""
    ground_truth_answer: Optional[str] = None
    ground_truth_evidence_quality: Optional[str] = Field(default=None, alias="ground_truth_evidence-quality")
    ground_truth_discrepancy: Optional[str] = None

    class Config:
        populate_by_name = True




