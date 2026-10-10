"""Add small, accessible improvements to the existing static site after optimization."""
from hashlib import sha256
from html import escape, unescape
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import sys

from pypdf import PdfReader

CSS = r'''/* Use the site's existing colours, fonts and square edges. */
a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible {
  outline: 3px solid #80652d; outline-offset: 4px;
}
.skip-link:focus { position: fixed; left: 16px; top: 16px; width: auto; height: auto;
  clip: auto; clip-path: none; overflow: visible; z-index: 1000; padding: 12px 18px;
  background: #fff; color: #16163f; border: 2px solid #d3b574; }
.cg-home-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px; margin-top: 24px; }
.cg-home-actions a { display: inline-flex; align-items: center; justify-content: center;
  min-height: 50px; padding: 12px 22px; font: 500 15px/1.5 Montserrat, sans-serif;
  text-decoration: none; background: #d3b574; color: #16163f; border: 1px solid #d3b574; }
.cg-home-actions a:hover { background: #e3c789; color: #16163f; }
.cg-home-actions .cg-home-secondary { background: transparent; color: #fff; border-color: #fff; }
.cg-home-actions .cg-home-secondary:hover { background: #fff; color: #16163f; }
.cg-home-actions a:focus-visible { outline-color: #fff; }
.elementor-nav-menu--dropdown[aria-hidden="false"] { max-height: var(--menu-height, 75vh);
  overflow-y: auto; overscroll-behavior: contain; }
.cg-book .book-resource-search[hidden], .cg-book .book-resource[hidden],
.cg-book .book-resource-empty[hidden] { display: none; }
.cg-book .book-resource-search { margin: 0 0 24px; }
.cg-book .book-resource-search label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.cg-book .book-resource-search-row { display: flex; align-items: center; gap: 12px; }
.cg-book .book-resource-search input { width: 100%; max-width: 610px; min-width: 0;
  min-height: 48px; border: 1px solid #b5b0a4; border-radius: 0; padding: 11px 14px;
  font: inherit; font-size: 16px; color: var(--book-navy); background: #fff; }
.cg-book .book-resource-search input::placeholder { color: #666570; opacity: 1; }
.cg-book .book-resource-clear { min-height: 48px; padding: 10px 16px; border-radius: 0;
  border: 1px solid #b5b0a4; background: #fff; color: var(--book-navy); font: inherit;
  font-size: 14px; cursor: pointer; }
.cg-book .book-resource-clear:hover { border-color: var(--book-bronze); background: #f8f5ed; }
.cg-book .book-resource-clear:disabled { color: #666570; border-color: #ddd9ce; background: #f8f7f4; cursor: default; }
.cg-book .book-resource-search-status { display: flex; flex-wrap: wrap; gap: 8px 20px;
  margin-top: 9px; font-size: 12px; line-height: 1.7; color: #60606a; }
.cg-book .book-resource-help { margin: 0 0 18px; font-size: 13px; color: #60606a; }
.cg-book .book-resource-meta { font-size: 12px; color: #60606a; }
.cg-book .book-resource-empty { padding: 24px; margin: 0; background: #f8f7f4;
  border-left: 3px solid var(--book-gold); color: var(--book-navy); }
.cg-not-found { color: #211f40; font: 16px/1.8 Montserrat, sans-serif; }
.cg-not-found main { max-width: 760px; margin: 0 auto; padding: 70px 24px; }
.cg-not-found .cg-error-logo { display: flex; align-items: center; gap: 12px; color: #211f40;
  font: 700 23px/1.4 Merriweather, serif; text-decoration: none; margin-bottom: 60px; }
.cg-not-found .cg-error-logo img { width: 58px; height: auto; }
.cg-not-found h1 { font: 400 40px/1.4 Merriweather, serif; border-left: 4px solid #d3b574;
  padding-left: 22px; margin: 18px 0 24px; }
.cg-not-found .cg-error-code { color: #80652d; font-size: 13px; letter-spacing: 2px; }
.cg-not-found .cg-home-actions .cg-home-secondary { color: #16163f; border-color: #80652d; }
.cg-not-found .cg-home-actions { justify-content: flex-start; }
.cg-not-found .cg-home-actions a:focus-visible { outline-color: #80652d; }
@media (max-width: 767px) {
  .cg-home-actions a { width: 100%; }
  .cg-book .book-resource-search-row { align-items: stretch; }
  .cg-book .book-resource-clear { padding-inline: 12px; }
  .cg-not-found h1 { font-size: 30px; }
}
'''

JS = r'''(() => {
  'use strict';
  const search = document.querySelector('#appendix-search');
  if (search) {
    const controls = search.closest('.book-resource-search');
    const cards = [...document.querySelectorAll('.book-resource')];
    const status = document.querySelector('#appendix-search-status');
    const empty = document.querySelector('.book-resource-empty');
    const clear = document.querySelector('.book-resource-clear');
    const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const entries = cards.map(card => ({ card, text: normalize(card.textContent + ' ' + (card.dataset.keywords || '')) }));
    const filter = () => {
      const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
      let count = 0;
      entries.forEach(({card, text}) => {
        const matches = terms.every(term => text.includes(term));
        card.hidden = !matches;
        if (matches) count++;
      });
      status.textContent = `${count} of ${cards.length} appendices`;
      empty.hidden = count !== 0;
      clear.disabled = !search.value;
    };
    search.addEventListener('input', filter);
    search.addEventListener('keydown', event => {
      if (event.key === 'Escape' && search.value) { event.preventDefault(); search.value = ''; filter(); }
    });
    clear.addEventListener('click', () => { search.value = ''; filter(); search.focus(); });
    filter();
    controls.hidden = false;
  }
  // Keep the existing disclosure menu; add predictable keyboard movement.
  document.querySelectorAll('.elementor-menu-toggle').forEach(toggle => {
    const widget = toggle.closest('.elementor-widget-nav-menu');
    const dropdown = widget?.querySelector('nav.elementor-nav-menu--dropdown');
    if (!dropdown) return;
    const links = [...dropdown.querySelectorAll('a')];
    toggle.addEventListener('keydown', event => {
      if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
      event.preventDefault();
      if (toggle.getAttribute('aria-expanded') !== 'true') toggle.click();
      (event.key === 'ArrowUp' ? links[links.length - 1] : links[0])?.focus();
    });
    dropdown.addEventListener('keydown', event => {
      const index = links.indexOf(document.activeElement);
      if (index < 0 || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1 :
        (index + (event.key === 'ArrowDown' ? 1 : links.length - 1)) % links.length;
      links[next]?.focus();
    });
    widget.addEventListener('focusout', event => {
      if (event.relatedTarget && !widget.contains(event.relatedTarget) && toggle.getAttribute('aria-expanded') === 'true') toggle.click();
    });
  });
})();
'''

KEYWORDS = {
    'B': 'Alberta trades apprenticeship careers',
    'C': 'scholarships scholarship bursaries bursary foundations provinces',
    'D': 'banks banking credit unions institutions',
    'E': 'age province provinces majority adulthood',
    'F': 'funding chapter chapters sponsor sponsors',
    'G': 'private sector financial specialists planning',
    'H': 'financial literacy education resources learning',
    'I': 'low income families funding',
    'J': 'income tax taxes filing student students',
    'K': 'tax taxes advantages funding',
    'L': 'RESP RESPs savings education modelling modeling',
    'M': 'demographic demographics groups funding',
}

def version(text): return sha256(text.encode('utf-8')).hexdigest()[:12]

def improve(root):
    assets = root / 'assets'
    book = root / 'book/index.html'
    html = book.read_text(encoding='utf-8')
    card_pattern = re.compile(r'<a\b[^>]*class="book-resource"[^>]*>.*?</a>', re.S)
    cards = list(card_pattern.finditer(html))
    if len(cards) != 12:
        raise ValueError(f'Expected 12 working appendix cards, found {len(cards)}')
    metadata = []
    def enrich(match):
        card = match[0]
        code = re.search(r'Appendix ([B-M])', card)[1]
        href = unescape(re.search(r'href="([^"]+)"', card)[1])
        pdf = root / urlsplit(href).path.lstrip('/')
        if not pdf.exists() or pdf.parent != assets: raise ValueError(f'Missing PDF: {href}')
        pages = len(PdfReader(pdf).pages)
        size = round(pdf.stat().st_size / 1024)
        metadata.append({'appendix': code, 'href': href, 'pages': pages, 'bytes': pdf.stat().st_size})
        card = re.sub(r'\sdata-keywords="[^"]*"', '', card)
        card = card.replace('class="book-resource"', f'class="book-resource" data-keywords="{escape(KEYWORDS[code])}"', 1)
        card = re.sub(r'<span class="book-resource-meta">.*?</span>', '', card, flags=re.S)
        card = re.sub(r'<svg class="book-resource-arrow".*?</svg>', '', card, flags=re.S)
        suffix = f'<span class="book-resource-meta">PDF · {pages} {"page" if pages == 1 else "pages"} · {size} KB</span>'
        suffix += '<svg class="book-resource-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" focusable="false"><path d="M7 17 17 7M7 7h10v10"/></svg>'
        return card[:-4] + suffix + '</a>'
    html = card_pattern.sub(enrich, html)
    controls = '''<div class="book-resource-search" role="search" aria-label="Find an appendix" hidden>
      <label for="appendix-search">Find an appendix</label>
      <div class="book-resource-search-row"><input type="search" id="appendix-search" placeholder="Try scholarships, tax or RESP" autocomplete="off" spellcheck="false" aria-controls="appendix-grid" aria-describedby="appendix-search-status"><button type="button" class="book-resource-clear">Clear</button></div>
      <div class="book-resource-search-status"><span id="appendix-search-status" role="status" aria-live="polite" aria-atomic="true">12 of 12 appendices</span></div>
    </div><p class="book-resource-help">Select an appendix to open its PDF in a new tab.</p>'''
    if 'id="appendix-search"' not in html:
        html = html.replace('<div class="book-resources-grid">', controls + '<div class="book-resources-grid" id="appendix-grid">', 1)
        # The next section follows this grid; insert a no-results message just after it.
        last = html.rfind('</a>', 0, html.index('<section', html.index('id="appendix-grid"')))
        end = html.index('</div>', last)
        html = html[:end + 6] + '<p class="book-resource-empty" hidden>No matching appendices. Try a different topic or clear your search.</p>' + html[end + 6:]
    book.write_text(html, encoding='utf-8')

    home = root / 'index.html'
    html = home.read_text(encoding='utf-8')
    if 'class="cg-home-actions"' not in html:
        actions = '<div class="cg-home-actions"><a href="/book/">Explore the book</a><a class="cg-home-secondary" href="/book/#resources">Browse PDF appendices</a></div>'
        html, count = re.subn(r'(<h1\b[^>]*>.*?</h1>)', lambda m: m[1] + actions, html, count=1, flags=re.S)
        if count != 1: raise ValueError('Homepage heading not found')
    home.write_text(html, encoding='utf-8')

    (root / 'improvements.css').write_text(CSS, encoding='utf-8')
    (root / 'improvements.js').write_text(JS, encoding='utf-8')
    css_href = f'/improvements.css?v={version(CSS)}'
    js_src = f'/improvements.js?v={version(JS)}'
    pages_updated = 0
    for path in sorted(root.rglob('*.html')):
        html = path.read_text(encoding='utf-8')
        if 'http-equiv="refresh"' in html: continue
        html = re.sub(r'<link rel="stylesheet" href="/improvements\.css\?v=[^"]+">', '', html)
        html = re.sub(r'<script defer src="/improvements\.js\?v=[^"]+"></script>', '', html)
        html = html.replace('</head>', f'<link rel="stylesheet" href="{css_href}"></head>', 1)
        html = html.replace('</body>', f'<script defer src="{js_src}"></script></body>', 1)
        # Add resource access to both versions of the existing footer's site-links list.
        def footer_links(match):
            nav = match[0]
            if 'About the author' not in nav or 'cg-appendix-link' in nav: return nav
            item = '<li class="menu-item menu-item-type-custom cg-appendix-link"><a class="elementor-item" href="/book/#resources">PDF appendices</a></li>'
            return nav.replace('</ul>', item + '</ul>', 1)
        footer_start = html.find('data-elementor-type="footer"')
        if footer_start != -1:
            html = html[:footer_start] + re.sub(r'<nav\b[^>]*>.*?</nav>', footer_links, html[footer_start:], flags=re.S)
        path.write_text(html, encoding='utf-8')
        pages_updated += 1

    # Root-relative assets allow GitHub Pages to serve this for arbitrary missing paths.
    home_html = home.read_text(encoding='utf-8')
    styles = ''.join(re.findall(r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', home_html))
    icon = '/assets/98f6c8f1bf4fdbd4-grad_cap.webp'
    if not (root / icon.lstrip('/')).exists(): raise ValueError('Brand icon missing')
    error = f'''<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,follow"><title>Page not found | Canadian GRADS</title>{styles}</head><body class="cg-not-found"><main id="content"><a class="cg-error-logo" href="/"><img src="{icon}" width="58" height="42" alt="">Canadian GRADS</a><p class="cg-error-code">404 · PAGE NOT FOUND</p><h1>Let’s get you back on track.</h1><p>This address may have changed, or the page may no longer be available. Explore the guide or find the appendix you need below.</p><div class="cg-home-actions"><a href="/">Return to home</a><a class="cg-home-secondary" href="/book/#resources">Browse PDF appendices</a></div></main></body></html>'''
    (root / '404.html').write_text(error, encoding='utf-8')
    proof_paths = ['index.html', 'book/index.html', '404.html', 'improvements.css', 'improvements.js']
    report = {'pages_updated': pages_updated, 'appendices': metadata, 'css_bytes': len(CSS.encode('utf-8')), 'js_bytes': len(JS.encode('utf-8')), 'css_version': version(CSS), 'js_version': version(JS),
              'verification_hashes': {name: sha256((root / name).read_text(encoding='utf-8').encode('utf-8')).hexdigest() for name in proof_paths}}
    print(json.dumps(report, indent=2))
    return report

if __name__ == '__main__':
    improve(Path(sys.argv[1]).resolve())
