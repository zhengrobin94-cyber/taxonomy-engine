"""
Main script that :
 - creates an initial taxonomy of the logistics domain
 - passes sample chunks to an LLM for concept extraction (example). Replace with actual document chunks.
 - adds a new term to the taxonomy (example). Replace with actual terms extracted from LLM response.
"""

"""
To run: 
    1. In a new terminal, start Ollama container (if not already running) using "docker restart ollama". 
    Then run the LLM (mistral-small3.2:latest) running "docker exec -it ollama /bin/bash" > then "ollama run mistral-small3.2:latest". 
    Once the model is loaded, keep it running.
    2. In a second terminal, build and start the app server with "make build" > "make up".
    3. In a third terminal, run this script with "docker compose exec app python -m app.main".

    You should see the real-time INFO log messages and LLM responses in the terminal you ran the main.py script.

    You can then tweak this file to take in real document chunks from the standards document and engineer the prompts accordingly.
"""
import asyncio
import logging
import httpx
import json
import os

from app.settings import settings
from app.taxonomy.models import AddConceptRequest, ExportTaxonomyRequest
from app.api.models.concept import ExtractConceptRequest


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load chunks from JSON file (chunking/doc_chunks_example.json) #TODO: Maybe store in redis vs .json file
json_path = "app/chunking/doc_chunks_example.json"

with open(json_path, "r", encoding="utf-8") as f:
    doc_data = json.load(f)

# Extract all "content" fields into a list
doc_chunks = [chunk["content"] for chunk in doc_data.get("chunks", [])]

logger.info(f"Loaded {len(doc_chunks)} chunks from {json_path}")


async def main():

    ###### STEP 1: Upload excel file and create initial taxonomy using /taxonomy-upload endpoint ######

    taxonomy_path = "app/taxonomy/sample_taxonomy.xlsx"  # Adjust the path as needed
    api_url = f"{settings.api_url}/taxonomy-upload"
    params = {"collection_name": "logistics_taxonomy", "reset": "true"}
    fname = os.path.basename(taxonomy_path)

    # Set file type for .xlsx files
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Send excel file to /taxonomy-upload endpoint for embedding and indexing
    async with httpx.AsyncClient(timeout=settings.httpx_timeout * 5) as client:
        with open(taxonomy_path, "rb") as fh:
            files = {"file": (fname, fh, content_type)}
            resp = await client.post(api_url, params=params, files=files)
            resp.raise_for_status()
            logger.info(resp.json())
            if resp.json().get("status") == "accepted":
                logger.info("Initial taxonomy terms embedded and indexed successfully.")

    ###### STEP 2: Make async POST request to LLM for concept extraction and stream responses ######
    # Call /generate endpoint to extract concepts from document chunks
    request = ExtractConceptRequest(  # Sample GenerateRequest payload
        prompt="""
                    You are an expert in technical terminology extraction.
                    Your task is to identify all term-definition pairs explicitly defined in this text chunk.

                    Follow these rules:
                    - Only include terms that have a clear definition or explanatory statement in the text.
                    - Ignore acronyms or references without definitions.
                    - Preserve exact wording from the source text (do not paraphrase).
                    - Return a JSON list where each item has two fields: "term" and "definition".
                    - If no valid term-definition pairs are found, return an empty JSON list: "".

                    Output format example:
                    [
                    {"term": "logistics", "definition": "The science of planning and carrying out the movement and maintenance of forces."},
                    {"term": "strategic airlift", "definition": "The long-range transportation of personnel and equipment by aircraft."}
                    ]
                """,
        model_name=settings.model_name,
        short_llm_responses=settings.short_llm_responses,
        chunks=doc_chunks,  # List of document chunks loaded from JSON file
    )

    api_url = f"{settings.api_url}/generate"
    logger.info(f"Sending request to {api_url}")

    final_result = None
    try:
        async with httpx.AsyncClient(timeout=settings.httpx_timeout * 20) as client:
            async with client.stream("POST", api_url, json=request.model_dump()) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        json_part = line[len("data: ") :]  # remove data prefix
                        try:
                            data = json.loads(json_part)
                            if data.get("type") == "complete":
                                final_result = data["data"]  # final result of all concepts extracted from each chunk
                                logger.info(f"Final result received: {json.dumps(final_result, indent=2)}")
                            else:
                                logger.info(f"Progress update: {json.dumps(data, indent=2)}")
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON: {json_part}")

    except httpx.HTTPError as e:
        logger.error(f"HTTP request failed: {e}")

    if final_result:
        # Flatten all extracted terms from all chunks into a single dict
        extracted_concepts = {}
        for chunk, content in final_result.items():
            response_str = content.get("response", "[]")
            try:
                items = json.loads(response_str)
                for item in items:
                    term = item.get("term")
                    definition = item.get("definition")
                    if term:
                        extracted_concepts[term] = definition
            except json.JSONDecodeError:
                logger.warning(f"No terms extracted from {chunk}.")

        logger.info(f"Flattened all extracted terms: {json.dumps(extracted_concepts, indent=2)}")

    ###### STEP 3: Add new term(s) to existing taxonomy using /taxonomy-add-term endpoint ######
    api_url = f"{settings.api_url}/taxonomy-add-term"
    request = AddConceptRequest(  # Sample AddTermRequest payload
        collection_name="logistics_taxonomy",
        file_name="sample_taxonomy.xlsx",
        concept="strategic airlift",
        definition="The long-range transportation of personnel, equipment, and supplies by aircraft to support operations across theaters.",
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(api_url, json=request.model_dump())
        resp.raise_for_status()
        logger.info(resp.json())
        if resp.json().get("status") == "success":
            logger.info(f"Term '{request.term}' added to taxonomy successfully.")

    ###### STEP 4: Export taxonomy to excel file using /taxonomy-export endpoint ######
    api_url = f"{settings.api_url}/taxonomy-export"
    request = ExportTaxonomyRequest(  # Sample ExportRequest payload
        collection_name="logistics_taxonomy",
        file_name="sample_taxonomy.xlsx",
        version=1,  # Optional; omit or set to None to get latest version
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, json=request.model_dump())
        response.raise_for_status()
        if response.status_code == 200:
            with open(f"updated_{request.collection_name}.xlsx", "wb") as f:
                f.write(response.content)
            logger.info(f"Successfully exported taxonomy to updated_{request.collection_name}.xlsx")
        else:
            logger.error(f"Failed to export taxonomy: {response.status_code} {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
