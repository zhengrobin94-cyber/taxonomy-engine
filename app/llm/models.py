from typing import Any
from pydantic import BaseModel, Field

from app.settings import settings
from app.llm.prompts.concept_extraction import system_prompt


class ConceptLLMResponse(BaseModel):
    term: str
    definition: str


class ExtractConceptLLMRequest(BaseModel):
    """Request model for extracting concepts from text chunks using an LLM."""

    system_prompt: str = Field(
        system_prompt,
        description="System prompt to guide the LLM's extraction of concepts from text chunks.",
    )
    model_name: str = Field(settings.concept_extraction_model_name, description="LLM model to use for generation")
    temperature: float = Field(
        default=settings.concept_extraction_temperature,
        description="Temperature of the model. The higher the temperature the more 'creative' the model is",
    )

    def asdict(self) -> dict[str, Any]:
        return self.model_dump()
