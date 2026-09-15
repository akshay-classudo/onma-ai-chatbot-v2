"""Generic (not onmascout.de-specific) HTML-to-knowledge-text extraction:
strip script/style/nav/header/footer/forms and anything that looks like a
cookie banner or menu by class/id name, then pull heading + paragraph +
list text from whatever's left, preserving headings as '## Heading' lines
so extracted content reads like the hand-typed knowledge entries."""

import re

from bs4 import BeautifulSoup, Tag

BOILERPLATE_TAGS = ["script", "style", "nav", "header", "footer", "form", "noscript", "svg", "iframe"]
BOILERPLATE_HINTS = ["cookie", "consent", "menu", "navigation", "sidebar", "breadcrumb", "social-share"]
CONTENT_TAGS = ["h1", "h2", "h3", "p", "li"]

# Belt-and-suspenders against cookie/consent banners that aren't in a
# cleanly-classed container (custom widgets, JS-injected markup, etc.) — drop
# any individual line whose text matches one of these regardless of its tag.
COOKIE_LINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"wir verwenden cookies", r"diese (?:webseite|website) verwendet cookies",
        r"cookies? (?:zu )?verwenden", r"cookie-einstellungen",
        r"we use cookies", r"this (?:website|site) uses cookies", r"accept cookies",
        r"informationen zu cookies", r"more information (?:about|on) cookies",
    ]
]


def _is_boilerplate_line(text: str) -> bool:
    return any(pattern.search(text) for pattern in COOKIE_LINE_PATTERNS)


def extract_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag_name in BOILERPLATE_TAGS:
        for el in soup.find_all(tag_name):
            el.decompose()

    for el in soup.find_all(True):
        if not isinstance(el, Tag) or el.attrs is None:
            continue
        marker = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
        marker = marker.lower()
        if any(hint in marker for hint in BOILERPLATE_HINTS):
            el.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup

    lines = []
    first_heading = ""
    for el in main.find_all(CONTENT_TAGS):
        text = el.get_text(" ", strip=True)
        if not text or _is_boilerplate_line(text):
            continue
        if el.name in ("h1", "h2", "h3"):
            lines.append(f"## {text}")
            first_heading = first_heading or text
        else:
            lines.append(text)

    content = "\n\n".join(lines)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    return {"title": title or first_heading, "content": content}
