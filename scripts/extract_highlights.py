"""
Extract highlighted text from PDF annotations (ground truth from SME)
Usage: python extract_highlights.py <highlighted_pdf_path>
"""

import json
import sys
from pathlib import Path
import logging

import fitz  # PyMuPDF - better for extracting highlights than pdfplumber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_highlights_pymupdf(pdf_path: str) -> list:
    """
    Extract highlighted text from PDF using PyMuPDF.
    Returns list of highlighted text segments with metadata.
    """
    highlights = []

    doc = fitz.open(pdf_path)
    logger.info(f"Processing {Path(pdf_path).name}: {len(doc)} pages")

    for page_num, page in enumerate(doc):
        # Get all annotations on this page
        annots = page.annots()

        if annots:
            for annot in annots:
                # Check if it's a highlight annotation (type 8)
                if annot.type[0] == 8:  # Highlight
                    # Get the rectangle coordinates of the highlight
                    rect = annot.rect

                    # Extract text from the highlighted area
                    highlighted_text = page.get_text("text", clip=rect).strip()

                    if highlighted_text:
                        highlights.append({
                            "page": page_num + 1,
                            "text": highlighted_text,
                            "type": "highlight",
                            "rect": [rect.x0, rect.y0, rect.x1, rect.y1]
                        })
                        logger.debug(f"Page {page_num + 1}: '{highlighted_text[:50]}...'")

    doc.close()
    logger.info(f"Extracted {len(highlights)} highlighted sections")
    return highlights


def extract_highlights_pdfplumber(pdf_path: str) -> list:
    """
    Fallback: Extract highlights using pdfplumber.
    """
    import pdfplumber

    highlights = []

    with pdfplumber.open(pdf_path) as pdf:
        logger.info(f"Processing {Path(pdf_path).name}: {len(pdf.pages)} pages")

        for page_num, page in enumerate(pdf.pages):
            if page.annots:
                for annot in page.annots:
                    subtype = annot.get('subtype', '')
                    if subtype == 'Highlight':
                        # Try to get contents or extract from coordinates
                        text = annot.get('contents', '')

                        if not text and 'rect' in annot:
                            # Try extracting text from the highlight region
                            rect = annot['rect']
                            text = page.within_bbox(rect).extract_text() or ''

                        if text:
                            highlights.append({
                                "page": page_num + 1,
                                "text": text.strip(),
                                "type": "highlight"
                            })

    logger.info(f"Extracted {len(highlights)} highlighted sections")
    return highlights


def clean_and_dedupe_highlights(highlights: list) -> list:
    """Clean up extracted highlights and remove duplicates."""
    seen = set()
    cleaned = []

    for h in highlights:
        # Normalize text
        text = h['text'].strip()
        text = ' '.join(text.split())  # Normalize whitespace

        if text and text not in seen:
            seen.add(text)
            cleaned.append({
                "page": h['page'],
                "text": text,
                "type": h['type']
            })

    return cleaned


def save_ground_truth(highlights: list, output_path: str):
    """Save highlights as ground truth JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "source": "SME highlighted document",
            "total_concepts": len(highlights),
            "concepts": highlights
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved ground truth to {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_highlights.py <highlighted_pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    # Try PyMuPDF first (better highlight extraction)
    try:
        highlights = extract_highlights_pymupdf(pdf_path)
    except ImportError:
        logger.warning("PyMuPDF not installed, falling back to pdfplumber")
        highlights = extract_highlights_pdfplumber(pdf_path)

    # Clean and deduplicate
    highlights = clean_and_dedupe_highlights(highlights)

    # Save output
    output_path = Path(pdf_path).stem + "_ground_truth.json"
    save_ground_truth(highlights, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print(f"[SUCCESS] Extracted highlights from {Path(pdf_path).name}")
    print(f"  Total highlighted concepts: {len(highlights)}")
    print(f"  Output: {output_path}")

    if highlights:
        print("\n" + "-" * 60)
        print("Sample highlights:")
        for h in highlights[:5]:
            print(f"  Page {h['page']}: {h['text'][:80]}...")
    print("=" * 60)


if __name__ == "__main__":
    main()
