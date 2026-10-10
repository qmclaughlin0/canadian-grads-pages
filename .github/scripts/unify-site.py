"""Apply the homepage design system to the public site and reduce page assets.

Run after redesign-homepage.py. Original prose, book sections, PDF documents,
canonical URLs and retailer destinations are retained. No runtime framework.
"""
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit
from io import BytesIO
import importlib.util
import json
import re
import sys

from PIL import Image, ImageOps

spec = importlib.util.spec_from_file_location('homepage', Path(__file__).with_name('redesign-homepage.py'))
home = importlib.util.module_from_spec(spec)
spec.loader.exec_module(home)
Node, Parser = home.Node, home.Parser

SHARED_CLASSES = {'wrap','eyebrow','section','section-heading','text-link','arrow','button','button-outline','button-gold','skip-link','site-header','header-inner','brand','brand-name','brand-caption','site-nav','header-buy','menu-toggle','menu-icon','site-footer','footer-top','footer-brand','footer-links','footer-bottom'}


def css_rules(text):
    """Walk the known flat rules and media queries without breaking declarations."""
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    pos=0
    while pos<len(text):
        opening=text.find('{',pos)
        if opening<0:
            break
        depth=1
        closing=opening+1
        while depth:
            if text[closing]=='{': depth+=1
            elif text[closing]=='}': depth-=1
            closing+=1
        yield text[pos:opening].strip(),text[opening+1:closing-1]
        pos=closing


def split_css(text):
    shared, dedicated=[],[]
    for selector, body in css_rules(text):
        if selector.startswith('@media'):
            a,b=split_css(body)
            if a: shared.append(selector+'{'+a+'}')
            if b: dedicated.append(selector+'{'+b+'}')
        else:
            a,b=[],[]
            for item in selector.split(','):
                classes=set(re.findall(r'\.([a-zA-Z_-][\w-]*)',item))
                (a if not classes or classes<=SHARED_CLASSES|{'js','is-open'} else b).append(item)
            if a: shared.append(','.join(a)+'{'+body+'}')
            if b: dedicated.append(','.join(b)+'{'+body+'}')
    return '\n'.join(shared), '\n'.join(dedicated)


def minify_css(text):
    # Known authored CSS only; do not rewrite text content or URLs.
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    text=re.sub(r'\s+',' ',text).strip()
    text=re.sub(r'\s*([{};:,])\s*',r'\1',text)
    return text.replace(';}', '}')+'\n'


def component_css(text):
    """Keep each page's CSS download limited to the components it uses."""
    groups={name:[] for name in ('core','author','shop','journal','article','error','appendices','newsletter')}
    prefixes={
        'author':('author-page','author-contact','author-biography','bio-label','career-logos','contact-panel'),
        'shop':('shop-','retailer-','library-note'),
        'journal':('journal-',),
        'article':('article-','share-links','related-posts'),
        'error':('error-',),
        'appendices':('book-resource-',),
        'newsletter':('newsletter',)}
    for selector,body in css_rules(text):
        if selector.startswith('@media'):
            nested=component_css(body)
            for key,part in nested.items():
                if part: groups[key].append(selector+'{'+part+'}')
        else:
            selections={key:[] for key in groups}
            for item in selector.split(','):
                classes=re.findall(r'\.([a-zA-Z_-][\w-]*)',item)
                group=next((key for key,starts in prefixes.items() if any(c.startswith(starts) for c in classes)),'core')
                selections[group].append(item)
            for key,items in selections.items():
                if items: groups[key].append(','.join(items)+'{'+body+'}')
    return {key:'\n'.join(parts) for key,parts in groups.items()}


EXTRA_CSS=r'''
.site-nav a[aria-current=page]{color:var(--bronze);text-decoration:underline;text-decoration-color:var(--gold);text-underline-offset:7px}
.page-hero{background:var(--ivory);border-bottom:1px solid var(--line);padding:52px 0 58px}
.breadcrumbs{display:flex;flex-wrap:wrap;align-items:center;gap:9px;font-size:10px;color:var(--muted);margin-bottom:24px}
.breadcrumbs a{text-decoration:none;min-height:28px;display:inline-flex;align-items:center}
.breadcrumbs a:hover{color:var(--bronze)}
.page-hero .eyebrow{margin-bottom:14px}
.page-hero h1{font-size:clamp(34px,4vw,48px);max-width:950px;margin-bottom:20px}
.page-lede{font-size:15px;line-height:1.85;color:var(--muted);max-width:690px}
.page-hero .page-lede:last-child{margin-bottom:0}
.prose{font-size:15px;line-height:1.95;color:var(--muted);overflow-wrap:break-word}
.prose p,.prose ul,.prose ol,.prose blockquote{margin-bottom:24px}
.prose h2{font-size:29px;margin:40px 0 20px}
.prose h3{font-size:19px;margin:30px 0 15px}
.prose strong,.prose b{color:var(--navy);font-weight:600}
.prose a{color:var(--navy);text-decoration-color:var(--gold)}
.prose ul,.prose ol{padding-left:24px}
.prose li{margin-bottom:13px;padding-left:5px}
.prose li::marker{color:var(--bronze)}
.prose blockquote{border-left:2px solid var(--gold);padding:10px 0 10px 25px;font-family:Merriweather,Georgia,serif;color:var(--navy)}
.prose table{border-collapse:collapse;width:100%;font-size:13px;margin:24px 0}
.prose td,.prose th{padding:12px 16px;border:1px solid var(--line);text-align:left}
.prose th{background:var(--ivory);color:var(--navy)}
.table-scroll{overflow-x:auto;max-width:100%}
.table-scroll table{min-width:480px}
.page-body{padding:64px 0 72px}
.body-narrow{max-width:780px;margin-inline:auto}
.book-callout{background:var(--navy);padding:41px 0;color:#d4d4df}
.book-callout .wrap{display:flex;align-items:center;justify-content:space-between;gap:40px}
.book-callout h2{color:#fff;font-size:27px;margin-bottom:12px}
.book-callout p{font-size:12px}
.book-callout .button{white-space:nowrap}
.book-callout a:focus-visible{outline-color:var(--gold)}
.author-page-grid{display:grid;grid-template-columns:1.4fr .8fr;align-items:center;gap:80px}
.author-page-grid .author-page-photo{width:290px;height:340px;object-fit:cover;object-position:50% 29%;box-shadow:16px 16px 0 #e1d9c5;margin:0 auto}
.author-page-quote{font-family:Merriweather,Georgia,serif;color:var(--navy);font-size:18px;line-height:1.8;max-width:610px;margin:24px 0}
.author-contact{display:flex;flex-wrap:wrap;gap:20px;font-size:12px;margin-top:24px}
.author-biography{display:grid;grid-template-columns:240px minmax(0,1fr);gap:70px}
.author-biography .bio-label{position:sticky;top:115px;align-self:start}
.author-biography .bio-label h2{font-size:30px;margin-top:12px}
.career-logos{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;align-items:center;margin:28px 0 40px;padding-block:22px;border-block:1px solid var(--line)}
.career-logos img{max-height:70px;width:100%;object-fit:contain;mix-blend-mode:multiply}
.contact-panel{margin-top:36px;padding:24px 27px;background:var(--ivory);border-left:2px solid var(--gold)}
.contact-panel p:last-child{margin-bottom:0}
.shop-hero{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:70px;align-items:center}
.shop-hero .shop-cover{width:200px;margin:auto;transform:rotate(-3deg);box-shadow:9px 12px 20px #181a362b}
.shop-hero .hero-actions{margin-top:24px;display:flex;gap:15px;flex-wrap:wrap}
.shop-hero .hero-actions .button{font-size:12px}
.retailer-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:23px}
.retailer-card{padding:25px;border:1px solid var(--line);display:flex;flex-direction:column;background:var(--ivory)}
.retailer-card h2{font-size:24px;margin:12px 0 15px}
.retailer-card p{font-size:12px;color:var(--muted);margin:0 0 24px;flex:1}
.retailer-card .button{font-size:12px;padding-inline:15px;align-self:stretch}
.shop-note{margin-top:26px;font-size:11px;color:var(--muted)}
.library-note{margin-top:42px;border-top:1px solid var(--line);padding-top:28px;max-width:760px}
.library-note h2{font-size:27px;margin-bottom:17px}
.library-note p{font-size:13px;color:var(--muted)}
.journal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:33px}
.journal-card{border-top:2px solid var(--navy);padding-top:20px}
.journal-image{aspect-ratio:3/2;width:100%;object-fit:cover;background:var(--ivory)}
.journal-card time{display:block;font-size:10px;color:var(--bronze);margin:21px 0 13px;text-transform:uppercase;letter-spacing:.08em}
.journal-card h2{font-size:24px;line-height:1.55;letter-spacing:-.025em;margin-bottom:18px}
.journal-card h2 a{text-decoration:none}
.journal-card h2 a:hover{color:var(--bronze)}
.journal-card .text-link{font-size:12px}
.article-hero h1{max-width:940px;font-size:clamp(32px,3.7vw,46px)}
.article-meta{display:flex;gap:13px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin-top:25px}
.article-meta a{color:var(--navy);text-decoration:none;font-weight:500}
.article-layout{display:grid;grid-template-columns:minmax(0,740px) 250px;gap:80px;align-items:start;justify-content:space-between}
.article-offer{position:sticky;top:113px;background:var(--ivory);border-top:2px solid var(--gold);padding:25px 21px;text-align:center}
.article-offer img{width:112px;margin:0 auto 22px;box-shadow:5px 7px 10px #181a3620}
.article-offer h2{font-size:21px;margin-bottom:15px}
.article-offer p{font-size:11px;color:var(--muted);margin-bottom:20px}
.article-offer .button{font-size:11px;padding-inline:15px;width:100%;min-height:48px}
.share-links{display:flex;align-items:center;flex-wrap:wrap;gap:9px 20px;margin-top:34px;padding-block:22px;border-block:1px solid var(--line);font-size:11px}
.share-links strong{font-weight:600;color:var(--navy);margin-right:8px}
.share-links a{min-height:35px;display:flex;align-items:center;text-decoration:none;color:var(--muted)}
.share-links a:hover{color:var(--bronze)}
.related-posts{margin-top:52px;border-top:1px solid var(--line);padding-top:28px}
.related-posts h2{font-size:27px;margin-bottom:24px}
.related-posts ul{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:1fr 1fr;gap:22px}
.related-posts a{font-family:Merriweather,Georgia,serif;font-size:17px;line-height:1.8;text-decoration:none;display:block;padding-top:12px;border-top:1px solid var(--gold)}
.related-posts a:hover{color:var(--bronze)}
.policy-body{min-height:220px}
.error-page{padding:90px 0;min-height:470px;background:var(--ivory)}
.error-page .eyebrow{margin-bottom:18px}
.error-page h1{font-size:clamp(33px,4vw,48px);margin-bottom:24px}
.error-page p:not(.eyebrow){max-width:620px;color:var(--muted);font-size:14px}
.error-actions{display:flex;gap:15px;flex-wrap:wrap;margin-top:28px}
.book-resource-search[hidden],.book-resource[hidden],.book-resource-empty[hidden]{display:none}
.book-resource-search{margin-bottom:24px}
.book-resource-search label{display:block;font-size:12px;font-weight:600;margin-bottom:8px}
.book-resource-search-row{display:flex;gap:12px;align-items:center}
.book-resource-search input{min-width:0;width:100%;max-width:610px;min-height:48px;background:#fff;border:1px solid #b5b0a4;border-radius:3px;padding:11px 14px;font:inherit;font-size:16px;color:var(--navy)}
.book-resource-search input:focus-visible{outline:3px solid var(--bronze);outline-offset:3px}
.book-resource-clear{min-height:48px;min-width:67px;padding:10px 16px;border-radius:3px;border:1px solid #b5b0a4;background:#fff;color:var(--navy);font:inherit;font-size:12px;cursor:pointer}
.book-resource-clear:disabled{color:var(--muted);border-color:var(--line);cursor:default}
.book-resource-search-status{margin-top:10px;font-size:11px;color:var(--muted)}
.book-resource-help{font-size:12px;color:var(--muted);margin-bottom:18px}
.book-resource-empty{font-size:13px;background:var(--ivory);padding:18px 22px}
.site-footer .contact-phone{display:inline-flex;align-items:center;min-height:32px;margin-top:4px;font-size:11px}
@media(max-width:1080px){.author-page-grid{gap:45px}.author-biography{gap:40px;grid-template-columns:200px 1fr}.article-layout{gap:35px;grid-template-columns:minmax(0,1fr) 230px}.retailer-grid{gap:18px}.retailer-card{padding:24px 19px}.shop-hero{gap:40px}.journal-grid{gap:25px}.journal-card h2{font-size:21px}}
@media(max-width:860px){.page-hero{padding:36px 0 44px}.page-hero h1{font-size:38px}.author-page-grid{grid-template-columns:1.35fr .8fr;gap:35px}.author-page-grid .author-page-photo{width:230px;height:285px}.author-page-quote{font-size:16px}.author-biography{grid-template-columns:1fr;gap:30px}.author-biography .bio-label{position:static}.author-biography .bio-label h2{font-size:29px}.retailer-grid{grid-template-columns:1fr 1fr}.journal-grid{gap:22px}.journal-card h2{font-size:19px}.article-layout{grid-template-columns:1fr;gap:38px}.article-offer{position:static;display:grid;grid-template-columns:110px 1fr;gap:22px;text-align:left;align-items:center}.article-offer img{width:95px;margin:0}.article-offer p{margin-bottom:14px}.article-offer .button{width:auto}.article-hero h1{font-size:37px}.book-callout h2{font-size:24px}.shop-hero{grid-template-columns:1fr 190px;gap:35px}.shop-hero .shop-cover{width:170px}.page-body{padding-block:46px}}
@media(max-width:600px){.page-hero{padding:28px 0 36px}.breadcrumbs{font-size:9px;margin-bottom:17px}.page-hero h1{font-size:32px;line-height:1.3;margin-bottom:17px}.page-lede{font-size:13px}.page-body{padding:37px 0 45px}.prose{font-size:14px;line-height:1.95}.prose p,.prose ul,.prose ol{margin-bottom:21px}.prose li{padding-left:2px}.prose ul,.prose ol{padding-left:20px}.prose h2{font-size:25px}.book-callout{padding:31px 0}.book-callout .wrap{display:block}.book-callout h2{font-size:25px}.book-callout p{font-size:11px;margin-bottom:23px}.book-callout .button{font-size:12px}.author-page-grid{display:flex;flex-direction:column;align-items:stretch;gap:29px}.author-page-grid .author-page-photo{width:228px;height:260px;margin:4px auto 16px}.author-page-quote{font-size:15px;margin-block:21px}.author-contact{gap:16px;font-size:11px;margin-top:16px}.author-biography{gap:25px}.career-logos{gap:20px;grid-template-columns:1fr 1fr;margin:20px 0 30px}.career-logos img{max-height:63px}.contact-panel{padding:21px;font-size:13px}.shop-hero{grid-template-columns:1fr;gap:28px}.shop-hero .shop-cover{width:160px}.shop-hero .hero-actions .button{min-height:47px;font-size:11px;padding-inline:16px}.retailer-grid{grid-template-columns:1fr;gap:17px}.retailer-card{padding:25px}.retailer-card h2{font-size:25px;margin-block:10px 13px}.library-note{margin-top:32px;padding-top:24px}.library-note h2{font-size:25px}.library-note p{font-size:12px}.journal-grid{grid-template-columns:1fr;gap:35px}.journal-card h2{font-size:25px}.journal-card time{margin:17px 0 12px}.journal-card .text-link{font-size:12px}.article-hero h1{font-size:30px}.article-meta{font-size:10px;gap:9px;margin-top:20px}.article-offer{grid-template-columns:90px 1fr;gap:17px;padding:22px 18px}.article-offer img{width:83px}.article-offer h2{font-size:20px;margin-bottom:13px}.article-offer p{font-size:10px}.article-offer .button{font-size:10px;min-height:46px}.share-links{gap:8px 17px}.share-links strong{width:100%}.share-links a{min-height:40px}.related-posts{margin-top:35px}.related-posts h2{font-size:25px}.related-posts ul{grid-template-columns:1fr;gap:20px}.related-posts a{font-size:17px}.error-page{padding:54px 0;min-height:450px}.error-page h1{font-size:32px}.error-actions .button{font-size:12px}.policy-body{min-height:175px}}
'''

BOOK_OVERRIDES=r'''
.cg-book{--book-navy:var(--navy);--book-deep:var(--navy);--book-gold:var(--gold);--book-bronze:var(--bronze);font-size:15px}
.cg-book .book-container{width:min(var(--width),calc(100% - 80px))}
.cg-book h1{font-size:clamp(35px,3.8vw,48px);line-height:1.3;letter-spacing:-.035em}
.cg-book h2{padding-left:0;border:0;line-height:1.3;font-weight:400;letter-spacing:-.035em}
.cg-book h3{font-family:Montserrat,Arial,sans-serif;font-size:18px;font-weight:600;letter-spacing:0}
.cg-book .book-hero{background:var(--ivory);color:var(--navy);border-bottom:1px solid var(--line)}
.cg-book .book-hero-grid{grid-template-columns:1.35fr .9fr;gap:85px;min-height:535px;padding-block:52px}
.cg-book .book-hero .book-eyebrow{color:var(--bronze);font-size:11px;letter-spacing:.14em}
.cg-book .book-hero-copy>p:not(.book-eyebrow):not(.book-byline){color:var(--muted);font-size:15px;max-width:550px}
.cg-book .book-byline{color:var(--muted);font-size:12px}
.cg-book .book-cover{position:relative;margin:0;padding:22px}
.cg-book .book-cover::before{content:"";position:absolute;inset:0 -12px -5px;background:#e9e5d8;border-radius:48% 48% 8px 8px}
.cg-book .book-cover img{position:relative;width:280px;transform:rotate(-3deg);box-shadow:4px 3px 0 #c8c5be,8px 5px 0 #f6f4ef,12px 18px 25px #181a362e}
.cg-book .book-cover figcaption{position:relative;color:var(--muted);font-size:10px;margin-top:20px}
.cg-book .book-button{background:var(--navy);color:#fff;border-color:var(--navy);border-radius:3px;min-height:52px;font-size:13px;font-weight:600;padding:14px 21px}
.cg-book .book-button:hover{background:#303353;color:#fff;border-color:#303353}
.cg-book .book-button-ghost{background:transparent;color:var(--navy);border-color:#bab9c2}
.cg-book .book-button-ghost:hover{background:#eeebe2;color:var(--navy);border-color:var(--navy)}
.cg-book .book-eyebrow{font-size:11px;letter-spacing:.14em;font-weight:700}
.cg-book .book-jump-nav a{font-size:12px;min-height:35px;display:inline-flex;align-items:center}
.cg-book .book-section{padding-block:67px}
.cg-book .book-section-lead{font-size:14px;color:var(--muted)}
.cg-book .book-stats{border-color:var(--line)}
.cg-book .book-stat strong{font-size:32px;font-weight:400}
.cg-book .book-chapters li{font-size:13px;padding-block:17px}
.cg-book .book-sample-section,.cg-book .book-purchase-section{background:var(--ivory);border-color:var(--line)}
.cg-book .book-sample-note{font-size:12px}
.cg-book .book-source-title{font-size:24px}
.cg-book details>summary{font-size:13px;min-height:62px;padding:18px 22px}
.cg-book .book-detail-body{font-size:13px;line-height:1.9}
.cg-book .book-detail-body p{margin-bottom:16px}
.cg-book .book-toolkit-section h2{color:#fff}
.cg-book .book-tools li{font-size:13px}
.cg-book .book-resource{background:var(--ivory);border-color:var(--line);border-radius:3px;min-height:148px}
.cg-book .book-resource-name{font-size:14px;font-weight:500}
.cg-book .book-resource-code{font-size:10px;letter-spacing:.12em}
.cg-book .book-resource-meta{font-size:10px}
.cg-book .book-purchase-image{border:0;background:transparent;padding:0}
.cg-book .book-edition h3{font-family:Merriweather,Georgia,serif;font-size:24px;font-weight:400;letter-spacing:-.025em}
.cg-book .book-edition p{font-size:12px}
.cg-book .book-edition .book-button{font-size:12px}
.cg-book .book-resource-search input{font-family:Montserrat,Arial,sans-serif}
@media(max-width:1080px){.cg-book .book-container{width:calc(100% - 56px)}.cg-book .book-hero-grid{gap:45px;grid-template-columns:1.2fr .9fr}.cg-book .book-cover img{width:245px}}
@media(max-width:860px){.cg-book .book-container{width:calc(100% - 44px)}.cg-book .book-hero-grid{gap:40px}.cg-book .book-cover img{width:225px}.cg-book .book-cover{padding:15px}.cg-book .book-hero-grid{min-height:500px}.cg-book h1{font-size:36px}.cg-book .book-hero-copy>p:not(.book-eyebrow):not(.book-byline){font-size:13px}.cg-book .book-button{font-size:12px;padding-inline:17px}.cg-book .book-byline{font-size:11px}}
@media(max-width:767px){.cg-book .book-container{width:calc(100% - 40px)}.cg-book .book-hero-grid{grid-template-columns:1fr;gap:29px;padding-block:33px}.cg-book h1{font-size:33px}.cg-book h2{font-size:29px}.cg-book .book-cover{max-width:300px;width:100%;margin:0 auto}.cg-book .book-cover img{width:210px}.cg-book .book-actions .book-button{width:auto;flex:1;font-size:11px;padding-inline:12px}.cg-book .book-section{padding-block:47px}.cg-book .book-jump-nav a{font-size:11px}.cg-book .book-stat strong{font-size:28px}.cg-book .book-stat span{font-size:10px}.cg-book .book-section-lead{font-size:13px}.cg-book .book-source-title{font-size:22px}.cg-book .book-tools li{font-size:12px}.cg-book .book-resource-name{font-size:13px}.cg-book .book-detail-body{padding:0 20px 20px}.cg-book .book-extra ul{font-size:12px}.cg-book .book-editions .book-button{width:100%}}
'''


def attr_html(attrs):
    return ''.join(' '+k+(f'="{escape(str(v),quote=True)}"' if v is not None else '') for k,v in attrs.items())


def render(node, keep_classes=False):
    if isinstance(node,str):
        return escape(node,quote=False)
    if node.tag in {'script','style','noscript'}:
        return ''
    children=''.join(render(child,keep_classes) for child in node.children)
    allowed={'p','ul','ol','li','b','strong','em','i','a','br','hr','h1','h2','h3','h4','h5','h6','blockquote','figure','figcaption','img','table','thead','tbody','tr','th','td','caption','sup','sub','details','summary','input','button','label','svg','path','span','section','nav','main','div'}
    if node.tag not in allowed or (not keep_classes and node.tag in {'div','span','section'}):
        return children
    attrs={k:v for k,v in node.attrs.items() if k in {'id','href','src','srcset','sizes','alt','width','height','loading','decoding','fetchpriority','target','rel','role','type','for','placeholder','autocomplete','spellcheck','hidden','disabled','open','tabindex','colspan','rowspan','scope','viewbox','viewBox','d','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','focusable'} or k.startswith('aria-') or k=='data-keywords' or (keep_classes and k=='class')}
    if attrs.get('class'):
        attrs['class']=' '.join('sr-only' if c=='elementor-screen-only' else c for c in attrs['class'].split() if c=='elementor-screen-only' or not c.startswith(('elementor','wp-','e-')))
        if not attrs['class']: del attrs['class']
    if node.tag=='a' and attrs.get('target')=='_blank':
        attrs['rel']='noopener noreferrer'
    if node.tag=='svg' and 'viewbox' in attrs:
        attrs['viewBox']=attrs.pop('viewbox')
    if node.tag=='img':
        attrs.setdefault('alt','')
        attrs['decoding']='async'
    if node.tag in home.VOID:
        return '<'+node.tag+attr_html(attrs)+'>'
    result='<'+node.tag+attr_html(attrs)+'>'+children+'</'+node.tag+'>'
    if node.tag=='table' and not keep_classes:
        result='<div class="table-scroll" tabindex="0" role="region" aria-label="Article table">'+result+'</div>'
    return result


def find_class(node, cls, tags={'div'}):
    return [n for n in node.find(tags) if cls in n.attrs.get('class','').split()]


def image_variants(root, source, label, widths, quality=88, lossless=False):
    path=root/source.lstrip('/')
    out=[]
    with Image.open(path) as img:
        original=ImageOps.exif_transpose(img)
        original=original.convert('RGBA' if 'A' in original.getbands() else 'RGB')
        for width in sorted(set(min(w,original.width) for w in widths)):
            height=round(original.height*width/original.width)
            resized=original.resize((width,height),Image.Resampling.LANCZOS)
            buffer=BytesIO()
            resized.save(buffer,format='WEBP',quality=quality,method=6,lossless=lossless,exact=True)
            data=buffer.getvalue()
            # Retain an already-efficient original when recompression adds bytes.
            if width>=original.width*.9 and len(data)>=path.stat().st_size:
                out.append({'src':source,'width':original.width,'height':original.height,'bytes':path.stat().st_size})
            else:
                filename=f'{label}-{width}-{sha256(data).hexdigest()[:12]}.webp'
                (root/'assets'/filename).write_bytes(data)
                out.append({'src':'/assets/'+filename,'width':width,'height':height,'bytes':len(data)})
    return out


def responsive_image(items, alt, classes='', sizes='(max-width:600px) 70vw, 320px', eager=False):
    largest=items[-1]
    attrs={'src':largest['src'],'width':largest['width'],'height':largest['height'],'alt':alt,'decoding':'async','srcset':', '.join(f"{i['src']} {i['width']}w" for i in items),'sizes':sizes}
    if classes: attrs['class']=classes
    if eager: attrs['fetchpriority']='high'
    else: attrs['loading']='lazy'
    return '<img'+attr_html(attrs)+'>'


def breadcrumb(label, blog=False):
    return '<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span>'+('<a href="/blog/">Blog</a><span aria-hidden="true">/</span>' if blog else '')+f'<span>{escape(label)}</span></nav>'


def page_hero(title,label,lede='',extra='',classes=''):
    return f'<section class="page-hero {classes}"><div class="wrap">{breadcrumb(label)}<p class="eyebrow">Canadian GRADS</p><h1>{escape(title)}</h1>'+ (f'<p class="page-lede">{escape(lede)}</p>' if lede else '')+extra+'</div></section>'


def callout():
    return f'<section class="book-callout" aria-label="Explore the guide"><div class="wrap"><div><h2>More ways to fund your next chapter.</h2><p>Explore 85 Canadian funding sources with Canadians’ Education Funding Guide.</p></div><a class="button button-gold" href="/book/">Explore the book {home.ARROW}</a></div></section>'


def author_page(dom,images):
    main=next(dom.find({'main'}))
    paragraphs=list(main.find({'p'}))
    biography=[p for p in paragraphs if len(p.text())>100 and not p.text().startswith('To book John')]
    if len(biography)!=6:
        raise ValueError('Expected the six original biography paragraphs')
    original_quote=next(main.find({'h2'})).text()
    hero=f'''<section class="page-hero"><div class="wrap">{breadcrumb('The author')}<div class="author-page-grid"><div><p class="eyebrow">Meet the author</p><h1>John F. McLaughlin</h1><p class="page-lede">Author of <em>Canadians’ Education Funding Guide</em></p><blockquote class="author-page-quote">{escape(original_quote)}</blockquote><div class="author-contact"><a class="text-link" href="https://www.linkedin.com/in/johnfrederickmclaughlin/">Connect on LinkedIn {home.ARROW}</a><a class="text-link" href="mailto:john@canadiangrads.ca">Email John {home.ARROW}</a></div></div>{responsive_image(images['portrait'],'John F. McLaughlin','author-page-photo','(max-width:600px) 228px, (max-width:860px) 230px, 290px',True)}</div></div></section>'''
    logos=''.join(responsive_image(i,alt,sizes='(max-width:600px) 140px, 130px') for alt,i in images['logos'])
    text=''.join(render(p) for p in biography)
    workshop=next(p for p in paragraphs if p.text().startswith('To book John'))
    body=f'<section class="page-body"><div class="wrap author-biography"><div class="bio-label"><p class="eyebrow">His story</p><h2>Education.<br>Experience.<br>Purpose.</h2></div><div class="prose">{text}<div class="career-logos" aria-label="Organizations from John’s career">{logos}</div><div class="contact-panel">{render(workshop)}</div></div></div></section>'
    return '<main id="content" tabindex="-1">'+hero+body+callout()+'</main>'


def purchase_page(dom,images,newsletter):
    main=next(dom.find({'main'}))
    links=[n.attrs['href'] for n in main.find({'a'}) if 'elementor-cta__button' in n.attrs.get('class','')]
    labels=[n.text() for n in main.find({'h2'}) if 'elementor-cta__title' in n.attrs.get('class','')]
    if labels!=['Amazon','Amazon Kindle','Indigo','Barnes & Noble','Rakuten Kobo'] or len(links)!=5:
        raise ValueError('Expected all five original retailers')
    formats=['Print edition','Digital edition','Digital edition','Print & digital editions','Digital edition']
    descriptions=['Browse print formats and current pricing on Amazon Canada.','Explore the Kindle edition and current device options.','View the guide and current pricing on Indigo.','Explore formats and current pricing on Barnes & Noble.','Explore the ebook and current pricing on Rakuten Kobo.']
    hero=f'<section class="page-hero"><div class="wrap">{breadcrumb("Purchase")}<div class="shop-hero"><div><p class="eyebrow">Choose your next chapter</p><h1>Get the guide.<br>Start your plan.</h1><p class="page-lede">Find Canadians’ Education Funding Guide at your preferred retailer. Choose a print or digital edition that works for you.</p><div class="hero-actions"><a class="button" href="{escape(links[0],quote=True)}">Buy print on Amazon {home.ARROW}</a><a class="button button-outline" href="{escape(links[1],quote=True)}">View Kindle edition {home.ARROW}</a></div></div>{responsive_image(images["cover"],"Canadians’ Education Funding Guide, First Edition","shop-cover","(max-width:600px) 160px, 200px",True)}</div></div></section>'
    cards=''.join(f'<article class="retailer-card"><p class="eyebrow">{fmt}</p><h2>{escape(label)}</h2><p>{description}</p><a class="button {"button-outline" if i else ""}" href="{escape(url,quote=True)}">View on {escape(label)} {home.ARROW}</a></article>' for i,(label,url,fmt,description) in enumerate(zip(labels,links,formats,descriptions)))
    body=f'<section class="page-body"><div class="wrap"><div class="retailer-grid">{cards}</div><p class="shop-note">Retailers set their own prices and availability. Follow a retailer link for current details.</p><div class="library-note"><p class="eyebrow">Prefer to borrow?</p><h2>Ask your library for the guide.</h2><p>Request <em>Canadians’ Education Funding Guide</em> by John F. McLaughlin.<br>ISBN 13: <strong>9781834387697</strong></p></div></div></section>'
    return '<main id="content" tabindex="-1">'+hero+body+newsletter+'</main>'


def blog_posts(dom):
    posts=[]
    for node in dom.find({'article'}):
        title=next(node.find({'h3'}))
        anchor=next(title.find({'a'}))
        date=next(n for n in node.find({'span'}) if 'elementor-post-date' in n.attrs.get('class',''))
        posts.append({'title':title.text(),'url':anchor.attrs['href'],'date':date.text(),'image':next(node.find({'img'})).attrs['src']})
    if len(posts)!=3: raise ValueError('Expected the three existing blog articles')
    return posts


def blog_page(posts,images):
    cards=[]
    for index,post in enumerate(posts):
        img=responsive_image(images['blog'][index],'','journal-image','(max-width:600px) calc(100vw - 40px), (max-width:1080px) 30vw, 365px',index==0)
        dt='/'.join(post['url'].strip('/').split('/')[:3]).replace('/','-')
        url=escape(post['url'],quote=True)
        cards.append(f'<article class="journal-card"><a href="{url}" aria-label="{escape(post["title"],quote=True)}" tabindex="-1">{img}</a><time datetime="{dt}">{escape(post["date"])}</time><h2><a href="{url}">{escape(post["title"])}</a></h2><a class="text-link" href="{url}" aria-label="Read {escape(post["title"],quote=True)}">Read the article {home.ARROW}</a></article>')
    return '<main id="content" tabindex="-1">'+page_hero('Ideas for your education funding journey.','Blog','Notes from John on planning, saving and exploring Canadian education funding options.')+'<section class="page-body"><div class="wrap journal-grid">'+''.join(cards)+'</div></section>'+callout()+'</main>'


def article_page(dom,post,posts,images):
    containers=find_class(dom,'elementor-widget-theme-post-content')
    if len(containers)!=1: raise ValueError('Expected one original article content container')
    prose=render(containers[0])
    canonical='https://canadiangrads.shop'+post['url']
    url=quote(canonical,safe='')
    title=quote(post['title'],safe='')
    dt='/'.join(post['url'].strip('/').split('/')[:3]).replace('/','-')
    hero=f'<section class="page-hero article-hero"><div class="wrap">{breadcrumb("Article",True)}<p class="eyebrow">From the Canadian GRADS blog</p><h1>{escape(post["title"])}</h1><div class="article-meta"><time datetime="{dt}">{escape(post["date"])}</time><span aria-hidden="true">·</span><a href="/author/">John F. McLaughlin</a></div></div></section>'
    share=f'<nav class="share-links" aria-label="Share this article"><strong>Share this article</strong><a href="https://www.facebook.com/sharer/sharer.php?u={url}" target="_blank" rel="noopener noreferrer">Facebook</a><a href="https://www.linkedin.com/sharing/share-offsite/?url={url}" target="_blank" rel="noopener noreferrer">LinkedIn</a><a href="https://twitter.com/intent/tweet?url={url}&amp;text={title}" target="_blank" rel="noopener noreferrer">X</a><a href="mailto:?subject={title}&amp;body={url}">Email</a></nav>'
    related='<section class="related-posts" aria-label="More articles"><h2>Keep exploring.</h2><ul>'+''.join(f'<li><a href="{escape(p["url"],quote=True)}">{escape(p["title"])}</a></li>' for p in posts if p['url']!=post['url'])+'</ul></section>'
    offer=f'<aside class="article-offer" aria-label="About the book">{responsive_image(images["cover"],"Canadians’ Education Funding Guide",sizes="(max-width:600px) 83px, 112px")}<div><h2>A clearer path to funding education.</h2><p>Explore 85 funding sources and 20 practical planning tools.</p><a class="button" href="/book/">Explore the guide {home.ARROW}</a></div></aside>'
    return '<main id="content" tabindex="-1">'+hero+'<div class="page-body wrap article-layout"><article><div class="prose">'+prose+'</div>'+share+related+'</article>'+offer+'</div>'+callout()+'</main>'


def legal_page(dom):
    main=next(dom.find({'main'}))
    title=next(main.find({'h1'})).text()
    # The original public export has headings but no authored policy paragraphs.
    # Preserve any supplied copy and do not invent legal terms.
    blocks=[n for n in main.find({'p','ul','ol'}) if n.text()]
    body=''.join(render(n) for n in blocks)
    if not body:
        body='<p>For questions about this site, contact <a href="mailto:john@canadiangrads.ca">john@canadiangrads.ca</a>.</p>'
    return '<main id="content" tabindex="-1">'+page_hero(title,title)+'<section class="page-body policy-body"><div class="wrap body-narrow prose">'+body+'</div></section></main>'


def error_page():
    return f'<main id="content" tabindex="-1"><section class="error-page"><div class="wrap"><p class="eyebrow">404 · Page not found</p><h1>Let’s get you back on track.</h1><p>This address may have changed, or the page may no longer be available. Explore the guide or find the appendix you need below.</p><div class="error-actions"><a class="button" href="/">Return to home {home.ARROW}</a><a class="button button-outline" href="/book/#resources">Browse PDF appendices {home.ARROW}</a></div></div></section></main>'


def replace_images(html,images):
    def change(match):
        node=next(Parser(match[0]).root.find({'img'}))
        source=node.attrs.get('src','')
        if 'coverdraft-CanadiansEducationFundingGuide' in source:
            items=images['cover']
            sizes='(max-width:600px) 222px, (max-width:860px) 245px, 322px' if 'book-cover' in node.attrs.get('class','') else '(max-width:767px) 210px, 280px'
        elif 'IMG_3171' in source:
            items=images['portrait'];sizes='(max-width:600px) 274px, 324px'
        elif 'grad_cap.webp' in source:
            items=images['cap'];sizes='50px'
        elif 'canadianseducationfundingguide-book' in source:
            items=images['mockup'];sizes='(max-width:767px) 300px, 340px'
        else: return match[0]
        result=responsive_image(items,node.attrs.get('alt',''),node.attrs.get('class',''),sizes,node.attrs.get('fetchpriority')=='high')
        # The small shared logo is already in the first viewport.
        if items is images['cap']:
            result=result.replace(' loading="lazy"','')
        return result
    return re.sub(r'<img\b[^>]*>',change,html)


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'public').resolve()
    original_home=(root/'index.html').read_text(encoding='utf-8')
    if 'class="wrap hero-grid"' not in original_home:
        raise ValueError('Run redesign-homepage.py before unifying the site')
    sources={p:p.read_text(encoding='utf-8') for p in root.rglob('*.html')}
    images={
        'cover':image_variants(root,home.COVER,'guide-cover',(360,720),88),
        'portrait':image_variants(root,home.PORTRAIT,'john-mclaughlin',(384,768),86),
        'cap':image_variants(root,home.CAP,'grads-cap',(160,),100,True),
        'mockup':image_variants(root,'/assets/dfa110b49a34b6ff-canadianseducationfundingguide-book-768x623.webp','guide-print-book',(360,720),90),
        'logos':[], 'blog':[]}
    author_dom=Parser(sources[root/'author/index.html']).root
    author_main=next(author_dom.find({'main'}))
    for index,img in enumerate(list(author_main.find({'img'}))[1:]):
        images['logos'].append((img.attrs['alt'],image_variants(root,img.attrs['src'],'career-'+str(index+1),(200,),100,True)))
    posts=blog_posts(Parser(sources[root/'blog/index.html']).root)
    for index,post in enumerate(posts):
        source=post['image']
        if index==0: source='/assets/32a12485d1ca2e60-grad.jpeg'
        images['blog'].append(image_variants(root,source,'journal-'+str(index+1),(300,600),88))
    foundation,dedicated=split_css(home.CSS)
    font_source=home.font_css(root)
    shared_extras='.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}'
    for selector,body in css_rules(EXTRA_CSS):
        if selector in {'.site-nav a[aria-current=page]','.site-footer .contact-phone'}:
            shared_extras+=selector+'{'+body+'}'
    foundation=minify_css(font_source+foundation+shared_extras)
    dedicated=minify_css(dedicated)
    components=component_css(EXTRA_CSS)
    newsletter_styles=component_css(dedicated)['newsletter']
    components['newsletter']=newsletter_styles
    book_source=(root/'book.css').read_text(encoding='utf-8')
    # No duplicate background image download; the genuine cover is the hero.
    book_source=re.sub(r'\.cg-book \.book-hero \{[^}]+\}', '',book_source)
    book=minify_css(book_source+BOOK_OVERRIDES)
    asset_content={'site.css':foundation,'home-layout.css':dedicated,'pages.css':minify_css(components['core']),'guide.css':book,'site.js':home.JS.strip()+'\n'}
    for component in ('author','shop','journal','article','error','appendices','newsletter'):
        asset_content[component+'.css']=minify_css(components[component])
    search_source=(root/'improvements.js').read_text(encoding='utf-8')
    search_source=search_source.split('  // Keep the existing disclosure menu;',1)[0]+'})();\n'
    asset_content['appendices.js']=search_source
    urls={}
    for name,content in asset_content.items():
        digest=sha256(content.encode()).hexdigest()
        stem,suffix=name.rsplit('.',1)
        hashed=f'{stem}-{digest[:12]}.{suffix}'
        (root/'assets'/hashed).write_text(content,encoding='utf-8',newline='\n')
        urls[name]='/assets/'+hashed
    header=re.search(r'<header class="site-header">.*?</header>',original_home,re.S)[0]
    header=header.replace('href="#inside"','href="/book/"').replace('href="#author"','href="/author/"')
    footer=re.search(r'<footer class="site-footer">.*?</footer>',original_home,re.S)[0]
    footer=footer.replace('</a></div><div class="footer-links">','</a><br><a class="contact-phone" href="tel:+17809911660">780-991-1660</a></div><div class="footer-links">',1)
    newsletter=re.search(r'<section class="newsletter".*?</section>',original_home,re.S)[0]
    # Newsletter component uses its own homepage selectors, loaded only where used.
    report=[]
    for path,source in sorted(sources.items()):
        name=path.relative_to(root).as_posix()
        if 'http-equiv="refresh"' in source:
            continue
        dom=Parser(source).root
        additional=[]
        page_header=header
        main_id='content'
        if name=='index.html':
            body=re.search(r'<main\b[^>]*>.*?</main>',source,re.S)[0]
            additional=['home-layout.css'];main_id='main-content'
        elif name=='book/index.html':
            main_node=next(dom.find({'main'}))
            body=render(main_node,True)
            additional=['guide.css','appendices.css']
            page_header=page_header.replace('href="/book/"','href="/book/" aria-current="page"',1)
        elif name=='author/index.html':
            body=author_page(dom,images);additional=['pages.css','author.css']
            page_header=page_header.replace('href="/author/"','href="/author/" aria-current="page"',1)
        elif name=='purchase/index.html':
            body=purchase_page(dom,images,newsletter);additional=['pages.css','shop.css','newsletter.css']
        elif name=='blog/index.html':
            body=blog_page(posts,images);additional=['pages.css','journal.css']
            page_header=page_header.replace('href="/blog/"','href="/blog/" aria-current="page"',1)
        elif name.startswith('2026/'):
            post=next(p for p in posts if p['url'].strip('/')==str(path.parent.relative_to(root)).replace('\\','/'))
            body=article_page(dom,post,posts,images);additional=['pages.css','article.css']
            page_header=page_header.replace('href="/blog/"','href="/blog/" aria-current="page"',1)
        elif name in {'privacy-policy-2/index.html','terms-of-service/index.html'}:
            body=legal_page(dom);additional=['pages.css']
        elif name=='404.html':
            body=error_page();additional=['pages.css','error.css']
        else:
            raise ValueError('Unexpected public page: '+name)
        if name!='index.html': page_header=page_header.replace('href="#buy"','href="/purchase/"')
        if name=='purchase/index.html': page_header=page_header.replace('href="/purchase/"','href="/purchase/" aria-current="page"',1)
        head=home.preserved_head(source)
        styles='\n'.join(f'<link rel="stylesheet" href="{urls[n]}">' for n in ['site.css']+additional)
        scripts=f'<script defer src="{urls["site.js"]}"></script>'
        if name=='book/index.html': scripts+=f'\n<script defer src="{urls["appendices.js"]}"></script>'
        html=f'<!doctype html>\n<html lang="en-CA">\n<head>\n{head}\n{styles}\n{scripts}\n</head>\n<body>\n<a class="skip-link" href="#{main_id}">Skip to content</a>\n{page_header}\n{body}\n{footer}\n</body>\n</html>\n'
        html=replace_images(html,images)
        path.write_text(html,encoding='utf-8',newline='\n')
        report.append({'path':name,'before_html_bytes':len(source.encode()),'html_bytes':len(html.encode()),'sha256':sha256(html.encode()).hexdigest(),'css_bytes':sum(len(asset_content[n].encode()) for n in ['site.css']+additional),'js_bytes':len(asset_content['site.js'].encode())+(len(asset_content['appendices.js'].encode()) if name=='book/index.html' else 0)})
    sitemap=root/'sitemap.xml'
    xml=sitemap.read_text(encoding='utf-8')
    xml=re.sub(r'<lastmod>[^<]+</lastmod>','<lastmod>2026-10-10</lastmod>',xml)
    sitemap.write_text(xml,encoding='utf-8',newline='\n')
    result={'pages':report,'assets':{urls[n]:{'bytes':len(v.encode()),'sha256':sha256(v.encode()).hexdigest()} for n,v in asset_content.items()},'responsive_images':images}
    (root/'site-build-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
