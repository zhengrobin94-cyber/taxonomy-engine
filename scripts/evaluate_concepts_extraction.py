"""
Concept Extraction Evaluation Pipeline
Compares LLM-extracted concepts against SME-highlighted ground truth.

Usage: python evaluate_extraction.py <chunks_json> <ground_truth_json>

Example:
    python evaluate_extraction.py \
        "document_extracted_concepts.json" \
        "document_ground_truth.json"
"""

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
from typing import Optional
from uuid import UUID

from app.concept.models import Concept


@dataclass
class ConceptGT:
    name: str
    definition: str
    page_number: int


@dataclass
class BaseConcept:
    name: str
    definition: str
    page_number: int
    id: Optional[UUID] = None

    @classmethod
    def from_ConceptGT(cls, x: ConceptGT) -> "BaseConcept":
        return cls(name=x.name, definition=x.definition, page_number=x.page_number)

    @classmethod
    def from_Concept(cls, x: Concept) -> "BaseConcept":
        return cls(name=x.name, definition=x.definition, page_number=x.page_number, id=x.id)


@dataclass
class EvaluationResult:
    """Stores evaluation metrics and details."""

    true_positives: list[ConceptGT]
    false_positives: list[Concept]
    false_negatives: list[ConceptGT]
    match_pairs: list[tuple[ConceptGT, BaseConcept]]
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1_score: float
    total_extracted: int
    total_ground_truth: int


class ConceptMatcher:
    """Handles fuzzy matching between extracted and ground truth concepts."""

    def __init__(self, similarity_threshold: float = 0.6):
        """
        Args:
            similarity_threshold: Minimum similarity ratio (0-1) for a match
        """
        self.similarity_threshold = similarity_threshold

    def normalize_text(self, x: str) -> str:
        """Normalize text for comparison."""
        x = x.lower()
        # Remove extra whitespace
        x = " ".join(x.split())
        # Remove footnote references (e.g., "deployment.3" -> "deployment")
        x = re.sub(r"\.\d+\s*", ". ", x)
        # Remove punctuation at start/end
        x = x.strip(".,;:")
        return x

    def normalize_concept(self, x: BaseConcept) -> tuple[str, str]:
        return self.normalize_text(x.name), self.normalize_text(x.definition)

    def similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two texts."""
        return max(SequenceMatcher(a=a, b=b).ratio(), SequenceMatcher(a=b, b=a).ratio())

    def similarity_name(self, a: str, b: str) -> float:
        if a in b or b in a:
            # This is to cope with acronyms. Sometimes, the LLM will only extract the acronym and not the full name
            return 1.0
        return self.similarity(a, b)

    def similarity_definition(self, gt: str, candidate: str, strict: bool = False) -> float:
        score = self.similarity(gt, candidate)
        if strict:
            return score
        # Sometimes the LLM might not limit itself to a single sentence for the definition. In this case we only
        # check the first sentence
        candidate_parts = candidate.split(".")
        if len(candidate_parts) == 1:
            return score
        return max(score, self.similarity(candidate_parts[0], gt))

    def find_match(
        self, concept: BaseConcept, candidates: list[BaseConcept]
    ) -> Optional[tuple[BaseConcept, float, int]]:
        """Find the best matching ground truth concept for an extracted concept."""
        concept_name, concept_def = self.normalize_concept(concept)

        best_match = None
        best_match_idx = -1
        best_score = 0

        for idx, candidate in enumerate(candidates):
            candidate_name, candidate_def = self.normalize_concept(candidate)

            name_score = self.similarity_name(concept_name, candidate_name)
            definition_score = self.similarity_definition(concept_def, candidate_def)
            same_page = concept.page_number == candidate.page_number

            combined_score = 0.60 * definition_score + 0.25 * name_score + 0.15 * same_page

            if combined_score > best_score:
                best_score = combined_score
                best_match = candidate
                best_match_idx = idx

        if best_score >= self.similarity_threshold:
            return (best_match, best_score, best_match_idx)


def load_concepts(concepts_filepath: Path) -> list[Concept]:
    """Load extracted concepts from JSON file."""
    with concepts_filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [Concept(**concept) for concept in data]


def indexing_concepts_by_page_number(concepts: list[Concept]):
    index = defaultdict(list)
    for concept in concepts:
        index[concept.page_number].append(concept)
    return index


def load_ground_truth(gt_path: str) -> list[ConceptGT]:
    """Load ground truth concepts from JSON file."""
    with gt_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [ConceptGT(**concept) for concept in data["concepts"]]


def evaluate(
    extracted_concepts: list[Concept], ground_truth: list[ConceptGT], similarity_threshold: float = 0.6
) -> EvaluationResult:
    """
    Evaluate extracted concepts against ground truth.

    Args:
        extracted_concepts: List of concepts extracted by the system
        ground_truth: List of ground truth concepts from SME
        similarity_threshold: Minimum similarity for a match

    Returns:
        EvaluationResult with metrics
    """
    matcher = ConceptMatcher(similarity_threshold=similarity_threshold)

    true_positives = []
    false_negatives = []
    matched_extracted_concepts = set()
    match_pairs: list[tuple[ConceptGT, BaseConcept]] = []

    extracted_concepts_idx = indexing_concepts_by_page_number(extracted_concepts)
    previous_p_nbr = None

    # Check each extracted concept
    for gt_concept in ground_truth:
        p_nbr = gt_concept.page_number
        if p_nbr != previous_p_nbr:  # Recreate the concepts candidates if we move to another page
            extracted_concepts_candidates = []
            for x in [-1, 0, 1]:
                extracted_concepts_candidates.extend(extracted_concepts_idx[p_nbr + x])
            extracted_concepts_candidates = [BaseConcept.from_Concept(ecc) for ecc in extracted_concepts_candidates]

        match = matcher.find_match(BaseConcept.from_ConceptGT(gt_concept), extracted_concepts_candidates)

        if match:
            matched_concept, score, idx = match
            match_pairs.append((gt_concept, matched_concept))
            del extracted_concepts_candidates[idx]  # Remove this candidates from the pool to avoid duplicated matches
            if matched_concept.id not in matched_extracted_concepts:
                true_positives.append(gt_concept)
                matched_extracted_concepts.add(matched_concept.id)
            else:
                # Already matched this concept, count as duplicate/FP
                false_negatives.append(gt_concept)
        else:
            false_negatives.append(gt_concept)

    false_positives = [ec for ec in extracted_concepts if ec.id not in matched_extracted_concepts]

    # Calculate metrics
    tp = len(true_positives)
    fp = len(false_positives)
    fn = len(false_negatives)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return EvaluationResult(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        match_pairs=match_pairs,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        total_extracted=len(extracted_concepts),
        total_ground_truth=len(ground_truth),
    )


def build_report(result: EvaluationResult) -> str:
    """Build evaluation report"""
    report = []
    report.append("+===================================+")
    report.append("CONCEPTS EXTRACTION EVALUATION REPORT")
    report.append("+===================================+")
    report.append("")

    report.append("SUMMARY METRICS")
    report.append("---------------")
    report.append("{:<35s}{}".format("Total extracted concepts:", result.total_extracted))
    report.append("{:<35s}{}".format("Total ground truth concepts:", result.total_ground_truth))
    report.append("")
    report.append("{:<35s}{}".format("True Positives (TP):", result.tp))
    report.append("{:<35s}{}".format("False Positives (FP):", result.fp))
    report.append("{:<35s}{}".format("False Negatives (FN):", result.fn))
    report.append("")
    report.append("{:<35s}{:.2%}".format("Precision:", result.precision))
    report.append("{:<35s}{:.2%}".format("Recall:", result.recall))
    report.append("{:<35s}{:.2%}".format("F1-Score:", result.f1_score))
    report.append("")

    report.append("CONFUSION MATRIX")
    report.append("----------------")
    report.append("")
    report.append("{:<20s}{}".format("", "Predicted"))
    report.append("{:<15s}{:3}{:<10s}{}".format("", "Pos", "", "Neg"))
    report.append("{:<15s}{:3}{:<10s}{}     {}".format("Actual Pos", result.tp, "", result.fn, "(TP, FN)"))
    report.append("{:<15s}{:3}{:<10s}{}     {}".format("Actual Neg", result.fp, "", "-", "(FP, TN)"))
    report.append("")

    report.append("DETAILS")
    report.append("-------")
    max_nbr_samples = 50
    if result.match_pairs:
        report.append("")
        report.append("Matched concepts - True Positives")
        report.append("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        for i, (gt, match) in enumerate(result.match_pairs[:max_nbr_samples], 1):
            report.append(f"\t{i}. [p.{gt.page_number}] {gt.name} - {gt.definition}")
            report.append(f"\t\tmatched with >> [p. {match.page_number}] {match.name} - {match.definition}")

        if result.tp > max_nbr_samples:
            report.append(f"... and {result.tp - max_nbr_samples} more")

    if result.false_negatives:
        report.append("")
        report.append("Missed concepts - False Negatives")
        report.append("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        for i, fn in enumerate(result.false_negatives[:max_nbr_samples], 1):
            report.append(f"\t{i}. [p.{fn.page_number}] {fn.name} - {fn.definition}")
        if result.fn > max_nbr_samples:
            report.append(f"... and {result.fn - max_nbr_samples} more")

    if result.false_positives:
        report.append("")
        report.append("Wrongly extracted concepts - False Positives")
        report.append("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        for i, fp in enumerate(result.false_positives[:max_nbr_samples], 1):
            report.append(f"\t{i}. [p.{fp.page_number}] {fp.name} - {fp.definition}")
        if result.fp > max_nbr_samples:
            report.append(f"... and {result.fp - max_nbr_samples} more")

    report.append("")
    report.append("+===================================+")

    return "\n".join(report)


def main():
    if len(sys.argv) < 3:
        print("Usage: python evaluate_concepts_extraction.py <extracted_concepts_filepath> <ground_truth_filepath>")
        print("\nExample:")
        print('\tpython evaluate_concepts_extraction.py "extracted_concepts.json" "ground_truth.json"')
        sys.exit(1)

    concepts_filepath = Path(sys.argv[1])
    gt_filepath = Path(sys.argv[2])

    # Validate files exist
    if not concepts_filepath.exists():
        print(f"Error: extracted_concepts file not found: {concepts_filepath}")
        sys.exit(1)
    if not gt_filepath.exists():
        print(f"Error: ground_truth file not found: {gt_filepath}")
        sys.exit(1)

    concepts = load_concepts(concepts_filepath)
    ground_truth = load_ground_truth(gt_filepath)

    result = evaluate(concepts, ground_truth)
    report = build_report(result)
    print(report)

    report_path = concepts_filepath.stem + "_evaluation_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
