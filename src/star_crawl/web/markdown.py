"""Safe markdown rendering: markdown-it-py → bleach sanitize."""

from __future__ import annotations

import bleach
from markdown_it import MarkdownIt

ALLOWED_TAGS = [
    "p", "br", "hr", "blockquote", "pre", "code",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "strong", "em", "del", "s", "ins", "u",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "sup", "sub", "abbr", "kbd", "mark", "small",
    "div", "span",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "abbr": ["title"],
    "kbd": [],
    "code": ["class"],
    "pre": ["class"],
    "td": ["align"],
    "th": ["align"],
    "div": ["class"],
    "span": ["class"],
}

_md = (
    MarkdownIt("commonmark", {"breaks": True, "linkify": True, "html": False})
    .enable(["table", "strikethrough"])
)


def render(md_text: str) -> str:
    """Render markdown to sanitized HTML safe for inclusion in templates."""
    raw = _md.render(md_text)
    cleaned = bleach.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return bleach.linkify(cleaned, callbacks=[_open_links_in_new_tab])


def _open_links_in_new_tab(attrs, new=False):
    attrs[(None, "rel")] = "noopener noreferrer"
    attrs[(None, "target")] = "_blank"
    return attrs
