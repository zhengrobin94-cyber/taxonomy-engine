from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Query, status, HTTPException, Path
from fastapi.responses import JSONResponse

from app.llm.models import ExtractConceptLLMRequest
from app.api.routes.chunk import get_chunk, get_document_chunks
from app.concept.extractor import extract_concepts
from app.concept.models import Concept
from app.store.conceptDB import ConceptDB


router = APIRouter(tags=["Extracting Concept"])


@router.post(
    "/concepts/chunks/{chunk_id}",
    summary="Extract concepts from a chunk.",
    description="Given the ID of a chunk, extract all concepts from it, if any. Extracted concept(s) won't be saved in any database.",
    response_description="Extracted concept(s)",
)
async def extract_concept_from_chunk(
    chunk_id: UUID, request: Annotated[ExtractConceptLLMRequest, Form()]
) -> list[Concept]:
    chunk = await get_chunk(chunk_id)
    return extract_concepts(chunk, **request.asdict())


@router.post(
    "/concepts/documents/{filename}",
    summary="Extract concepts from a document's chunks and save them in a database.",
    description="Given the name of a document, i.e. Standard, extract all concepts from each document's chunks, if any. Extracted concept(s) will be saved in a database.",
    response_description="Result",
    status_code=status.HTTP_201_CREATED,
)
async def extract_concept_from_document_chunks(filename: str, request: Annotated[ExtractConceptLLMRequest, Form()]):
    last_chunks = False
    limit = 10
    offset = 0
    nbr_concepts = 0
    while not last_chunks:
        concepts = []
        chunks = await get_document_chunks(filename, limit, offset)
        n_chunks = len(chunks)
        last_chunks = n_chunks < limit
        offset += n_chunks
        for chunk in chunks:
            concepts.extend(extract_concepts(chunk, **request.asdict()))
        if concepts:
            ConceptDB().insert_many(concepts)
            nbr_concepts += len(concepts)

    return JSONResponse(
        {
            "success": True,
            "filename": filename,
            "nbr_concepts": nbr_concepts,
        }
    )


@router.get(
    "/concepts/{concept_id}",
    summary="Get data for a specific concept.",
    description="Given the ID of a concept, fetch its data from the database.",
    response_description="Requested concept",
)
async def get_concept(concept_id: UUID = Path(description="ID of the concept in the UUID4 format.")) -> Concept:
    concept = ConceptDB().get_by_id(concept_id)
    if concept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Concept with ID `{concept_id}` not found.")
    return concept


@router.delete(
    "/concepts/all",
    summary="Delete all concepts.",
    description="Delete all concepts stored in the database.",
    response_description="Result",
)
async def delete_concepts() -> str:
    ConceptDB().truncate()
    return "Concepts successfully deleted"


@router.delete(
    "/concepts/{concept_id}",
    summary="Delete a specific concept.",
    description="Given the ID of a concept, remove it from the database.",
    response_description="Result",
)
async def delete_concept(concept_id: UUID = Path(description="ID of the concept in the UUID4 format.")) -> str:
    ConceptDB().delete(concept_id)
    return f"Concept {concept_id} successfully deleted"


@router.get(
    "/concepts/documents/{filename}",
    summary="Get concepts related to a specific document.",
    description="Given the name of a document, i.e. Standard, fetch all its associated concepts from the database.",
    response_description="Associated concept(s)",
)
async def get_document_concepts(
    filename: str = Path(description="Name (with extension) of the document, i.e. Standard."),
    limit: int = Query(
        -1,
        description="Maximum number of concepts to return. Defaults to -1 which implies that all concepts associated with the document will be returned.",
        ge=-1,
    ),
    offset: int = Query(0, description="Number of concepts to skip for pagination.", ge=0),
) -> list[Concept]:
    return ConceptDB().get_by_document(filename, limit, offset)


@router.delete(
    "/concepts/documents/{filename}",
    summary="Delete concepts related to a specific document.",
    description="Given the name of a document, i.e. Standard, delete all its associated concepts from the database.",
    response_description="Result",
)
async def delete_document_concepts(
    filename: str = Path(description="Name (with extension) of the document, i.e. Standard."),
) -> str:
    ConceptDB().delete_by_document(filename)
    return f"Concepts related to document `{filename}` successfully deleted"


@router.delete(
    "/concepts/{older_than_x_days}",
    summary="Delete all concepts created more than x days ago.",
    description="Given a number _x_, delete all concepts from the database that are older than _x_ days.",
    response_description="Result",
)
async def delete_old_concepts(
    older_than_x_days: int = Path(
        description="Threshold above which to consider a concept old, based on the number of days since its creation."
    ),
) -> str:
    ConceptDB().delete_old_records(older_than_x_days)
    return "Old concepts successfully deleted"
