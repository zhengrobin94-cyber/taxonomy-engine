from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.chunk.models import SemanticChunk
from app.llm.models import ConceptLLMResponse
from app.utils import convert_str_fields_to_uuid


@dataclass
class Concept:
    name: str
    definition: str
    chunk_id: UUID
    page_number: int
    filename: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        convert_str_fields_to_uuid(self)

    @classmethod
    def from_llm_response(cls, llm_response: ConceptLLMResponse, chunk: SemanticChunk) -> "Concept":
        """Instantiate a `Concept` object from an LLM response and its associated `SemanticChunk`.

        Args:
            llm_response (ConceptLLMResponse): The response returned by the LLM.
            chunk (SemanticChunk): Chunk from which the concept has been extracted.

        Returns:
            Concept: Instance of `Concept`.
        """
        return cls(
            name=llm_response.term,
            definition=llm_response.definition,
            chunk_id=chunk.id,
            page_number=chunk.page_number,
            filename=chunk.filename,
        )

    def serialize(self) -> dict[str, Any]:
        return asdict(self, dict_factory=self._serializer)

    @staticmethod
    def _serializer(data):
        return {f: str(value) if isinstance(value, UUID) else value for f, value in data}
