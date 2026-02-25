from dataclasses import asdict, dataclass, field
from functools import partial
from typing import Any, Optional
from uuid import UUID, uuid4

from app.utils import convert_str_fields_to_uuid


@dataclass
class SemanticChunk:
    text: str
    page_number: int
    filename: str
    page_tags: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        convert_str_fields_to_uuid(self)

    def serialize(self, list_separator: Optional[str] = None) -> dict[str, Any]:
        return asdict(self, dict_factory=partial(self._serializer, list_separator=list_separator))

    @staticmethod
    def _serializer(data, list_separator: Optional[str] = None):
        s = {}
        for f, value in data:
            if isinstance(value, UUID):
                s[f] = str(value)
            elif isinstance(value, list) and list_separator:
                s[f] = list_separator.join(value)
            else:
                s[f] = value
        return s
