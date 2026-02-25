from app.chunk.models import SemanticChunk
from app.concept.models import Concept
from app.llm.client import StructuredOllamaClient
from app.llm.models import ConceptLLMResponse
from app.llm.prompts.concept_extraction import system_prompt, user_prompt
from app.settings import settings


def extract_concepts(
    chunk: SemanticChunk,
    system_prompt: str = system_prompt,
    model_name: str = settings.concept_extraction_model_name,
    temperature: float = settings.concept_extraction_temperature,
) -> list[Concept]:
    """Extract `Concept`(s) (i.e. name-definition pair) from a `SemanticChunk` using an LLM.

    Args:
        chunk (SemanticChunk): Chunk from which to extract concept(s).
        system_prompt (str, optional): System prompt for the LLM. Defaults to predefined prompt.
        model_name (str, optional): Name of the LLM to use for the extraction. Defaults to
            settings.concept_extraction_model_name.
        temperature (float, optional): Temperature to set the model to. Higher temperature leads to more creativity
            and, potentially, more hallucinations. Defaults to settings.concept_extraction_temperature.

    Returns:
        list[Concept]: Extracted concept(s).
    """
    llm = StructuredOllamaClient()
    response = llm.generate(
        system_prompt=system_prompt,
        prompt=user_prompt.format(**chunk.serialize()),
        response_model=list[ConceptLLMResponse],
        model=model_name,
        temperature=temperature,
    )
    return [Concept.from_llm_response(llm_response=raw_concept, chunk=chunk) for raw_concept in response]
