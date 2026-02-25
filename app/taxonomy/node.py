from uuid import uuid4
from typing import Any, Optional

from anytree import Node
from anytree.exporter import JsonExporter
from anytree.importer import JsonImporter, DictImporter

from app.concept.models import Concept


DOC_TEMPLATE = "{name}: {definition}"
STANDARD_TEMPLATE = "{filename} (p. {page_number})"


class ConceptNode(Node):
    def __init__(
        self, name: str, definition: str, parent: Optional[Node] = None, children: Optional[list[Node]] = None, **kwargs
    ):
        extra_cols = {
            "Status": "",
            "Associated Standards": [],
            "Alternative Names": [],
            "Alternative Definitions": [],
        }
        kwargs = extra_cols | kwargs
        super().__init__(name, parent, children, definition=definition, **kwargs)

    @classmethod
    def singleton_from_row(cls, **kwargs) -> "ConceptNode":
        # Create detached node (i.e. no children, no parent)
        name = kwargs.pop("Term").strip()
        definition = kwargs.pop("Definition")
        # TODO: Generate definition with LLM if missing + Update Source name.
        id = kwargs.pop("ID") or str(uuid4())
        return cls(name, definition, id=id, Status="Original", **kwargs)

    @classmethod
    def from_concept(cls, concept: Concept) -> "ConceptNode":
        kwargs = {
            "Status": "Introduced",
            "Associated Standards": [STANDARD_TEMPLATE.format(**concept.serialize())],
            "Source name": concept.filename,
        }
        return cls(concept.name, concept.definition, id=str(concept.id), **kwargs)

    def to_row(self) -> dict[str, Any]:
        attrs = {
            "ID": self.id,
            "Term": self.name,
            "Definition": self.definition,
            "Parent name/Broader": self.parent.name if self.parent else "",
            "Child name/Narrower": "; ".join(child.name for child in self.children),
            "Status": getattr(self, "Status", "") or "NotFound",  # NotFound: No similar concept in studied Standards
            "Associated Standards": "; ".join(getattr(self, "Associated Standards", [])),
            "Alternative Names": "; ".join(getattr(self, "Alternative Names", [])),
            "Alternative Definitions": "; ".join(getattr(self, "Alternative Definitions", [])),
        }
        termdb_cols = [
            "Type",
            "Source name",
            "Record number",
            "Preferred name",
            "Also know as/Alternative",
            "Term related to",
            "Abbreviation",
            "Comments",
        ]
        attrs |= {k: getattr(self, k, "") for k in termdb_cols}
        cols_order = [
            "ID",
            "Term",
            "Type",
            "Source name",
            "Record number",
            "Preferred name",
            "Also know as/Alternative",
            "Term related to",
            "Definition",
            "Abbreviation",
            "Parent name/Broader",
            "Child name/Narrower",
            "Comments",
            "Status",
            "Associated Standards",
            "Alternative Names",
            "Alternative Definitions",
        ]
        return {key: attrs[key] for key in cols_order}

    def serialize(self) -> str:
        return JsonExporter().export(self)

    @classmethod
    def deserialize(cls, data: str) -> "ConceptRootNode":
        return JsonImporter(DictImporter(ConceptNode)).import_(data)

    def to_doc(self) -> str:
        return DOC_TEMPLATE.format(name=self.name, definition=self.definition)

    def to_name_definition_pair(self) -> dict[str, str]:
        return {"name": self.name, "definition": self.definition}

    def merge(self, concept: Concept) -> None:
        new_alt_def = getattr(self, "Alternative Definitions", []).append(concept.definition)
        setattr(self, "Alternative Definitions", new_alt_def)
        new_alt_name = getattr(self, "Alternative Names", []).append(concept.name)
        setattr(self, "Alternative Names", new_alt_name)
        new_ass_std = getattr(self, "Associated Standards", []).append(STANDARD_TEMPLATE.format(**concept.serialize()))
        setattr(self, "Associated Standards", new_ass_std)
        setattr(self, "Status", "Corroborated")

    def insert_as_child(self, concept: Concept) -> "ConceptNode":
        new_node = ConceptNode.from_concept(concept)
        if self.children is None:
            self.children = (new_node,)
        else:
            children = list(self.children)
            children.append(new_node)
            self.children = tuple(children)
        return new_node

    def insert_as_new_parent(self, concept: Concept) -> "ConceptNode":
        new_node = ConceptNode.from_concept(concept)
        # No need to update children relationships as this is maintained by anytree when detaching and attaching
        current_parent = self.parent
        new_node.parent = current_parent
        self.parent = new_node
        return new_node


class ConceptRootNode(ConceptNode):
    def __init__(self, name: str, definition: str, children: Optional[list[Node]] = None, **kwargs):
        super().__init__(name=name, definition=definition, parent=None, children=children, **kwargs)
