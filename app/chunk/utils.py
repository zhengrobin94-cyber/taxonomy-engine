import re

from unstructured.documents.elements import Element


def is_header_or_footer(x: Element) -> bool:
    """Classify the `Element` as a "Header"/"Footer" or else.

    Identify if it is a "Header" or "Footer" `Element`, i.e. Chapter name, Document name, Document edition, Page number,
    Classification label.

    Args:
        x (Element): `Element` to categorize into Header/Footer or something else.

    Returns:
        bool: True if the `Element` is a "Header" or "Footer", False otherwise
    """
    return is_header(x) or is_footer(x)


def is_header(x: Element) -> bool:
    """Identify if it is a "Header" `Element`, i.e. Chapter name, Document name, Classification label.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is of type "Header", False otherwise.
    """
    return x.category == "Header" or is_classification_label(x)


def is_footer(x: Element) -> bool:
    """Identify if it is a "Footer" `Element`, i.e. Page number, Document edition, Classification label.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is of type "Footer", False otherwise.
    """
    return is_edition(x) or is_page_number(x) or is_classification_label(x)


def is_page_number(x: Element) -> bool:
    """Identify if the `Element` is about the page number.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is about the page number, False otherwise.
    """
    pattern = r"""
        ^                               # whole string must be a page label
        (?:                             # group of possible formats
            \d+                         # 12
            | p\d+                      # p1
            | [ivxlcdmIVXLCDM]+         # v, IIX (Roman-like)
            | [A-Za-z0-9]+-[A-Za-z0-9]+ # 1-2, A-3, etc.
        )$
    """
    page_re = re.compile(pattern, re.VERBOSE)
    return bool(page_re.match(x.text.strip())) and is_at_bottom_of_page(x)


def is_edition(x: Element) -> bool:
    """Identify if the `Element` is about the edition/version of the document.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is about the edition/version of the document, False otherwise.
    """
    return x.text.strip().casefold().startswith("edition") and is_at_bottom_of_page(x)


def is_classification_label(x: Element) -> bool:
    """Identify if the `Element` is about the classification of the document.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is about the classification label of the document, False otherwise.
    """
    labels = ("unclassified", "restricted", "secret")
    return x.text.strip().casefold() in labels and (is_at_bottom_of_page(x) or is_at_top_of_page(x))


def is_at_bottom_of_page(x: Element) -> bool:
    """Identify if the `Element` is at the bottom of the page.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element`'s location is more or equal to 724 on the X-axis, False otherwise.
    """
    try:
        return x.metadata.coordinates.points[0][1] >= 724
    except:  # noqa
        return False


def is_at_top_of_page(x: Element) -> bool:
    """Identify if the `Element` is at the top of the page.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element`'s location is less or equal to 52 on the X-axis, False otherwise.
    """
    try:
        return x.metadata.coordinates.points[0][1] <= 52
    except:  # noqa
        return False


def is_list_item(x: Element) -> bool:
    """Identify if the `Element` belongs to a list.

    Args:
        x (Element): `Element` to classify.

    Returns:
        bool: True if the `Element` is part of a list, False otherwise.
    """
    pattern = re.compile(r"^(?:\d+[.)]|[A-Za-z][.)]|i{1,3}\.)")
    return bool(pattern.match(x.text.lstrip()))
