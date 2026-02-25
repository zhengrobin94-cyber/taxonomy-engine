# Taxonomy Engine

An AI-powered system that automatically extracts concepts from PDF standards documents and intelligently integrates them into existing taxonomy trees. Built as a containerized FastAPI application with LLM-powered extraction, vector similarity matching, and ontological placement logic.

## The Problem

Organizations that maintain large taxonomies of standardized terminology face a scaling challenge: as new documents are published, subject matter experts must manually read each one, identify defined terms, and decide where each term fits within an existing hierarchical taxonomy. This process is slow, inconsistent across reviewers, and can't keep pace with publication volume.

## The Solution

This system automates the full pipeline — from raw PDF to taxonomy update — through four stages:

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  PDF Input   │────▶│ Semantic Chunking│────▶│ Concept Extraction│────▶│ Taxonomy Insertion   │
│              │     │                 │     │   (LLM-powered)  │     │ (Vector Similarity)  │
└─────────────┘     └─────────────────┘     └──────────────────┘     └─────────────────────┘
```

### Stage 1: Semantic Chunking

The PDF chunker (`app/chunk/chunker.py`) partitions documents into context-preserving text segments using intelligent boundary detection. It recognizes list structures, chapter breaks, and section types, then propagates page-level tags (e.g., "Lexicon", "Definitions") so downstream extraction can weight those chunks more heavily. The chunker skips introductory pages by locating the first chapter automatically and handles inconsistent formatting across publications.

### Stage 2: LLM-Powered Concept Extraction

Each chunk is processed by a local LLM (via Ollama) with structured outputs enforced through the [Instructor](https://github.com/567-labs/instructor) library and Pydantic response models. The LLM client (`app/llm/client.py`) includes a smart retry system that adapts its strategy based on failure type:
- **Token limit exceeded** → injects "be more concise" instruction
- **Schema validation failure** → feeds the validation error back to the model
- **Timeout** → progressively increases the timeout by 50%

This turns what would otherwise be brittle LLM calls into a reliable production component.

### Stage 3: Vector Similarity Matching

Extracted concepts are embedded and compared against the existing taxonomy using ChromaDB (`app/store/chromaDB.py`). Similarity scores (1 − L2 distance) determine how closely a new concept relates to existing taxonomy nodes.

### Stage 4: Taxonomy Insertion Algorithm

The core intellectual contribution of the project. When a new concept is extracted, the system decides what to do with it through a series of threshold-based comparisons (`app/taxonomy/taxonomy.py`):

| Similarity to Best Matching Node (BMN) | Action |
|---|---|
| Below 0.45 | **Reject** — concept is too distant from the taxonomy |
| Above 0.73 | **Merge** — concept corroborates an existing node |
| 0.45 – 0.73 | **Insert** — compare similarity to BMN's parent vs. siblings to determine placement |

For insertions in the middle range, the algorithm compares the concept's similarity to the best node's **parent** versus its **siblings** to decide whether to insert as:
- **Parent** of the BMN (similarity to parent ≥ 0.50 and > sibling similarity)
- **Sibling** of the BMN (similarity to siblings ≥ 0.50 and > parent similarity)
- **Child** of the BMN (fallback)

This encodes real ontological reasoning about how concept hierarchies evolve — not just nearest-neighbor matching.

## Evaluation Framework

The project includes a formal evaluation pipeline (`scripts/evaluate_concepts_extraction.py`) that computes precision, recall, and F1 scores by comparing extracted concepts against SME-annotated ground truth. Matching uses a weighted scoring formula:

```
combined_score = 0.60 × definition_similarity + 0.25 × name_similarity + 0.15 × same_page
```

This allows systematic measurement and improvement of extraction accuracy rather than relying on qualitative review.

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI with background task processing |
| LLM Integration | Ollama (Mistral) + Instructor for structured outputs |
| Vector Database | ChromaDB with nomic-embed-text embeddings |
| Relational Storage | SQLite with abstract generic database layer |
| PDF Processing | Unstructured |
| Data Modeling | Pydantic, anytree |
| Infrastructure | Docker Compose, Makefile |
| Documentation | Sphinx |

## Project Structure

```
├── app/
│   ├── api/              # FastAPI routes (chunking, extraction, taxonomy, e2e pipeline)
│   ├── chunk/            # Semantic PDF chunker with page-tag propagation
│   ├── concept/          # Concept data models
│   ├── job/              # Background job tracking
│   ├── llm/              # Ollama client with smart retry + prompt templates
│   ├── store/            # Abstract DB layer (SQLite + ChromaDB)
│   ├── taxonomy/         # Tree structure, insertion algorithm, node operations
│   ├── main.py           # E2E pipeline orchestration
│   └── settings.py       # Pydantic-based configuration management
├── scripts/
│   └── evaluate_concepts_extraction.py   # Precision/recall/F1 evaluation
├── docs/                 # Sphinx documentation source
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── requirements.txt
```

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/) and Docker Compose
- [Ollama](https://ollama.com/download) with a compatible model pulled (recommended: `mistral-small3.2`)

### Quick Start

```bash
# Pull the LLM model
ollama pull mistral-small3.2

# Start the application
make up
```

The API will be available at `http://localhost:5100`. Upload a taxonomy file (CSV/Excel) and one or more PDF standards to the `/e2e` endpoint to run the full pipeline.

### Local Development

```bash
conda create -n taxonomy-engine python=3.12
conda activate taxonomy-engine
pip install -r requirements.txt
```

See [DEV.md](DEV.md) for detailed development setup and containerized execution instructions.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/e2e` | Run the full pipeline (PDF standards + taxonomy → updated taxonomy) |
| `GET` | `/e2e/jobs/{job_id}` | Check pipeline job status |
| `GET` | `/e2e/jobs/{job_id}/output` | Download updated taxonomy as Excel |
| `POST` | `/chunks` | Extract chunks from a PDF |
| `POST` | `/concepts` | Extract concepts from chunks |
| `POST` | `/taxonomy` | Initialize a taxonomy from CSV/Excel |
| `POST` | `/taxonomy/{id}/insert` | Insert a concept into an existing taxonomy |

## Acknowledgments

This project was co-developed in close collaboration with a colleague. The architecture, algorithms, and implementation reflect genuine shared ownership — every major design decision, from the chunking strategy to the insertion thresholds, was debated, prototyped, and refined together.
