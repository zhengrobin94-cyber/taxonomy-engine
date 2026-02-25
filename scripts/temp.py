from pathlib import Path
import json

from tqdm import tqdm

from app.concept.extractor import extract_concepts
from app.chunk.models import SemanticChunk

standards = "sample-standard"
chunks_filepath = Path(f"./data/{standards} - Chunks.json")

with chunks_filepath.open() as fh:
    data = json.load(fh)

concepts = []
for chunk in tqdm(data):
    c = SemanticChunk(**chunk)
    concepts.extend(extract_concepts(c))

concepts_filepath = Path(f"./data/{standards} - Concepts.json")
concepts_filepath.touch()
with concepts_filepath.open("w") as fh:
    json.dump([c.serialize() for c in concepts], fh, indent=4, default=str)
