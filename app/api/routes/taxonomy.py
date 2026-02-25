import logging
import io
from uuid import UUID

from fastapi import APIRouter, Body, Path, status, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse

from app.concept.models import Concept
from app.store.conceptDB import ConceptDB
from app.taxonomy.models import InsertAttemptResult, TaxonomyUploadResponse
from app.taxonomy.taxonomy import Taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Updating Taxonomy"])


@router.post(
    "/taxonomies",
    summary="Initialize a taxonomy by uploading an Excel file.",
    description="Given an Excel file describing a taxonomy, initialize a taxonomy tree. Initialized taxonomy will be saved in a database.",
    response_description="Initialization result",
    status_code=status.HTTP_201_CREATED,
)
async def upload_taxonomy(
    file: UploadFile = File(..., description="Excel file containing the taxonomy for initialization."),
) -> TaxonomyUploadResponse:
    try:
        taxonomy = Taxonomy.from_csv_xls(file.file)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.error("An error occurred while initializing the taxonomy.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Check the logs."
        )
    return TaxonomyUploadResponse(id=taxonomy.id, n_concepts=len(taxonomy))


@router.post(
    "/taxonomies/{taxonomy_id}/concepts/{concept_id}",
    summary="Attempt to insert a new concept in the taxonomy.",
    description="Given the ID of a concept, attempt to insert it in a taxonomy, specified by its ID. Updated taxonomy will be saved in a database.",
    response_description="Insert attempt result",
    status_code=status.HTTP_201_CREATED,
)
async def insert_concept_to_taxonomy(
    taxonomy_id: UUID = Path(description="ID of the taxonomy in the UUID4 format."),
    concept_id: UUID = Path(description="ID of the concept in the UUID4 format."),
) -> InsertAttemptResult:
    concept = ConceptDB().get_by_id(concept_id)
    if concept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Concept with ID `{concept_id}` not found.")
    taxonomy = Taxonomy.from_id(taxonomy_id)
    if taxonomy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Taxonomy with ID `{taxonomy_id}` not found."
        )
    return taxonomy.insert(concept)


@router.post(
    "/taxonomies/{taxonomy_id}/concepts/",
    summary="Attempt to insert a new user-created concept in the taxonomy.",
    description="Given a concept created by the user, attempt to insert it in a taxonomy, specified by its ID. Updated taxonomy will be saved in a database.",
    response_description="Insert attempt result",
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"requestBody": {"description": "User-generated concept."}},
)
async def insert_user_concept_to_taxonomy(
    taxonomy_id: UUID = Path(description="ID of the taxonomy in the UUID4 format."),
    concept: Concept = Body(),
) -> InsertAttemptResult:
    taxonomy = Taxonomy.from_id(taxonomy_id)
    if taxonomy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Taxonomy with ID `{taxonomy_id}` not found."
        )
    return taxonomy.insert(concept)


@router.get(
    "/taxonomies/{taxonomy_id}/display",
    summary="Display the taxonomy tree.",
    description="Given the ID of a taxonomy, show its tree structure.",
    response_description="Taxonomy tree representation",
    response_class=PlainTextResponse,
)
async def display_taxonomy_tree(taxonomy_id: UUID = Path(description="ID of the taxonomy in the UUID4 format.")) -> str:
    taxonomy = Taxonomy.from_id(taxonomy_id)
    if taxonomy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Taxonomy with ID `{taxonomy_id}` not found."
        )
    return repr(taxonomy)


@router.get(
    "/taxonomies/{taxonomy_id}",
    summary="Export a taxonomy to an Excel file.",
    description="Given the ID of a taxonomy, export it as an Excel file.",
    response_description="Excel file",
)
async def export_taxonomy_as_xlsx(taxonomy_id: UUID = Path(description="ID of the taxonomy in the UUID4 format.")):
    taxonomy = Taxonomy.from_id(taxonomy_id)
    if taxonomy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Taxonomy with ID `{taxonomy_id}` not found."
        )
    taxonomy_df = taxonomy.export()
    file_buffer = io.BytesIO()
    taxonomy_df.to_excel(file_buffer, index=False)
    file_buffer.seek(0)
    file_name = f"{taxonomy.chroma.collection_name}.xlsx"

    return StreamingResponse(
        file_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
