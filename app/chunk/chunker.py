"""
Class to extract chunks / snippets of texts from a standards document in PDF format.
"""

from itertools import filterfalse
from io import BytesIO
from typing import Iterable, NewType, Optional, Self

from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Element

from app.chunk.models import SemanticChunk
from app.chunk.utils import is_header_or_footer, is_list_item
from app.chunk.typings import PartitionStrategy

PageTags = NewType("PageTags", list[list[str]])  # Its length will depend on the number of page in the document


class StandardPDFChunker:
    def __init__(self, file: BytesIO, filename: str):
        """Class to extract chunks from a standards document in PDF format.

        Args:
            file (BytesIO): Handler for the standards document.
            filename (str): Name of the standards document.
        """
        self.file = file
        self.filename = filename
        self.elements: list[Element] = []
        self.chunks: list[SemanticChunk] = []
        self.page_tags: PageTags = []

    def __call__(
        self,
        strategy: PartitionStrategy = "fast",
        languages: Optional[list[str]] = ["eng"],
        search_first_chapter_page_limit: int = 25,
        soft_max_characters: int = 750,
        ignore_page_boundaries: bool = True,
    ) -> list[SemanticChunk]:
        """Extract relevant chunks from the file.

        In order to extract self-contained semantic chunks, they are made of at least one paragraph, but can regroup
        several in an attempt to fully capture the context. Hence, chunks have no defined upper and lower bounds in
        terms of length. However a soft upper bound can be defined to stop attaching paragraphs to a chunk that would
        already be too long.
        Chunks are extracted starting from the first chapter, if found, thus ignoring the first couple of introductory
        pages.

        Args:
            strategy (PartitionStrategy, optional): The strategy to be used to partition the file.
                See https://docs.unstructured.io/open-source/concepts/partitioning-strategies#partitioning-strategies.
                Defaults to PartitionStrategy.FAST.
            languages (Optional[list[str]], optional): Language(s) in which the document is written, for use in
                partitioning and/or OCR. For french, use `fre`. Defaults to ["eng"].
            search_first_chapter_page_limit (int, optional): Page # up to which to look for the first chapter.
                Defaults to 25.
            soft_max_characters (int, optional): Soft length limit for chunks. When a chunk has accumulated more
                characters than this threshold, no more paragraphs are added to it. Defaults to 750.
            ignore_page_boundaries (bool, optional): Whether to disregard page boundaries when creating chunks or to
                automatically stop a chunk when the end of the page is reached. Defaults to True.

        Returns:
            list[SemanticChunk]: Extracted chunks.
        """
        self.partition(strategy, languages)
        self.postprocess_elements(search_first_chapter_page_limit)
        self.generate_chunks(soft_max_characters, ignore_page_boundaries)
        return self.chunks

    def partition(self, strategy: PartitionStrategy = "fast", languages: Optional[list[str]] = ["eng"]) -> Self:
        """Partition the file into labeled `Elements` such as "Headers", "Titles", "Paragraphs", "Footers", etc..

        Args:
            strategy (PartitionStrategy, optional): The strategy to be used to partition the file.
                See https://docs.unstructured.io/open-source/concepts/partitioning-strategies#partitioning-strategies.
                Defaults to PartitionStrategy.FAST.
            languages (Optional[list[str]], optional):  Language(s) in which the document is written, for use in
                partitioning and/or OCR. For french, use `fre`. Defaults to ["eng"].

        Returns:
            Self: Chunker instance.
        """
        self.elements = partition_pdf(file=self.file, languages=languages, strategy=strategy)
        return self

    def postprocess_elements(self, search_first_chapter_page_limit: int = 25) -> Self:
        """Postprocess `Elements` identified by partitioning the file.

        - Look ahead for the first chapter's page. If found, only start extracting chunks from this page.
        - Build a lookup array for page tags. Those tags can be useful to contextualize chunks. For instance, a chunk
            extracted from a Lexicon page should be identified as such as it might contain more relevant information.
        - Discard "Header" and "Footer" `Elements` as they will otherwise be inserted in between a chunk spread across two
            pages and thus break its continuity.

        Args:
            search_first_chapter_page_limit (int, optional): Page # up to which to look for the first chapter.
                Defaults to 25.

        Returns:
            Self: Chunker instance.
        """
        self._skip_to_first_chapter_page(search_first_chapter_page_limit)
        self.page_tags = self._sanitize_and_propagate_lexicon_tags(self._extract_page_tags())
        self._filter_header_and_footer_elements()
        return self

    def generate_chunks(self, soft_max_characters: int = 750, ignore_page_boundaries: bool = True) -> Self:
        """Generate chunks from postprocessed `Elements` extracted from partitioning.

        To create Semantically relevant chunks, `Elements` are regrouped if:
            - they are part of a list;
            - they don't end with a closing punctuation, such as '.', ')', or ']'.

        Args:
            soft_max_characters (int, optional): Soft length limit for chunks. When a chunk has accumulated more
                characters than this threshold, no more paragraphs are added to it. Defaults to 750.
            ignore_page_boundaries (bool, optional): Whether to disregard page boundaries when creating chunks or to
                automatically stop a chunk when the end of the page is reached. Defaults to True.

        Returns:
            Self: Chunker instance.
        """

        def flush() -> None:
            acc = [el.text.strip() for el in accumulator if el.text.strip()]
            if acc:
                self.chunks.append(self._build_chunk("\n".join(acc), accumulator[0].metadata.page_number))

        def reset() -> None:
            nonlocal accumulator, accumulator_size
            accumulator = []
            accumulator_size = 0

        def flush_and_reset_accumulator() -> None:
            flush()
            reset()

        n_elements = len(self.elements)
        accumulator: list[Element] = []
        previous_element_page_number = None
        accumulator_size = 0
        for idx, el in enumerate(self.elements):
            el_text = el.text.strip()
            # BREAK: If non multi-pages chunks and next page
            if not ignore_page_boundaries and el.metadata.page_number != previous_element_page_number:
                flush_and_reset_accumulator()

            # BREAK: Chunk size limit reached
            if (accumulator_size + len(el_text)) > soft_max_characters:
                flush_and_reset_accumulator()

            # ACCUMULATE
            accumulator.append(el)
            accumulator_size += len(el_text)
            previous_element_page_number = el.metadata.page_number

            # ACCUMULATE: Regroup elements that are part of a list
            if is_list_item(el):
                continue  # To cover for cases where we only have the list item number, i.e. a single 1. or a.

            # BREAK: Semantic break at the end of a line
            if el_text.endswith((".", ")", "]")):
                # Order is important. This `break` should be tested before the ListItem comparison because the last
                # element of the list might be a ListItem, and it is the case, it usually ends with a `.`.
                flush_and_reset_accumulator()
                continue

            # ACCUMULATE: Regroup elements that are part of a list
            if el.category == "ListItem" or el_text.endswith((":", ";", "; and")) or not el_text.endswith("."):
                continue

            # BREAK: End of file break
            if idx == n_elements - 1:
                flush_and_reset_accumulator()

            # BREAK: End of list
            if self.elements[idx + 1].category != "ListItem":
                flush_and_reset_accumulator()

        return self

    def _build_chunk(self, text: str, page_number: int) -> SemanticChunk:
        """Assemble a chunk from text and the page number where it starts.

        Args:
            text (str): Snippet of text representing the chunk.
            page_number (int): Page # where the chunk starts.

        Returns:
            SemanticChunk: Chunk with its metadata.
        """
        return SemanticChunk(
            text=text,
            page_tags=self.page_tags[page_number],
            page_number=page_number,
            filename=self.filename,
        )

    def _skip_to_first_chapter_page(self, search_page_limit: int = 25) -> None:
        """Discard `Elements` that appear on introductory pages, i.e. before the first chapter.

        Args:
            search_page_limit (int, optional): Page # up to which to look for the first chapter. Defaults to 25.
        """
        first_chapter_page_number = self._find_first_chapter_page(search_page_limit) or 0
        for idx, el in enumerate(self.elements):
            if el.metadata.page_number >= first_chapter_page_number:
                break
        self.elements = self.elements[idx:]

    def _find_first_chapter_page(self, search_page_limit: int = 25) -> Optional[int]:
        """Find the page number where the firs chapter starts.

        The strategy is to first find the Preface page as the first chapter starts often right after it. However,
        the Preface is not always present. As a fallback, the page where the Table of Content starts is also inferred.
        All pages where "chapter 1" is found are listed, and the first page where this mention is found, and that is
        after the Preface and/or the Table of Content, is considered the page where the first chapter starts.

        Args:
            search_page_limit (int, optional): Page # up to which to look for the first chapter. Defaults to 25.

        Returns:
            Optional[int]: Page number where the first chapter starts, if found.
        """
        table_of_contents_page_number = 0
        preface_page_number = 0
        chapter_1_page_numbers = set()
        for el in self.elements:
            cleaned_text = el.text.strip().lower()

            if cleaned_text == "preface":
                preface_page_number = el.metadata.page_number
            if cleaned_text == "table of contents":  # Since Preface is not always present in standards documents
                table_of_contents_page_number = el.metadata.page_number
            if "chapter 1" in cleaned_text:
                chapter_1_page_numbers.add(el.metadata.page_number)

            if el.metadata.page_number > search_page_limit:
                break

        if not chapter_1_page_numbers:
            return None

        # The first chapter should only start after the Table of Content, and Preface if present.
        last_intro_page_number = max(table_of_contents_page_number, preface_page_number)
        chapter_1_page_candidates = [x for x in chapter_1_page_numbers if x > last_intro_page_number]
        if chapter_1_page_candidates:
            # Minimum because the "Chapter 1" caption can be included in the header of each chapter's pages
            return min(chapter_1_page_candidates)

    def _extract_page_tags(
        self, exclude: Iterable[str] = ("unclassified", "restricted", "edition", "intentionally blank")
    ) -> PageTags:
        """Create an array where element at index _i_ contains the tags associated to the page _i_.

        Tags are based on the page "Header" and "Title" `Elements`.

        Args:
            exclude (Iterable[str], optional): Exclude those "Header"s and "Title"s to be used as tags. Defaults to
                ("unclassified", "restricted", "edition", "intentionally blank").

        Returns:
            PageTags: Array which length equals the number of pages in the file and where element at index _i_ contains
                the tags associated to the page _i_.
        """
        exclude = tuple(x.casefold() for x in exclude)
        page_tags = [[] for _ in range(self.elements[-1].metadata.page_number + 1)]
        for el in self.elements:
            if el.category in ("Header", "Title"):
                cleaned_text = el.text.strip()
                if len(cleaned_text) <= 5:
                    continue
                if not exclude:
                    page_tags[el.metadata.page_number].append(cleaned_text)
                elif not cleaned_text.casefold().startswith(exclude):
                    page_tags[el.metadata.page_number].append(cleaned_text)
        return page_tags

    def _sanitize_and_propagate_lexicon_tags(self, page_tags: PageTags) -> PageTags:
        """Clean up tags and propagate Lexicon tags.

        Search for Lexicon, Acronyms, Abbreviations, Terms, Definitions keywords in headers. If present, sanitize
        header and try to propagate to next page if similar headers are found but without those keywords

        Args:
            page_tags (PageTags): Tags to clean up and for which to propagate Lexicon tags.

        Returns:
            PageTags: Sanitized PageTags array.
        """
        # TODO: Propagate only if we are in the bottom 15% of the document to prevent propagate too early if the Lexicon
        # has been used as a pointer in the first part of the document.
        predefined_keywords = {"lexicon", "acronyms", "abbreviations", "terms", "definitions"}
        dynamic_lookups = set()
        for idx, ph in enumerate(page_tags):
            saved_headers = set()
            for header in ph:
                header = header.casefold()
                for pk in predefined_keywords:
                    if pk in header:
                        saved_headers.add(pk)
                if header in dynamic_lookups:
                    saved_headers.add("lexicon")
            if saved_headers:
                dynamic_lookups.update(map(lambda header: header.casefold(), ph))
                page_tags[idx] = list(saved_headers)
        return page_tags

    def _filter_header_and_footer_elements(self) -> None:
        """Discard "Header" and "Footer" `Elements`.

        Try to filter out `Elements` in the header (i.e. chapter name, document name, classification label) and in the
        footer (i.e. page number, document edition, classification label) to avoid breaking up the continuity of chunks
        spanning across multiple pages.
        """
        self.elements = list(filterfalse(is_header_or_footer, self.elements))
