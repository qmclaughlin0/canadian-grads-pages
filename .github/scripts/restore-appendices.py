"""Reconnect the book's appendix cards to the PDFs in the public export."""
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import sys


def restore(public):
    book = public / "book/index.html"
    css = public / "book.css"
    text = book.read_text(encoding="utf-8")
    cards = re.compile(
        r'<(?P<tag>div|a)\b[^>]*class="book-resource"[^>]*>'
        r'(?P<body><span class="book-resource-code">Appendix (?P<code>[B-M])</span>'
        r'<span class="book-resource-name">[^<]+</span>)</(?P=tag)>')
    linked = []

    def link(match):
        code = match["code"]
        files = sorted((public / "assets").glob(f"*-Appendix-{code}-*.pdf"))
        if len(files) != 1:
            raise ValueError(f"Expected one PDF for Appendix {code}, found {len(files)}")
        pdf = files[0]
        with pdf.open("rb") as handle:
            if not handle.read(8).startswith(b"%PDF-"):
                raise ValueError(f"Invalid PDF: {pdf.name}")
        if code in linked:
            raise ValueError(f"Duplicate appendix card: {code}")
        linked.append(code)
        href = "/" + pdf.relative_to(public).as_posix() + "?v=" + sha256(pdf.read_bytes()).hexdigest()[:12]
        return (f'<a class="book-resource" href="{escape(href, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer" title="Open Appendix {code} PDF">'
                + match["body"] + '</a>')

    updated = cards.sub(link, text)
    if set(linked) != set("BCDEFGHIJKLM"):
        raise ValueError(f"Expected 12 appendix cards (B–M), found {linked}")
    # Links inherit the original card text color instead of the theme link color.
    color_rule = ".cg-book a.book-resource { color: inherit; }"
    styles = css.read_text(encoding="utf-8")
    if color_rule not in styles:
        styles = styles.rstrip() + "\n\n" + color_rule + "\n"
        css.write_text(styles, encoding="utf-8", newline="\n")
    version = sha256(styles.encode()).hexdigest()[:12]
    updated = re.sub(r"/book\.css(?:\?v=[^\"'\s>]+)?", "/book.css?v=" + version, updated)
    book.write_text(updated, encoding="utf-8", newline="\n")
    print("Restored 12 appendix PDF links (B–M), preserving the existing card layout.")


if __name__ == "__main__":
    restore(Path(sys.argv[1]))
