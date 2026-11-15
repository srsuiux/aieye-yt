"""The /docs section: Markdown files in the repo's docs/ folder, listed in docs/nav.json, rendered on demand."""
import json
from pathlib import Path
import markdown
from ..config import ROOT

DOCS_DIR = ROOT / "docs"

def nav():
    """[{section, pages: [{slug, title}]}] in reading order."""
    return json.loads((DOCS_DIR / "nav.json").read_text())

def flat():
    return [p for sec in nav() for p in sec["pages"]]

def find(slug):
    for sec in nav():
        for p in sec["pages"]:
            if p["slug"] == slug:
                return sec["section"], p
    return None, None

def render(slug):
    """-> dict(title, section, html, toc, prev, next) or None. Only slugs listed in nav.json can be read."""
    section, page = find(slug)
    if not page:
        return None
    path = (DOCS_DIR / f"{slug}.md").resolve()
    if DOCS_DIR.resolve() not in path.parents or not path.exists():
        return None
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "admonition", "attr_list"],
                           extension_configs={"toc": {"toc_depth": "2-3", "permalink": False}})
    html = md.convert(path.read_text())
    pages = flat()
    i = next(k for k, p in enumerate(pages) if p["slug"] == slug)
    return {"title": page["title"], "section": section, "html": html, "toc": md.toc_tokens, "slug": slug,
            "prev": pages[i - 1] if i > 0 else None, "next": pages[i + 1] if i + 1 < len(pages) else None}
