"""Reduce public asset downloads without changing the site's CSS or image geometry.

Run after configure-domain.py, against a fresh extraction of the public package.
Requires Pillow 12.3.0. Original images remain available for downloads/metadata.
"""
from hashlib import sha256
from html import escape, unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import json
import re
import sys

from PIL import Image, ImageOps


ROOT = Path(sys.argv[1]).resolve()
TEXT_SUFFIXES = {".html", ".css"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
ASSET_URL = re.compile(r"/assets/[^\s\"'()<>?,]+")
ATTR = re.compile(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.S)
LINK = re.compile(r"<link\b[^>]*>", re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)
CHARSET = re.compile(r"@charset\s+[\"'][^\"']+[\"']\s*;", re.I)
report = {"images": [], "stylesheets": [], "lazy_images": 0}


def attrs(tag):
    return {m[1].lower(): unescape(m[3]) for m in ATTR.finditer(tag)}


def local_path(url):
    path = (ROOT / url.lstrip("/").split("?", 1)[0].split("#", 1)[0]).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Asset escapes public directory: {url}")
    return path


def save_webp(image, info, label, lossless):
    buffer = BytesIO()
    options = {"lossless": lossless, "quality": 100 if lossless else 90,
               "method": 6, "exact": True}
    for key in ("icc_profile", "exif", "xmp"):
        if info.get(key):
            options[key] = info[key]
    image.save(buffer, format="WEBP", **options)
    content = buffer.getvalue()
    name = sha256(content).hexdigest()[:16] + "-" + label + ".webp"
    return content, "/assets/" + name


# Preserve all inline image dimensions and srcset descriptors. Photos used as
# backgrounds get a separate 2560px version; CSS keeps its existing crop/size.
texts = {p: p.read_text(encoding="utf-8") for p in sorted(ROOT.rglob("*"))
         if p.is_file() and p.suffix in TEXT_SUFFIXES}
css_refs = {url for p, text in texts.items() if p.suffix == ".css"
            for url in ASSET_URL.findall(text)}
all_refs = {url for text in texts.values() for url in ASSET_URL.findall(text)}
html_images = {}
css_images = {}
for url in sorted(all_refs):
    source = local_path(url)
    if source.suffix.lower() not in IMAGE_SUFFIXES or not source.is_file():
        continue
    original_size = source.stat().st_size
    if original_size < 12000:
        continue
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) != 1:
            continue
        image = ImageOps.exif_transpose(original)
        image = image.convert("RGBA" if "A" in image.getbands()
                              or "transparency" in original.info else "RGB")
        info = dict(original.info)
        exif = original.getexif()
        # Pixel orientation is applied above, so do not apply it twice in WebP.
        if exif:
            exif.pop(274, None)
            info["exif"] = exif.tobytes()
        dimensions = image.size
        # Text on covers, logos and diagrams must stay pixel-exact.
        is_photo = any(token in source.name.lower()
                       for token in ("unsplash", "img_3171", "untitled-design-1"))
        content, target = save_webp(image, info, source.stem, not is_photo)
        if len(content) < original_size * .95:
            local_path(target).write_bytes(content)
            html_images[url] = target
            css_images[url] = target
            report["images"].append({"source": url, "target": target,
                "usage": "original dimensions", "dimensions": dimensions,
                "before": original_size, "after": len(content),
                "lossless": not is_photo})
        if url in css_refs and is_photo and max(dimensions) > 2560:
            background = image.copy()
            background.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            content, target = save_webp(background, info, source.stem + "-background", False)
            if len(content) < original_size * .95:
                local_path(target).write_bytes(content)
                css_images[url] = target
                report["images"].append({"source": url, "target": target,
                    "usage": "CSS background", "dimensions": background.size,
                    "before": original_size, "after": len(content), "lossless": False})


def replace_urls(text, replacements):
    return ASSET_URL.sub(lambda m: replacements.get(m[0], m[0]), text)


for path, text in texts.items():
    # Keep structured social metadata and direct full-image download links intact.
    if path.suffix == ".css":
        text = replace_urls(text, css_images)
    else:
        text = IMG.sub(lambda m: replace_urls(m[0], html_images), text)
    path.write_text(text, encoding="utf-8", newline="\n")


def stylesheet(tag):
    a = attrs(tag)
    if (a.get("rel") == "stylesheet" and a.get("href", "").startswith("/")
            and a.get("media", "all") == "all"
            and not any(k in a for k in ("integrity", "onload", "disabled"))):
        path = local_path(a["href"])
        if path.is_file():
            return a["href"], path
    return None


def bundle_group(group, page):
    if len(group) < 2:
        return group[0][0]
    parts = []
    for _, (_, path) in group:
        css = path.read_text(encoding="utf-8")
        if "@import" in css:
            raise ValueError(f"Resolve CSS imports before bundling {path}")
        # Existing URLs are root-relative, so moving the CSS preserves resolution.
        css = CHARSET.sub("", css)
        parts.append("/* " + path.name + " */\n" + css)
    content = "\n".join(parts) + "\n"
    url = "/assets/" + sha256(content.encode()).hexdigest()[:16] + "-styles.css"
    local_path(url).write_text(content, encoding="utf-8", newline="\n")
    report["stylesheets"].append({"page": page, "before": len(group), "after": 1,
                                  "bundle": url})
    return '<link rel="stylesheet" href="' + escape(url, quote=True) + '" media="all">'


def bundle_css(text, page):
    # Bundle only consecutive stylesheet links. Inline styles stay in their exact
    # position in the cascade, and every original rule stays in its original order.
    edits, group = [], []
    def flush():
        if group:
            edits.append((group[0][2], group[-1][3],
                          bundle_group([(tag, item) for tag, item, _, _ in group], page)))
            group.clear()
    for match in LINK.finditer(text):
        item = stylesheet(match[0])
        if not item:
            flush()
            continue
        if group and text[group[-1][3]:match.start()].strip():
            flush()
        group.append((match[0], item, match.start(), match.end()))
    flush()
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text


for path in sorted(ROOT.rglob("*.html")):
    text = bundle_css(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix())
    image_index = 0
    def loading(match):
        global image_index
        tag = match[0]
        a = attrs(tag)
        image_index += 1
        # First images are logo/hero. Native lazy loading only affects later images.
        if image_index > 2 and "loading" not in a:
            tag = tag[:-1].rstrip().removesuffix("/").rstrip() + ' loading="lazy">'
            report["lazy_images"] += 1
        if "decoding" not in a:
            tag = tag[:-1].rstrip().removesuffix("/").rstrip() + ' decoding="async">'
        return tag
    text = IMG.sub(loading, text)
    path.write_text(text, encoding="utf-8", newline="\n")


class AssetCheck(HTMLParser):
    def handle_starttag(self, tag, pairs):
        a = dict(pairs)
        for name in ("src", "href"):
            url = a.get(name, "")
            if url.startswith("/assets/") and not local_path(url).is_file():
                raise ValueError(f"Missing {tag} asset: {url}")
        if tag == "img":
            for candidate in a.get("srcset", "").split(","):
                url = candidate.strip().split(" ")[0]
                if url.startswith("/assets/") and not local_path(url).is_file():
                    raise ValueError(f"Missing srcset asset: {url}")


for path in sorted(ROOT.rglob("*.html")):
    AssetCheck().feed(path.read_text(encoding="utf-8"))
for path in ROOT.rglob("*.css"):
    for url in ASSET_URL.findall(path.read_text(encoding="utf-8")):
        if not local_path(url).is_file():
            raise ValueError(f"Missing CSS asset: {url}")
print(json.dumps(report, indent=2))
