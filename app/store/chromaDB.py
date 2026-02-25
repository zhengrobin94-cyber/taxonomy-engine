from typing import Any, Optional
from uuid import UUID
import chromadb
from chromadb.api.types import Embedding, QueryResult
import requests
import logging

from app.settings import settings

logger = logging.getLogger(__name__)


class ChromaDB:
    def __init__(
        self,
        collection_name: str,
        database: str = settings.chroma_database,
        ollama_url: str = settings.ollama_url,
        model: str = settings.chroma_embedding_model_name,
    ):
        """Lightweight wrapper for a ChromaDB handler.

        Args:
            collection_name (str): Name to give to the ChromaDB's Collection.
            database (str, optional): Name/location of the database. Defaults to settings.chroma_database.
            ollama_url (str, optional): Ollama URL for the Embedding API. Defaults to settings.ollama_url.
            model (str, optional): Embedding model's name. Defaults to settings.chroma_embedding_model_name.
        """
        self.client = chromadb.PersistentClient(
            database, settings=chromadb.Settings(anonymized_telemetry=settings.chroma_anonymized_telemetry)
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(name=collection_name)

        # Ollama embed endpoint
        self.ollama_url = f"{ollama_url}/api/embed"
        self.model = model

    @property
    def size(self) -> int:
        """Size of the ChromaDB's Collection, i.e. number of embeddings.

        Returns:
            int: Number of embeddings in the Collection.
        """
        return self.collection.count()

    def reset_collection(self) -> None:
        """Drop and recreate the Collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            print(f"Clearing Chroma collection '{self.collection_name}'.")
        except Exception as e:
            print(f"Could not delete collection '{self.collection_name}': {e}")
            raise e

        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        print(f"Reinitialized collection '{self.collection_name}'.")

    def embed(self, documents: str | list[str]) -> list[Embedding]:
        """Generate embedding for each document.

        Args:
            documents (str | list[str]): Document(s)/Text snippet(s) to embed.

        Returns:
            list[Embedding]: An embedding for each document in `documents`.
        """
        documents = [documents] if isinstance(documents, str) else documents
        return [self._embed(doc, self.ollama_url, self.model) for doc in documents]

    @staticmethod
    def _embed(text: str, url: str, model: str) -> Embedding:
        """Generate embedding for the snippet of text.

        Args:
            text (str): Text snippet to embed.
            url (str): Ollama URL for the API entrypoint.
            model (str): Embedding model's name.

        Returns:
            Embedding: Generated embedding.
        """
        response = requests.post(url, json={"model": model, "input": text})
        response.raise_for_status()
        return response.json()["embeddings"][0]

    def insert(self, id: str | UUID, document: str, metadata: Optional[dict[str, Any]] = None):
        """Insert a document to Chroma, generating the embedding on-the-fly.

        Args:
            id (str | UUID): ID to associate to the document.
            document (str): Document/Text snippet to store in the database.
            metadata (Optional[dict[str, Any]], optional): Metadata to associate to the document. Defaults to None.
        """
        self.insert_many([str(id)], [document], [metadata] if metadata else None)

    def insert_many(
        self, ids: list[str | UUID], documents: list[str], metadatas: Optional[list[dict[str, Any]]] = None
    ):
        """Insert multiple documents to Chroma, generating embeddings on-the-fly.

        Args:
            ids (list[str  |  UUID]): IDs to associate to documents. Should be the same length as `documents`.
            documents (list[str]): Document(s)/Text snippet(s) to store in the database.
            metadatas (Optional[list[dict[str, Any]]], optional): Metadata to associate to documents. Should be the
                same length as `documents`. Defaults to None.
        """
        self.collection.add(
            ids=list(map(str, ids)),
            documents=documents,
            embeddings=self.embed(documents),
            metadatas=metadatas,
        )

        print(f"Added {len(documents)} documents to Chroma collection '{self.collection.name}'.\n")

    def query(self, document: str, top_k: int = 1, where: dict = None) -> QueryResult:
        """Fetch most similar documents, with optional metadata filtering.

        Args:
            document (str): Document to use query against.
            top_k (int, optional): Number of most similar documents to return. Defaults to 1.
            where (dict, optional): Metadata filters. See
                https://docs.trychroma.com/docs/querying-collections/metadata-filtering for more information. Defaults
                to None.

        Returns:
            QueryResult: Results object containing lists of ids, embeddings, documents, and metadatas of the records
                that matched your query.
        """
        return self.collection.query(query_embeddings=self.embed(document), n_results=top_k, where=where)
