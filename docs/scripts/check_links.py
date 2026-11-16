"""Check local URLs and fragments in the built site, including the retained demo."""

from html.parser import HTMLParser
import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.urls = []
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        # Canonical metadata is not a navigable URL (notably the static 404 route).
        if tag == "link" and attrs.get("rel") == "canonical":
            return
        for name in ("href", "src", "poster", "data-src"):
            if attrs.get(name):
                self.urls.append(attrs[name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=Path(__file__).resolve().parents[1] / "_site")
    parser.add_argument("--baseurl", default="/MarsLab")
    parser.add_argument("--origin", default="https://kimhoyun-robotair.github.io")
    args = parser.parse_args()
    root = args.site_dir.resolve()
    base = args.baseurl.rstrip("/") + "/"
    origin = args.origin.rstrip("/")
    if not (root / "index.html").exists():
        raise SystemExit("Build the website first: cd docs && jekyll build --safe")
    pages = {path: Page(path) for path in root.rglob("*.html")}
    errors = []
    checked = 0
    for path, page in pages.items():
        relative = path.relative_to(root).as_posix()
        page_url = origin + base + relative
        for url in page.urls:
            parsed = urlsplit(urljoin(page_url, url))
            if parsed.scheme not in ("http", "https") or parsed.netloc != urlsplit(origin).netloc:
                continue
            if not parsed.path.startswith(base):
                errors.append(f"{relative}: URL escapes project base: {url}")
                continue
            target = root / unquote(parsed.path.removeprefix(base))
            if target.is_dir():
                target /= "index.html"
            checked += 1
            if not target.is_file():
                errors.append(f"{relative}: missing target: {url}")
            elif parsed.fragment and target.suffix == ".html":
                target_page = pages.get(target)
                if target_page is None:
                    target_page = Page(target)
                if unquote(parsed.fragment) not in target_page.ids:
                    errors.append(f"{relative}: missing fragment: {url}")
    index = json.loads((root / "search.json").read_text())
    if not index:
        errors.append("Search index is empty")
    for document in index:
        url = urlsplit(document["url"])
        target = root / url.path.removeprefix(base) / "index.html"
        if not url.path.startswith(base) or not target.is_file() or not document.get("content"):
            errors.append(f"Invalid search entry: {document['title']}")
        if "{{" in document["content"] or "{%" in document["content"]:
            errors.append(f"Unrendered template in search entry: {document['title']}")
    if errors:
        raise SystemExit("\n".join(sorted(set(errors))))
    print(f"Checked {len(pages)} HTML pages and {checked} local links/assets; no broken targets or fragments.")
    print(f"Search index: {len(index)} documents with valid targets.")


if __name__ == "__main__":
    main()
