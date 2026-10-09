"""Adapt the public website package for the canadiangrads.shop root domain."""
from pathlib import Path
import sys

public = Path(sys.argv[1])
old_site = b"https://qmclaughlin0.github.io/canadian-grads-pages"
site = b"https://canadiangrads.shop"
old_prefix = b"/canadian-grads-pages/"
updated = 0
for path in public.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in (".html", ".css", ".js", ".svg", ".xml", ".txt"):
        continue
    original = path.read_bytes()
    text = original.replace(old_site, site).replace(old_prefix, b"/")
    if text != original:
        path.write_bytes(text)
        updated += 1
print(f"Configured {updated} public files for {site.decode()}")
