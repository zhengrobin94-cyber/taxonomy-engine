"""
Chunking API Routes
Provides REST endpoints for PDF chunking operations
"""

import logging
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, status, Query, Path
from fastapi.responses import JSONResponse

from app.chunk.models import SemanticChunk
from app.chunk.chunker import StandardPDFChunker
from app.chunk.typings import PartitionStrategy
from app.store.chunkDB import ChunkDB
from app.utils import init_logging


init_logging()
logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chunking"])


@router.post(
    "/chunks",
    summary="Split PDF Standards document(s) into semantic chunks and save them in a database.",
    description="Given a set of document(s), i.e. Standards, generate chunks. Generated chunk(s) will be saved in a database.",
    response_description="Result",
    status_code=status.HTTP_201_CREATED,
)
async def extract_chunks_from_pdf(
    files: list[UploadFile] = File(..., description="Standard file(s), in PDF format, to chunk."),
    strategy: PartitionStrategy = Form("fast", description="Strategy to use to parse the document."),
    languages: list[str] = Form(["eng"], description="Language(s) in which the `files` are written."),
    soft_max_characters_in_chunk: int = Form(
        750,
        description="The soft-maximum number of characters in a chunk. Some chunks might be longer to prevent breaking a semantic concept.",
        ge=100,
        le=2000,
    ),
    ignore_page_boundaries: bool = Form(True, description="Whether to allow multi-pages chunks."),
    search_first_chapter_page_limit: int = Form(
        25,
        description="Upper boundary, in terms of pages, for the search of the page containing the first chapter.",
        ge=1,
        le=35,
    ),
):
    if any(file.content_type != "application/pdf" for file in files):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document type. Only PDF files are allowed."
        )
    data = []
    try:
        for file in files:
            logger.info(f"Processing uploaded file: {file.filename}")

            chunker = StandardPDFChunker(file.file, file.filename)
            chunks = chunker(
                strategy=strategy,
                languages=languages,
                search_first_chapter_page_limit=search_first_chapter_page_limit,
                soft_max_characters=soft_max_characters_in_chunk,
                ignore_page_boundaries=ignore_page_boundaries,
            )
            logger.debug(f"Successfully chunked {file.filename}: {len(chunks)} chunks.")

            data.append({"filename": file.filename, "nbr_chunks": len(chunks)})

            ChunkDB().insert_many(chunks)
            logger.debug("Successfully inserted chunks in DB.")

        return JSONResponse(
            {
                "success": True,
                "data": data,
                "nbr_files": len(files),
                "nbr_chunks": sum(x["nbr_chunks"] for x in data),
            }
        )

    except Exception as e:
        logger.error(f"Error processing {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.get(
    "/chunks/{chunk_id}",
    summary="Get data for a specific chunk.",
    description="Given the ID of a chunk, fetch its data from the database.",
    response_description="Requested chunk",
)
async def get_chunk(chunk_id: UUID = Path(description="ID of the chunk in the UUID4 format.")) -> SemanticChunk:
    chunk = ChunkDB().get_by_id(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chunk with ID `{chunk_id}` not found.")
    return chunk


@router.get(
    "/chunks/documents/{filename}",
    summary="Get chunks related to a specific document.",
    description="Given the name of a document, i.e. Standard, fetch all its associated chunks from the database.",
    response_description="Associated chunk(s)",
)
async def get_document_chunks(
    filename: str = Path(description="Name (with extension) of the document, i.e. Standard."),
    limit: int = Query(
        -1,
        description="Maximum number of chunks to return. Defaults to -1 which implies that all chunks associated with the document will be returned.",
        ge=-1,
    ),
    offset: int = Query(0, description="Number of chunks to skip for pagination.", ge=0),
) -> list[SemanticChunk]:
    return ChunkDB().get_by_document(filename, limit, offset)


@router.delete(
    "/chunks/all",
    summary="Delete all chunks.",
    description="Delete all chunks stored in the database.",
    response_description="Result",
)
async def delete_chunks() -> str:
    ChunkDB().truncate()
    return "Chunks successfully deleted"


@router.delete(
    "/chunks/{chunk_id}",
    summary="Delete a specific chunk.",
    description="Given the ID of a chunk, remove it from the database.",
    response_description="Result",
)
async def delete_chunk(chunk_id: UUID = Path(description="ID of the chunk in the UUID4 format.")) -> str:
    ChunkDB().delete(chunk_id)
    return f"Chunk {chunk_id} successfully deleted"


@router.delete(
    "/chunks/documents/{filename}",
    summary="Delete chunks related to a specific document.",
    description="Given the name of a document, i.e. Standard, delete all its associated chunks from the database.",
    response_description="Result",
)
async def delete_document_chunks(
    filename: str = Path(description="Name (with extension) of the document, i.e. Standard."),
) -> str:
    ChunkDB().delete_by_document(filename)
    return f"Chunks related to document `{filename}` successfully deleted"


@router.delete(
    "/chunks/{older_than_x_days}",
    summary="Delete all chunks created more than x days ago.",
    description="Given a number _x_, delete all chunks from the database that are older than _x_ days.",
    response_description="Result",
)
async def delete_old_chunks(
    older_than_x_days: int = Path(
        description="Threshold above which to consider a chunk old, based on the number of days since its creation."
    ),
) -> str:
    ChunkDB().delete_old_records(older_than_x_days)
    return "Old chunks successfully deleted"
