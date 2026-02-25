from __future__ import annotations

from typing import Any, TYPE_CHECKING
from app.llm.client import StructuredOllamaClient
from app.llm.models import ConceptLLMResponse
from app.llm.prompts.definition_generation import system_prompt, user_prompt
from app.settings import settings
from app.utils import dict2str

if TYPE_CHECKING:
    from app.taxonomy.taxonomy import ConceptNode


def generate_definition(
    concept: ConceptNode,
    system_prompt: str = system_prompt,
    model_name: str = settings.definition_generation_model_name,
    temperature: float = settings.definition_generation_temperature,
) -> str:
    """Generate a definition for a concept given its context (i.e. surrounding nodes in the taxonomy tree).

    Args:
        concept (ConceptNode): Node from the taxonomy tree for which to generate a definition.
        system_prompt (str, optional): System prompt for the LLM. Defaults to predefined prompt.
        model_name (str, optional): Name of the LLM to use for the extraction. Defaults to
            settings.definition_generation_model_name.
        temperature (float, optional): Temperature to set the model to. Higher temperature leads to more creativity
            and, potentially, more hallucinations. Defaults to settings.definition_generation_temperature.

    Returns:
        str: Generated definition.
    """
    llm = StructuredOllamaClient()

    response = llm.generate(
        system_prompt=system_prompt,
        prompt=user_prompt.format(term=concept.name, context=dict2str(build_node_context(concept))),
        response_model=ConceptLLMResponse,
        model=model_name,
        temperature=temperature,
    )
    return response.definition


def build_node_context(concept: ConceptNode) -> dict[str, Any]:
    return {
        "parent": concept.parent.to_name_definition_pair() if concept.parent else None,
        "siblings": (
            [s.to_name_definition_pair() for s in concept.parent.children if s.id != concept.id]
            if concept.parent and concept.parent.children
            else []
        ),
        "children": [c.to_name_definition_pair() for c in concept.children] if concept.children else [],
    }
