"""Definitions of all request models used by API's routes."""

from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel


class TaxonomyUploadResponse(BaseModel):
    id: UUID
    n_concepts: int


class BestMatchingNode(BaseModel):
    name: str
    similarity_score: float


class InsertAttemptResult(BaseModel):
    taxonomy_id: UUID
    result: Literal["Reject", "Merge", "Insert"]  # TODO: Split "Insert" into its subvariants + Use Enum
    best_matching_node: Optional[BestMatchingNode] = None
    # TODO: Include Parent and Sibling details if Insert
