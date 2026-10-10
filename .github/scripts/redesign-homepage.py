"""Build a lean, book-focused homepage after the existing static-site pipeline.

Only index.html, the homepage's two new assets and its sitemap date are changed.
Metadata, genuine endorsements and existing book/retailer links are retained.
"""
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import sys

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def text(self):
        return ' '.join(''.join(c if isinstance(c, str) else c.text() for c in self.children).split())

    def find(self, tags):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag in tags:
                    yield child
                yield from child.find(tags)


class Parser(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


CSS = r'''
:root{--navy:#181a36;--gold:#d3b574;--bronze:#80652d;--ink:#27283a;--muted:#626271;--ivory:#f8f6ef;--line:#dedbd0;--white:#fff;--width:1160px;color-scheme:light}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:110px}
body{margin:0;background:var(--white);color:var(--ink);font:400 15px/1.75 Montserrat,Arial,sans-serif;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%;height:auto}
a{color:inherit;text-underline-offset:4px}
button{font:inherit}
[hidden]{display:none!important}
a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--bronze);outline-offset:5px}
h1,h2,h3,p,figure,blockquote{margin:0}
h1,h2,h3{color:var(--navy)}
h1,h2{font-family:Merriweather,Georgia,serif;font-weight:400;letter-spacing:-.035em}
h1{font-size:clamp(38px,4.45vw,58px);line-height:1.18}
h2{font-size:clamp(29px,3vw,40px);line-height:1.3}
h3{font-size:18px;line-height:1.5;font-weight:600}
.wrap{width:min(var(--width),calc(100% - 80px));margin-inline:auto}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.16em;line-height:1.6;text-transform:uppercase;color:var(--bronze)}
.section{padding:88px 0}
.section-heading{display:flex;justify-content:space-between;align-items:end;gap:36px;margin-bottom:40px}
.section-heading .eyebrow{margin-bottom:12px}
.section-heading>p{max-width:375px;color:var(--muted);font-size:14px}
.text-link{display:inline-flex;align-items:center;gap:9px;font-size:13px;font-weight:600;text-decoration:none;border-bottom:1px solid var(--gold);padding:5px 0;min-height:40px}
.text-link:hover{color:var(--bronze);border-color:var(--bronze)}
.arrow{width:18px;height:18px;flex:none}
.button{display:inline-flex;align-items:center;justify-content:center;gap:12px;min-height:52px;padding:14px 23px;background:var(--navy);color:#fff;font-size:13px;font-weight:600;text-decoration:none;border:1px solid var(--navy);border-radius:3px;line-height:1.5;transition:background .15s,border-color .15s}
.button:hover{background:#303353;border-color:#303353}
.button-outline{background:transparent;color:var(--navy);border-color:#bab9c2}
.button-outline:hover{background:#eeebe2;border-color:var(--navy)}
.button-gold{background:var(--gold);border-color:var(--gold);color:var(--navy)}
.button-gold:hover{background:#e3c789;border-color:#e3c789}
.skip-link{position:fixed;left:16px;top:-100px;z-index:100;background:#fff;padding:12px 20px}
.skip-link:focus{top:12px}
.site-header{position:sticky;top:0;z-index:30;background:var(--ivory);border-bottom:1px solid var(--line)}
.header-inner{display:flex;align-items:center;gap:26px;min-height:84px}
.brand{display:flex;align-items:center;gap:12px;text-decoration:none;flex-shrink:0}
.brand img{width:50px;height:30px;object-fit:contain;mix-blend-mode:multiply}
.brand-name{font-size:19px;font-weight:600;letter-spacing:-.045em;color:var(--navy);line-height:1.4}
.brand-name strong{font-weight:700}
.brand-caption{display:block;font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.site-nav{display:flex;align-items:center;justify-content:flex-end;gap:26px;margin-left:auto}
.site-nav a{font-size:12px;font-weight:500;text-decoration:none;display:flex;align-items:center;min-height:44px}
.site-nav a:hover{color:var(--bronze)}
.header-buy{min-height:44px;padding:10px 19px;white-space:nowrap}
.menu-toggle{display:none;align-items:center;justify-content:center;gap:9px;min-height:44px;padding:8px 10px;border:1px solid var(--line);border-radius:3px;background:transparent;color:var(--navy);font-size:12px;cursor:pointer}
.menu-icon{width:16px;height:16px}
.hero{background:var(--ivory);overflow:hidden}
.hero-grid{display:grid;grid-template-columns:1.12fr 1fr;align-items:center;gap:70px;padding:58px 0 56px}
.hero-copy{padding:12px 0}
.hero-copy .eyebrow{font-size:12px;letter-spacing:.12em;margin-bottom:19px;max-width:490px}
.hero-copy h1{max-width:580px;margin-bottom:23px}
.hero-lede{max-width:500px;color:var(--muted);font-size:16px;line-height:1.85}
.hero-author{margin-top:17px;font-size:12px;color:var(--muted)}
.hero-author a{color:var(--navy);font-weight:600;text-decoration:none}
.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}
.hero-digital{margin-top:13px;font-size:11px;color:var(--muted)}
.hero-digital a{color:var(--navy);font-weight:500}
.hero-art{position:relative;display:grid;place-items:center;min-height:520px;padding:14px 20px 32px}
.hero-art::before{content:"";position:absolute;inset:20px -20px 0 4px;background:#e9e5d8;border-radius:48% 48% 8px 8px}
.hero-art::after{content:"";position:absolute;bottom:8px;left:12%;right:12%;height:18px;border-radius:50%;background:#b9b1a4;filter:blur(14px);opacity:.6}
.book-cover{position:relative;z-index:1;width:322px;transform:rotate(-4deg);box-shadow:3px 2px 0 #c8c5be,7px 5px 0 #f6f4ef,10px 6px 0 #aaa99f,16px 23px 28px #181a362e;border:1px solid #42484b33}
.edition-tag{position:absolute;z-index:2;right:-4px;bottom:43px;background:var(--navy);color:#fff;padding:13px 19px;font-size:10px;letter-spacing:.11em;text-transform:uppercase;line-height:1.5}
.edition-tag span{display:block;color:var(--gold);font-weight:600}
.stats{background:var(--ivory);padding-bottom:36px}
.stats-inner{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #cfccbf;padding-top:25px}
.stat{display:flex;align-items:center;gap:16px;justify-content:center;border-right:1px solid #cfccbf}
.stat:first-child{justify-content:flex-start}
.stat:last-child{border:0;justify-content:flex-end}
.stat strong{font-family:Merriweather,Georgia,serif;font-size:33px;font-weight:400;color:var(--navy);line-height:1.2}
.stat span{font-size:12px;line-height:1.6;color:var(--muted);max-width:145px}
.endorsements{padding:62px 0 48px}
.endorsements>.wrap>.eyebrow{margin-bottom:26px}
.quote-grid{display:grid;grid-template-columns:1.15fr 1fr;gap:64px}
.quote{padding-left:24px;border-left:2px solid var(--gold)}
.quote blockquote{font-family:Merriweather,Georgia,serif;font-size:18px;line-height:1.85;letter-spacing:-.018em;color:var(--navy)}
.quote figcaption{margin-top:20px;display:flex;flex-direction:column;gap:3px}
.quote figcaption strong{font-size:12px;font-weight:600}
.quote figcaption span{font-size:11px;color:var(--muted);line-height:1.7}
.more-quotes{margin-top:28px;font-size:13px}
summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.more-quotes>summary{display:inline-flex;align-items:center;gap:12px;min-height:44px;font-size:12px;font-weight:500;color:var(--muted);border-bottom:1px solid var(--line)}
.more-quotes>summary::after{content:"+";font-size:20px;color:var(--bronze)}
.more-quotes[open]>summary::after{content:"−"}
.full-quotes{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:30px}
.full-quote{padding:24px;background:var(--ivory)}
.full-quote .eyebrow{margin-bottom:14px;font-size:9px}
.full-quote blockquote{font-size:13px}
.full-quote figcaption{margin-top:18px;font-size:11px;color:var(--muted)}
.full-quote figcaption strong{display:block;color:var(--navy)}
.inside{padding-top:60px;border-top:1px solid var(--line)}
.inside-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:36px}
.inside-item{border-top:2px solid var(--navy);padding-top:22px}
.inside-number{font-family:Merriweather,Georgia,serif;font-size:30px;line-height:1.3;color:var(--bronze);margin-bottom:14px}
.inside-item h3{margin-bottom:12px}
.inside-item p{font-size:14px;color:var(--muted);margin-bottom:17px}
.audience{display:flex;gap:25px;align-items:center;margin-top:42px;padding:24px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.audience h3{font-size:12px;font-weight:600;min-width:124px}
.audience ul{display:flex;flex-wrap:wrap;gap:10px 23px;list-style:none;padding:0;margin:0;font-size:12px;color:var(--muted)}
.audience li{display:flex;align-items:center;gap:8px}
.audience li::before{content:"";width:5px;height:5px;background:var(--bronze);border-radius:50%}
.resources-note{display:flex;align-items:center;justify-content:space-between;gap:28px;padding-top:27px;font-size:13px;color:var(--muted)}
.resources-note p{max-width:670px}
.resources-note a{white-space:nowrap}
.author{background:var(--ivory)}
.author-grid{display:grid;grid-template-columns:340px 1fr;gap:90px;align-items:center;max-width:1030px}
.author-portrait{position:relative;padding:0 16px 16px 0}
.author-portrait::before{position:absolute;content:"";inset:16px 0 0 16px;background:#e1d9c5}
.author-portrait img{position:relative;width:324px;height:365px;object-fit:cover;object-position:50% 29%}
.author-caption{position:relative;padding:12px 0 0;font-size:10px;letter-spacing:.08em;color:var(--muted)}
.author-copy .eyebrow{margin-bottom:12px}
.author-copy h2{margin-bottom:22px}
.author-copy p{color:var(--muted);font-size:14px;margin-bottom:16px}
.author-copy .text-link{margin-top:5px}
.buy{background:var(--navy);color:#ecebf0;position:relative;padding:78px 0}
.buy-grid{display:grid;grid-template-columns:.9fr 1.3fr;gap:70px;align-items:center}
.buy-copy .eyebrow{color:var(--gold);margin-bottom:15px}
.buy-copy h2{color:#fff;font-size:38px;margin-bottom:20px}
.buy-copy p{color:#c2c2cf;font-size:14px;max-width:355px}
.buy-options{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.buy-card{border:1px solid #ffffff32;padding:27px 23px 24px;display:flex;flex-direction:column;background:#ffffff04}
.buy-card h3{color:#fff;font-family:Merriweather,Georgia,serif;font-size:24px;font-weight:400}
.format-label{font-size:10px;letter-spacing:.1em;color:var(--gold);text-transform:uppercase;margin-bottom:14px}
.buy-card p{color:#c2c2cf;font-size:12px;margin:13px 0 22px;flex:1}
.buy-card .button{padding:12px 14px;font-size:12px;width:100%}
.buy-card .button-outline{border-color:#ffffff80;color:#fff}
.buy-card .button-outline:hover{background:#ffffff12;border-color:#fff}
.buy a:focus-visible{outline-color:var(--gold)}
.retailer-note{margin-top:21px;font-size:11px;color:#c2c2cf;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.retailer-note a{color:#fff}
.faq-grid{display:grid;grid-template-columns:.85fr 1.3fr;gap:80px}
.faq-heading .eyebrow{margin-bottom:13px}
.faq-heading p{color:var(--muted);font-size:14px;margin-top:20px;max-width:300px}
.faq-list{border-top:1px solid var(--line)}
.faq-list details{border-bottom:1px solid var(--line)}
.faq-list summary{display:flex;align-items:center;justify-content:space-between;gap:25px;font-size:14px;font-weight:600;color:var(--navy);min-height:70px;padding:19px 2px;line-height:1.6}
.faq-list summary::after{content:"+";color:var(--bronze);font-size:25px;font-weight:400;flex:none}
.faq-list details[open] summary::after{content:"−"}
.faq-list details>div{padding:0 30px 24px 2px;font-size:13px;color:var(--muted)}
.faq-list details>div a{color:var(--navy)}
.newsletter{padding:40px 0 48px;background:var(--ivory);border-top:1px solid var(--line)}
.newsletter-grid{display:flex;align-items:center;justify-content:space-between;gap:40px}
.newsletter .eyebrow{margin-bottom:9px}
.newsletter h2{font-size:26px;margin-bottom:12px}
.newsletter p{font-size:12px;max-width:680px;color:var(--muted)}
.newsletter .button{white-space:nowrap}
.site-footer{padding:46px 0 22px;background:#fff;font-size:12px;color:var(--muted)}
.footer-top{display:flex;justify-content:space-between;gap:40px;padding-bottom:34px}
.footer-brand .brand-name{font-size:20px;margin-bottom:12px;display:block}
.footer-brand p{max-width:340px;font-size:12px;margin-bottom:8px}
.footer-links{display:flex;gap:70px}
.footer-links div{display:flex;flex-direction:column;gap:2px}
.footer-links strong{font-size:11px;color:var(--navy);margin-bottom:7px;text-transform:uppercase;letter-spacing:.08em}
.footer-links a{display:flex;align-items:center;min-height:35px;text-decoration:none;font-size:11px}
.footer-links a:hover{color:var(--bronze)}
.footer-bottom{border-top:1px solid var(--line);padding-top:20px;display:flex;justify-content:space-between;gap:20px;font-size:10px}
.footer-bottom nav{display:flex;gap:20px}
.footer-bottom a{display:inline-flex;min-height:30px;align-items:center}
@media(min-width:1600px){.hero-grid{padding-block:74px}.hero-art{min-height:560px}.book-cover{width:345px}}
@media(max-width:1080px){.wrap{width:calc(100% - 56px)}.site-nav{gap:18px}.site-nav a{font-size:11px}.header-inner{gap:18px}.hero-grid{gap:35px}.hero-art{min-height:475px}.book-cover{width:290px}.edition-tag{right:-10px}.hero-lede{font-size:14px}.hero-copy .eyebrow{font-size:10px}.hero-actions .button{font-size:12px;padding-inline:17px}.author-grid{gap:50px;grid-template-columns:300px 1fr}.author-portrait img{width:284px;height:340px}.buy-grid{gap:40px;grid-template-columns:.85fr 1.4fr}.buy-card{padding:24px 17px}.buy-copy h2{font-size:31px}.faq-grid{gap:50px}.quote-grid{gap:40px}}
@media(max-width:860px){.wrap{width:calc(100% - 44px)}.header-inner{min-height:74px;gap:13px;flex-wrap:wrap}.brand{margin-right:auto;gap:8px}.brand img{width:39px;height:24px}.brand-name{font-size:17px}.brand-caption{font-size:8px}.menu-toggle{display:flex}.header-buy{font-size:11px;padding:10px 14px}.site-nav{order:4;flex-basis:100%;margin:0;display:flex;flex-wrap:wrap;justify-content:flex-start;gap:0;padding:0 0 14px}.site-nav a{font-size:13px;width:50%;padding:7px 0;min-height:44px}.js .site-nav:not(.is-open){display:none}.hero-grid{gap:30px;padding:42px 0}.hero-art{min-height:415px;padding-inline:14px}.book-cover{width:245px}.hero-art::before{inset:10px -4px 0}.edition-tag{right:-7px;bottom:30px;font-size:8px;padding:11px 12px}.hero-copy h1{font-size:38px}.hero-author{font-size:10px}.hero-actions{margin-top:23px}.hero-actions .button{padding:12px 17px;min-height:47px}.stat strong{font-size:28px}.stat span{font-size:10px}.stat{gap:12px}.section{padding:64px 0}.section-heading{gap:30px}.section-heading>p{max-width:260px;font-size:12px}.inside-grid{gap:25px}.inside-item h3{font-size:16px}.inside-item p{font-size:12px}.resources-note{flex-direction:column;align-items:flex-start;gap:12px}.author-grid{gap:38px;grid-template-columns:250px 1fr}.author-portrait img{width:234px;height:300px}.author-copy h2{font-size:27px}.author-copy p{font-size:12px}.buy-grid{grid-template-columns:1fr;gap:30px}.buy-copy{max-width:570px}.buy-copy h2{font-size:34px}.buy-copy p{max-width:570px}.buy-card{padding:27px}.faq-grid{grid-template-columns:1fr;gap:27px}.faq-heading p{max-width:540px}.faq-heading h2{font-size:32px}.newsletter-grid{gap:25px}.newsletter p{max-width:440px}.footer-links{gap:35px}.quote blockquote{font-size:16px}}
@media(max-width:600px){html{scroll-padding-top:92px}.wrap{width:calc(100% - 40px)}.header-inner{gap:8px;min-height:70px}.brand-name{font-size:15px}.brand-caption{font-size:7px}.brand img{width:32px;height:20px}.menu-toggle{padding:8px;border:0;font-size:0;gap:0;min-width:40px}.menu-icon{width:21px;height:21px}.header-buy{min-height:41px;padding:9px 12px;font-size:10px}.hero-grid{display:flex;flex-direction:column;gap:25px;padding:32px 0 31px}.hero-copy{padding:0;width:100%}.hero-copy .eyebrow{font-size:9px;letter-spacing:.1em;margin-bottom:15px}.hero-copy h1{font-size:37px;line-height:1.2;max-width:400px;margin-bottom:18px}.hero-lede{font-size:13px;line-height:1.85;max-width:420px}.hero-author{font-size:10px;margin-top:13px}.hero-actions{display:grid;grid-template-columns:1.2fr 1fr;gap:9px;margin-top:22px}.hero-actions .button{padding:12px 9px;min-height:49px;font-size:11px;gap:7px}.hero-actions .arrow{width:15px}.hero-digital{font-size:10px;margin-top:10px}.hero-art{width:100%;min-height:345px;padding:12px 24px 25px;max-width:400px}.hero-art::before{inset:5px 13px 0}.book-cover{width:222px;transform:rotate(-3deg)}.edition-tag{right:5px;bottom:21px;font-size:8px;padding:11px 13px}.stats{padding-bottom:25px}.stats-inner{padding-top:22px;gap:10px}.stat,.stat:first-child,.stat:last-child{flex-direction:column;gap:6px;align-items:center;justify-content:flex-start;text-align:center}.stat strong{font-size:28px}.stat span{font-size:9px;max-width:95px;line-height:1.6}.endorsements{padding:39px 0}.endorsements>.wrap>.eyebrow{font-size:9px;margin-bottom:23px}.quote-grid{grid-template-columns:1fr;gap:28px}.quote{padding-left:19px}.quote blockquote{font-size:16px;line-height:1.85}.quote figcaption{margin-top:14px}.quote figcaption strong{font-size:11px}.quote figcaption span{font-size:10px}.more-quotes{margin-top:20px}.more-quotes>summary{font-size:10px}.full-quotes{grid-template-columns:1fr;gap:18px}.section{padding:48px 0}.section-heading{display:block;margin-bottom:29px}.section-heading>p{margin-top:17px;max-width:400px;font-size:13px}.section-heading .eyebrow{margin-bottom:10px}.section-heading h2{font-size:30px}.inside-grid{grid-template-columns:1fr;gap:27px}.inside-item{display:grid;grid-template-columns:40px 1fr;gap:12px;padding-top:21px}.inside-number{font-size:24px}.inside-item h3{font-size:17px;margin-bottom:10px}.inside-item p{font-size:13px;margin-bottom:10px}.audience{display:block;margin-top:28px;padding:22px 0}.audience h3{margin-bottom:13px}.audience ul{gap:9px 15px;font-size:11px}.resources-note{font-size:12px;padding-top:22px}.author-grid{display:flex;flex-direction:column-reverse;gap:27px;align-items:stretch}.author-copy h2{font-size:30px;margin-bottom:20px}.author-copy p{font-size:13px}.author-portrait{max-width:290px;margin-inline:auto}.author-portrait img{width:274px;height:303px}.author-caption{font-size:9px}.buy{padding:47px 0}.buy-grid{gap:26px}.buy-copy h2{font-size:32px}.buy-copy p{font-size:13px}.buy-options{grid-template-columns:1fr;gap:14px}.buy-card{padding:24px}.buy-card h3{font-size:23px}.buy-card p{margin:11px 0 19px;font-size:12px}.format-label{margin-bottom:10px;font-size:9px}.retailer-note{font-size:10px;gap:10px}.faq-grid{gap:24px}.faq-heading h2{font-size:29px}.faq-heading p{font-size:13px;margin-top:16px}.faq-list summary{font-size:12px;min-height:66px;padding-block:17px;gap:14px}.faq-list details>div{font-size:12px;padding-right:12px}.newsletter{padding:35px 0}.newsletter-grid{display:block}.newsletter h2{font-size:25px}.newsletter p{font-size:11px}.newsletter .button{margin-top:22px;font-size:12px}.site-footer{padding:34px 0 20px}.footer-top{display:block;padding-bottom:22px}.footer-brand{margin-bottom:27px}.footer-brand p{font-size:11px}.footer-links{gap:52px}.footer-links a{min-height:39px}.footer-bottom{display:block;font-size:9px}.footer-bottom nav{gap:18px;margin-top:9px}.footer-bottom a{min-height:36px}}
@media(max-width:600px){.brand-caption{display:none}.menu-toggle{min-width:44px}.header-buy{min-height:44px}}
@media(max-width:380px){.header-inner{gap:4px}.brand img{display:none}.brand-name{font-size:14px}.hero-copy h1{font-size:32px}.hero-actions .button{font-size:10px;padding-inline:7px;gap:4px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.button{transition:none}}
'''

JS = r'''(() => {
  const root = document.documentElement;
  const button = document.getElementById('menu-toggle');
  const nav = document.getElementById('site-navigation');
  if (!button || !nav) return;
  root.classList.add('js');
  button.hidden = false;
  const mobile = window.matchMedia('(max-width: 860px)');
  function setOpen(open, focusButton = false) {
    nav.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (focusButton) button.focus();
  }
  button.addEventListener('click', () => setOpen(button.getAttribute('aria-expanded') !== 'true'));
  nav.addEventListener('click', event => {
    if (mobile.matches && event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') setOpen(false, true);
  });
  document.addEventListener('click', event => {
    if (mobile.matches && !event.target.closest('.site-header')) setOpen(false);
  });
  mobile.addEventListener('change', () => setOpen(false));
})();
'''

ARROW = '<svg class="arrow" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 12h15m-6-6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
COVER = '/assets/3d0e214411d33b92-coverdraft-CanadiansEducationFundingGuide-639160395068117422-images-0-scaled-e1780942186837-728x1024.jpg'
PORTRAIT = '/assets/617a37aebdc8cfb6-27821ff85ed01902-IMG_3171-1-768x1024.webp'
CAP = '/assets/98f6c8f1bf4fdbd4-grad_cap.webp'
PRINT = 'https://www.amazon.ca/dp/1834387698'
KINDLE = 'https://www.amazon.ca/dp/B0HCXYSHX6'
NEWSLETTER = 'https://canadian-grads-shop.onrender.com/#form-field-email'


def extract_reviews(html):
    dom = Parser(html).root
    reviews = []
    for slide in dom.find({'div'}):
        if 'swiper-slide' not in slide.attrs.get('class', '').split():
            continue
        fields = {}
        for node in slide.find({'div', 'span'}):
            for field in ('text', 'name', 'title'):
                if f'elementor-testimonial__{field}' in node.attrs.get('class', '').split():
                    fields[field] = node.text()
        if fields.get('text'):
            if not fields.get('name') or not fields.get('title'):
                raise ValueError('An endorsement is missing its attribution')
            reviews.append(fields)
    if len(reviews) != 6:
        raise ValueError(f'Expected six genuine endorsements, found {len(reviews)}')
    return reviews


def font_css(root):
    blocks = []
    for filename in ('88da5473b4bd6d2d-css.css', '9508b1d05fd06d5d-css.css'):
        source = (root / 'assets' / filename).read_text(encoding='utf-8')
        for block in re.findall(r'@font-face\s*\{[^}]+\}', source):
            if 'U+0000-00FF' in block and 'font-style: normal;' in block and re.search(r'font-weight: (400|500|600|700);', block):
                blocks.append(block)
    if len(blocks) != 8:
        raise ValueError(f'Expected eight local font declarations, found {len(blocks)}')
    return '\n'.join(blocks) + '\n'


def preserved_head(html):
    source = html.split('<head>', 1)[1].split('</head>', 1)[0]
    # Keep title, search/social metadata, icons, canonical and structured data.
    source = re.sub(r'<style\b[^>]*>.*?</style>', '', source, flags=re.S | re.I)
    source = re.sub(r'<script\b(?![^>]*type=["\']application/ld\+json["\'])[^>]*>.*?</script>', '', source, flags=re.S | re.I)
    source = re.sub(r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', '', source, flags=re.I)
    source = source.replace('name="twitter:image:alt" content="Home"', 'name="twitter:image:alt" content="Canadians&#x27; Education Funding Guide"')
    return re.sub(r'\n\s*\n+', '\n', source).strip()


def full_reviews(reviews):
    out = []
    for index, item in enumerate(reviews):
        label = 'Planning client experience' if index in (2, 3) else 'Book endorsement'
        out.append(f'''<figure class="full-quote"><p class="eyebrow">{label}</p>
          <blockquote>{escape(item['text'])}</blockquote>
          <figcaption><strong>{escape(item['name'])}</strong>{escape(item['title'])}</figcaption></figure>''')
    return '\n'.join(out)


def body_html(reviews):
    first = "Canadians' Education Funding Guide is by far the most comprehensive guide I have come across that focuses solely on this task."
    second = "As a father of a high school senior, I found John's book, particularly the chapter on scholarships, extremely insightful."
    for excerpt, review in ((first, reviews[0]), (second, reviews[1])):
        if excerpt not in review['text']:
            raise ValueError('Featured quote must be an exact excerpt from the existing endorsement')
    featured = '\n'.join(f'''<figure class="quote"><blockquote>“{escape(excerpt)}”</blockquote>
      <figcaption><strong>{escape(review['name'])}</strong><span>{escape(review['title'])}</span></figcaption></figure>'''
      for excerpt, review in ((first, reviews[0]), (second, reviews[1])))
    return f'''
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="/" aria-label="Canadian GRADS home"><img src="{CAP}" alt="" width="261" height="156"><span><span class="brand-name">Canadian <strong>GRADS</strong></span><span class="brand-caption">Education funding, explained</span></span></a>
    <button id="menu-toggle" class="menu-toggle" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="site-navigation" hidden><svg class="menu-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg><span>Menu</span></button>
    <nav class="site-nav" id="site-navigation" aria-label="Main navigation"><a href="#inside">Inside the book</a><a href="/book/#resources">Free PDF resources</a><a href="#author">The author</a><a href="/blog/">Blog</a></nav>
    <a class="button button-gold header-buy" href="#buy">Get the book</a>
  </div>
</header>
<main id="main-content">
  <section class="hero" aria-labelledby="hero-title">
    <div class="wrap hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Canadians’ Education Funding Guide</p>
        <h1 id="hero-title">More ways to fund<br>your education.</h1>
        <p class="hero-lede">Discover 85 Canadian funding sources—from RESPs and scholarships to grants and loans—and build a practical plan for post-secondary costs.</p>
        <p class="hero-author">By <a href="/author/">John F. McLaughlin</a> <span aria-hidden="true">&nbsp;·&nbsp;</span> First edition</p>
        <div class="hero-actions"><a class="button" href="{PRINT}">Buy print on Amazon {ARROW}</a><a class="button button-outline" href="/book/#sample-source">Read a sample {ARROW}</a></div>
        <p class="hero-digital">Prefer digital? <a href="{KINDLE}">Explore the Kindle edition</a></p>
      </div>
      <figure class="hero-art"><img class="book-cover" src="{COVER}" alt="Canadians’ Education Funding Guide, First Edition, by John F. McLaughlin" width="728" height="1024" fetchpriority="high" decoding="async"><figcaption class="edition-tag">One guide.<span>More possibilities.</span></figcaption></figure>
    </div>
  </section>
  <section class="stats" aria-label="What the guide includes"><div class="wrap stats-inner"><div class="stat"><strong>85</strong><span>Canadian<br>funding sources</span></div><div class="stat"><strong>700+</strong><span>Resource links<br>to explore</span></div><div class="stat"><strong>20</strong><span>Tools to build<br>your funding plan</span></div></div></section>
  <section class="endorsements" aria-label="Book endorsements"><div class="wrap"><p class="eyebrow">Perspectives from an educator and a parent</p><div class="quote-grid">{featured}</div>
    <details class="more-quotes"><summary>Read all endorsements and client experiences</summary><div class="full-quotes">{full_reviews(reviews)}</div></details>
  </div></section>
  <section class="section inside" id="inside" aria-labelledby="inside-title"><div class="wrap">
    <div class="section-heading"><div><p class="eyebrow">Inside the guide</p><h2 id="inside-title">Turn possibilities<br>into a funding plan.</h2></div><p>One place to understand your options, explore useful resources and take the next step with more confidence.</p></div>
    <div class="inside-grid">
      <article class="inside-item"><p class="inside-number" aria-hidden="true">01</p><div><h3>Find more funding options</h3><p>Look beyond a single savings account. Explore scholarships, grants, loans, RESPs and other Canadian sources of education funding.</p><a class="text-link" href="/book/#contents">Explore the chapters {ARROW}</a></div></article>
      <article class="inside-item"><p class="inside-number" aria-hidden="true">02</p><div><h3>Know where to look</h3><p>Use over 700 resource links to research programs and opportunities, with guidance for different learners and stages of life.</p><a class="text-link" href="/book/#sample-source">See a sample funding source {ARROW}</a></div></article>
      <article class="inside-item"><p class="inside-number" aria-hidden="true">03</p><div><h3>Build a plan that fits</h3><p>Work through 20 do-it-yourself planning tools to bring your education goals, costs and funding options together.</p><a class="text-link" href="/book/#toolkit">Explore the planning toolkit {ARROW}</a></div></article>
    </div>
    <div class="audience"><h3>Written for</h3><ul><li>Parents &amp; grandparents</li><li>Students</li><li>Adults returning to school</li><li>Educators &amp; advisors</li></ul></div>
    <div class="resources-note"><p>Already have the guide—or want to explore further? The companion appendices bring useful reference material together in one place.</p><a class="text-link" href="/book/#resources">Browse the free PDFs {ARROW}</a></div>
  </div></section>
  <section class="section author" id="author" aria-labelledby="author-title"><div class="wrap author-grid">
    <figure class="author-portrait"><img src="{PORTRAIT}" alt="John F. McLaughlin, author of Canadians’ Education Funding Guide" width="768" height="1024" loading="lazy" decoding="async"><figcaption class="author-caption">John F. McLaughlin · Edmonton, Alberta</figcaption></figure>
    <div class="author-copy"><p class="eyebrow">Meet the author</p><h2 id="author-title">Practical experience.<br>A personal purpose.</h2><p>John F. McLaughlin brings a 44-year career in planning and management consulting to a subject he knows personally: funding education across three generations of his family.</p><p>His guide brings that experience and years of research together to help Canadians discover more options and create their own education funding plan.</p><a class="text-link" href="/author/">Read John’s story {ARROW}</a></div>
  </div></section>
  <section class="buy" id="buy" aria-labelledby="buy-title"><div class="wrap buy-grid">
    <div class="buy-copy"><p class="eyebrow">Your next chapter starts here</p><h2 id="buy-title">Get the guide.<br>Start your plan.</h2><p>Choose the format that works for you and explore the possibilities for your education—or your family’s.</p></div>
    <div><div class="buy-options">
      <article class="buy-card"><span class="format-label">The print edition</span><h3>A book to keep<br>by your side.</h3><p>Explore the chapters, revisit the resources and work through your plan at your own pace.</p><a class="button button-gold" href="{PRINT}">Buy print on Amazon {ARROW}</a></article>
      <article class="buy-card"><span class="format-label">The Kindle edition</span><h3>Your guide,<br>wherever you go.</h3><p>Prefer to read digitally? Explore the Kindle edition and current device options on Amazon.</p><a class="button button-outline" href="{KINDLE}">View Kindle on Amazon {ARROW}</a></article>
    </div><div class="retailer-note"><span>See current pricing and availability on Amazon.</span><a href="/purchase/">Other retailers &amp; purchase details</a></div></div>
  </div></section>
  <section class="section faq" aria-labelledby="faq-title"><div class="wrap faq-grid">
    <div class="faq-heading"><p class="eyebrow">Before you begin</p><h2 id="faq-title">A few helpful answers.</h2><p>Find the right starting point for your education funding journey.</p></div>
    <div class="faq-list">
      <details><summary>Who is the guide for?</summary><div>It is written for parents, grandparents, students and adults returning to education, as well as educators and advisors helping them plan. The guide also explores funding options for Indigenous learners, people with disabilities and new Canadians.</div></details>
      <details><summary>Does it cover more than RESPs?</summary><div>Yes. RESPs are one part of the guide’s 85 funding sources. It also covers scholarships, grants, loans and other options. <a href="/book/#contents">Browse the contents</a> to see the topics.</div></details>
      <details><summary>Can I preview the book before buying?</summary><div>Yes. You can <a href="/book/#sample-source">read a sample funding source</a>, explore the <a href="/book/#toolkit">planning toolkit overview</a> and browse the <a href="/book/#resources">free companion appendix PDFs</a>.</div></details>
      <details><summary>Are there planning tools in the guide?</summary><div>The guide includes 20 do-it-yourself tools to help you prepare an education funding plan for your own circumstances. <a href="/book/#toolkit">See the toolkit overview</a>.</div></details>
      <details><summary>Does it include information for Quebec?</summary><div>Yes. Chapter 16 discusses Quebec’s education funding arrangements and how they differ from other Canadian jurisdictions.</div></details>
      <details><summary>Where can I buy it or request it from a library?</summary><div>Explore the <a href="{PRINT}">print edition</a> and <a href="{KINDLE}">Kindle edition</a> on Amazon, or see <a href="/purchase/">other retailer options</a>. To request the print book from a library, use the title <em>Canadians’ Education Funding Guide</em>, author John F. McLaughlin and ISBN 9781834387697.</div></details>
    </div>
  </div></section>
  <section class="newsletter" aria-labelledby="newsletter-title"><div class="wrap newsletter-grid"><div><p class="eyebrow">Stay connected</p><h2 id="newsletter-title">Keep learning about your options.</h2><p>Sign up for the planned quarterly Canadian GRADS newsletter, launching by the end of 2026. Subscriptions are free until the end of 2027.</p></div><a class="button button-outline" href="{NEWSLETTER}">Sign up for the newsletter {ARROW}</a></div></section>
</main>
<footer class="site-footer"><div class="wrap">
  <div class="footer-top"><div class="footer-brand"><span class="brand-name">Canadian <strong>GRADS</strong></span><p>Helping Canadians explore more ways to fund education.</p><a href="mailto:john@canadiangrads.ca">john@canadiangrads.ca</a></div><div class="footer-links"><div><strong>The guide</strong><a href="/book/">About the book</a><a href="/book/#resources">Free appendix PDFs</a><a href="/purchase/">Where to buy</a></div><div><strong>Explore</strong><a href="/author/">About John</a><a href="/blog/">Blog &amp; articles</a><a href="https://www.linkedin.com/in/johnfrederickmclaughlin/">LinkedIn</a></div></div></div>
  <div class="footer-bottom"><p>© 2026 Canadian GRADS. All rights reserved.</p><nav aria-label="Legal"><a href="/privacy-policy-2/">Privacy policy</a><a href="/terms-of-service/">Terms &amp; conditions</a></nav></div>
</div></footer>
'''


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'public').resolve()
    original = (root / 'index.html').read_text(encoding='utf-8')
    if 'class="wrap hero-grid"' in original:
        raise ValueError('Run this homepage transform on the extracted site, not its own output')
    reviews = extract_reviews(original)
    for url in (COVER, PORTRAIT, CAP):
        if not (root / url.lstrip('/')).is_file():
            raise FileNotFoundError(url)
    styles = font_css(root) + CSS.strip() + '\n'
    script = JS.strip() + '\n'
    css_hash = sha256(styles.encode()).hexdigest()[:12]
    js_hash = sha256(script.encode()).hexdigest()[:12]
    head = preserved_head(original)
    home = f'''<!doctype html>
<html lang="en-CA">
<head>
{head}
<link rel="stylesheet" href="/home.css?v={css_hash}">
<script defer src="/home.js?v={js_hash}"></script>
</head>
<body>
{body_html(reviews)}
</body>
</html>
'''
    (root / 'home.css').write_text(styles, encoding='utf-8', newline='\n')
    (root / 'home.js').write_text(script, encoding='utf-8', newline='\n')
    (root / 'index.html').write_text(home, encoding='utf-8', newline='\n')
    sitemap = root / 'sitemap.xml'
    xml = sitemap.read_text(encoding='utf-8')
    xml, count = re.subn(r'(<loc>https://canadiangrads\.shop/</loc><lastmod>)[^<]+', r'\g<1>2026-10-10', xml)
    if count != 1:
        raise ValueError('Expected exactly one homepage URL in the sitemap')
    sitemap.write_text(xml, encoding='utf-8', newline='\n')
    print(json.dumps({'homepage': {'bytes': len(home.encode()), 'sha256': sha256(home.encode()).hexdigest()}, 'css': {'bytes': len(styles.encode()), 'sha256': sha256(styles.encode()).hexdigest()}, 'js': {'bytes': len(script.encode()), 'sha256': sha256(script.encode()).hexdigest()}, 'genuine_endorsements_preserved': len(reviews)}, indent=2))


if __name__ == '__main__':
    main()
