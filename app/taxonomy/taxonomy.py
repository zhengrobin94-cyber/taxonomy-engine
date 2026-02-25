from io import BytesIO
import logging
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, Optional

import pandas as pd
from anytree import RenderTree, PreOrderIter
from anytree.search import find_by_attr

from app.concept.models import Concept
from app.store.chromaDB import ChromaDB
from app.store.taxonomyDB import TaxonomyDB
from app.taxonomy.generator import generate_definition
from app.taxonomy.models import BestMatchingNode, InsertAttemptResult
from app.taxonomy.node import ConceptNode, ConceptRootNode, DOC_TEMPLATE
from app.utils import init_logging

init_logging()
logger = logging.getLogger(__name__)


REJECTION_THRESHOLD = 0.5
MERGE_THRESHOLD = 0.65


class Taxonomy:
    def __init__(self, id: UUID, root: ConceptRootNode, chroma_collection: Optional[str] = None):
        self.id = id
        self.root = root
        self.chroma = ChromaDB(collection_name=chroma_collection if chroma_collection else str(self.id))
        if self.chroma.size == 0:
            logger.debug("Initializing Chroma's collection")
            self.initialize_chroma_collection()
        elif self.chroma.size != len(self):
            logger.warning(
                "Chroma's collection not in sync with Taxonomy!\n"
                f"{self.chroma.size} embeddings in Chroma's collection vs {len(self)} nodes in the Taxonomy tree.\n"
                "Resetting and reinitializing Chroma's collection."
            )
            self.chroma.reset_collection()
            self.initialize_chroma_collection()

    def __len__(self) -> int:
        """Number of nodes in the taxonomy tree.

        Returns:
            int: Number of nodes in the taxonomy tree.
        """
        return len(self.nodes)

    def __str__(self) -> str:
        content = []
        for pre, _, node in RenderTree(self.root):
            content.append(f"{pre}{node.name}")
        return "\n".join(content)

    def __repr__(self) -> str:
        core = f"Taxonomy(id:'{self.id}', n_nodes:'{len(self)}', n_embeddings:'{self.chroma.size}', chroma_collection:'{self.chroma.collection_name}')"
        return core + "\n" + str(self)

    @property
    def nodes(self) -> list[ConceptNode | ConceptRootNode]:
        return list(PreOrderIter(self.root))

    @staticmethod
    def grow_tree(df: pd.DataFrame) -> ConceptRootNode:
        """Build the anytree hierarchy from dataframe."""
        # Create all nodes from dataframe without lineage yet
        nodes = {}
        for _, row in df.iterrows():
            node = ConceptNode.singleton_from_row(**row.to_dict())
            nodes[node.name] = node

        # Set parent relationships
        # Assumptions:
        #   1/ Concept's name is a unique identifier.
        #   2/ Each node can only have one parent.
        #   3/ There is only one root node.
        # Notes:
        #   1/ The `Parent name/Broader` column sometimes use the `Term`, sometimes the `Preferred name` ...
        root = None
        nodes_alt_names = [getattr(node, "Preferred name").strip() for node in nodes.values()]
        for name, node in nodes.items():
            parent_name = getattr(node, "Parent name/Broader").strip()
            if not parent_name:
                if root:
                    raise ValueError("More than one root node found.")
                root = nodes[name]
            elif not (parent_name in nodes or parent_name in nodes_alt_names):
                raise ValueError(f"Parent node not found for {node}, or multiple parents.")
            else:
                if parent_name in nodes:
                    parent = nodes[parent_name]
                else:
                    parent = list(nodes.values())[nodes_alt_names.index(parent_name)]
                nodes[name].parent = parent

        # Delete parent and child attributes from file
        for node in nodes.values():
            delattr(node, "Parent name/Broader")
            delattr(node, "Child name/Narrower")

        # Generate missing definition
        for name, node in nodes.items():
            if node.definition:
                continue
            logger.info(f"Generating definition for partial concept `{name}`")
            node.definition = generate_definition(node)
            curr_source_name = getattr(node, "Source name", "")
            new_source_name = curr_source_name + " " * bool(curr_source_name) + "(LLM-generated definition)"
            setattr(node, "Source name", new_source_name)

        return root

    def initialize_chroma_collection(self) -> None:
        """Index all terms + definitions into Chroma."""
        ids = [node.id for node in self.nodes]
        docs = [node.to_doc() for node in self.nodes]
        self.chroma.insert_many(ids, docs)

    def insert_into_chroma(self, node: ConceptNode) -> None:
        self.chroma.insert(node.id, node.to_doc())

    def display(self) -> None:
        print(str(self))

    def save(self) -> None:
        TaxonomyDB().insert(self)

    def insert(self, concept: Concept) -> InsertAttemptResult:
        # REJECT | Missing name or definition
        if not concept.name or not concept.definition:
            return InsertAttemptResult(taxonomy_id=self.id, result="Reject")

        doc = DOC_TEMPLATE.format(name=concept.name, definition=concept.definition)
        result = self.chroma.query(doc, top_k=1)
        best_node = self.get_node(id=result["ids"][0][0])
        assert best_node is not None, "Best node couldn't be found in Taxonomy. ChromaDB not in sync with Taxonomy"
        best_similarity_score = 1 - result["distances"][0][0]

        # REJECT | Below rejection threshold
        if best_similarity_score < REJECTION_THRESHOLD:
            return InsertAttemptResult(
                taxonomy_id=self.id,
                result="Reject",
                best_matching_node=BestMatchingNode(name=best_node.name, similarity_score=best_similarity_score),
            )

        # MERGE
        if best_similarity_score >= MERGE_THRESHOLD:
            best_node.merge(concept)
            self.save()
            return InsertAttemptResult(
                taxonomy_id=self.id,
                result="Merge",
                best_matching_node=BestMatchingNode(name=best_node.name, similarity_score=best_similarity_score),
            )

        # TODO: INSERT AS SIBLING

        # TODO: INSERT BETWEEN BEST MATCH AND BEST MATCH's PARENT

        # INSERT AS CHILD | Naive approach: Always insert as a child of best matching node
        new_node = best_node.insert_as_child(concept)
        self.save()
        self.insert_into_chroma(new_node)
        return InsertAttemptResult(
            taxonomy_id=self.id,
            result="Insert",
            best_matching_node=BestMatchingNode(name=best_node.name, similarity_score=best_similarity_score),
        )

    def get_node(self, id: UUID | str) -> ConceptNode | None:
        return find_by_attr(self.root, str(id), name="id")

    def serialize(self) -> dict[str, Any]:
        return {"id": str(self.id), "tree": self.root.serialize(), "chroma_collection": self.chroma.collection_name}

    def export(self) -> pd.DataFrame:
        nodes = [node.to_row() for node in self.nodes]
        return pd.DataFrame(nodes)

    @staticmethod
    def deserialize(id: str, tree: str, chroma_collection: Optional[str] = None) -> tuple[UUID, ConceptRootNode, str]:
        return UUID(id), ConceptRootNode.deserialize(tree), chroma_collection if chroma_collection else str(id)

    @classmethod
    def from_id(cls, id: UUID) -> Optional["Taxonomy"]:
        t_dict = TaxonomyDB().get_by_id(id)
        return cls(*cls.deserialize(**t_dict)) if t_dict is not None else None

    @classmethod
    def from_csv_xls(cls, io: Path | str | BytesIO) -> "Taxonomy":
        if isinstance(io, (str, Path)):
            io = Path(io)
            if io.suffix not in (".csv", ".xls", ".xlsx"):
                raise ValueError(f"Expected a CSV or Excel file, but got a `{io.suffix}` for file `{io.stem}`")
        df = pd.read_excel(io).fillna("")
        root = cls.grow_tree(df)
        instance = cls(uuid4(), root)
        instance.save()
        return instance
