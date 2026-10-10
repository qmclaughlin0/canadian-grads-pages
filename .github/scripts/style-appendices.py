"""Retypeset the existing public appendices without revising their reference content.

Install reportlab==4.4.9 pdfplumber==0.11.9 pypdf==6.10.0.
Usage: python style-appendices.py INPUT_ASSETS OUTPUT_ASSETS
The source PDFs are never modified. Rebuilt PDFs keep their public filenames.
"""
from pathlib import Path
import re, sys, json, html, hashlib, io
import pdfplumber
from pypdf import PdfReader
from pypdf.filters import decode_stream_data
import reportlab
from reportlab import rl_config
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether

NAVY = colors.HexColor('#211f40')
DEEP = colors.HexColor('#16163f')
GOLD = colors.HexColor('#d3b574')
INK = colors.HexColor('#292b36')
MUTED = colors.HexColor('#666777')
PALE = colors.HexColor('#f3f4f7')
LINE = colors.HexColor('#dce0e7')
BRONZE = colors.HexColor('#80652d')
rl_config.useA85=False
TITLES = {
    'B': 'Classification of Alberta Trades',
    'C': 'Organizations with Scholarships and Bursaries',
    'D': 'Sample Canadian Financial Institutions',
    'E': 'Age of Majority by Province',
    'F': 'Funding Sources by Sponsor Type',
    'G': 'Private Sector Specialists',
    'H': 'Canadian Financial Literacy Resources',
    'I': 'Funding Sources for Low-Income Families',
    'J': 'Income Tax Filing Tips for Students',
    'K': 'Tax Advantages of Funding Sources',
    'L': 'Modeling for Optimal Use of RESP',
    'M': 'Funding Sources Applicable to Demographic Groups',
}

fontdir = Path(reportlab.__file__).parent / 'fonts'
for name, filename in [('Body', 'Vera.ttf'), ('BodyBold', 'VeraBd.ttf'), ('BodyItalic', 'VeraIt.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(fontdir / filename)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='BodyItalic', boldItalic='BodyBold')
STYLES = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=9.7, leading=14.3, textColor=INK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Body', fontSize=8.1, leading=11.4, textColor=MUTED, spaceAfter=6),
    'heading': ParagraphStyle('heading', fontName='BodyBold', fontSize=10.7, leading=14.7, textColor=NAVY, spaceBefore=9, spaceAfter=6, keepWithNext=True),
    'cell': ParagraphStyle('cell', fontName='Body', fontSize=8.6, leading=11.7, textColor=INK),
    'url': ParagraphStyle('url', fontName='Body', fontSize=7.9, leading=10.8, textColor=BRONZE, splitLongWords=True),
    'th': ParagraphStyle('th', fontName='BodyBold', fontSize=8.2, leading=11.3, textColor=colors.white),
    'center': ParagraphStyle('center', fontName='Body', fontSize=8.6, leading=11.7, textColor=INK, alignment=TA_CENTER),
    'bullet': ParagraphStyle('bullet', fontName='Body', fontSize=9.7, leading=14.3, textColor=INK, leftIndent=12, firstLineIndent=-10, spaceAfter=5),
}

def clean(text):
    if text is None:
        return ''
    return re.sub(r'\s+', ' ', str(text).translate(str.maketrans({'\u2010':'-', '\u2011':'-', '\u2012':'-', '\u2013':'-', '\u2014':'-', '\u2212':'-'}))).strip()

def esc(text):
    return html.escape(clean(text), quote=True)

def para(text, style='body', uri=None):
    text = clean(text)
    if uri:
        rendered = f'<link href="{html.escape(uri, quote=True)}" color="#80652d">{html.escape(text)}</link>'
    else:
        rendered = html.escape(text)
    return Paragraph(rendered, STYLES[style] if isinstance(style,str) else style)

def heading(text):
    return para(text, 'heading')

def link_in_cell(page, bbox):
    if not bbox:
        return None
    x0, top, x1, bottom = bbox
    candidates = []
    for link in page.hyperlinks:
        x, y = (link['x0'] + link['x1']) / 2, (link['top'] + link['bottom']) / 2
        if x0-2 <= x <= x1+2 and top-2 <= y <= bottom+2 and link.get('uri'):
            candidates.append(link['uri'])
    return candidates[0] if candidates else None

def url_text(text):
    return re.sub(r'\s+', '', str(text or ''))

def make_table(rows, widths, header=True, urlcols=(), uris=None, centercols=(), spans=(), size=None, padding=6):
    header_count=int(header)
    data = []
    for ri, row in enumerate(rows):
        line = []
        for ci, value in enumerate(row):
            value = clean(value)
            style = 'th' if ri < header_count else ('url' if ci in urlcols and value != 'N/A' else ('center' if ci in centercols else 'cell'))
            if ri >= header_count and ci in urlcols and value != 'N/A':
                value = url_text(row[ci])
                uri = (uris or {}).get((ri, ci)) or ('https://' + value if value.startswith('www.') else value)
            else:
                uri = (uris or {}).get((ri,ci)) if ri>=header_count else None
            cell_style=STYLES[style]
            if size and ri >= header_count:
                cell_style=ParagraphStyle('custom', parent=cell_style, fontSize=size, leading=size*1.34)
            p = para(value, cell_style, uri)
            line.append(p)
        data.append(line)
    table = Table(data, colWidths=widths, repeatRows=header_count, hAlign='LEFT', splitByRow=1)
    commands = [('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),padding), ('RIGHTPADDING',(0,0),(-1,-1),padding), ('TOPPADDING',(0,0),(-1,-1),padding), ('BOTTOMPADDING',(0,0),(-1,-1),padding), ('LINEBELOW',(0,0),(-1,-1),0.35,LINE)]
    if header:
        commands += [('BACKGROUND',(0,0),(-1,header_count-1),NAVY), ('TOPPADDING',(0,0),(-1,header_count-1),7), ('BOTTOMPADDING',(0,0),(-1,header_count-1),7)]
    for ri in range(header_count, len(rows)):
        if ri % 2:
            commands.append(('BACKGROUND',(0,ri),(-1,ri),PALE))
    commands += [('SPAN', start, end) for start, end in spans]
    table.setStyle(TableStyle(commands))
    return table

def extracted(page, index=0, cols=None, start=1, fillcols=()):
    source = page.find_tables()[index]
    raw = source.extract()
    selected = cols or list(range(len(raw[0])))
    rows, uris, last = [], {}, {}
    for ri in range(start, len(raw)):
        row = [raw[ri][ci] for ci in selected]
        if not any(clean(value) for value in row):
            continue
        # Forward-fill only genuinely merged cells, never an empty source cell.
        for ci in fillcols:
            if row[ci] is None:
                row[ci] = last.get(ci, '')
            elif clean(row[ci]):
                last[ci] = row[ci]
        rows.append(row)
        for ci, src_ci in enumerate(selected):
            uri = link_in_cell(page, source.rows[ri].cells[src_ci])
            if uri:
                uris[(len(rows), ci)] = uri  # Destination table has one header row.
            elif ci in fillcols and raw[ri][src_ci] is None and len(rows)>1:
                prior = uris.get((len(rows)-1,ci))
                if prior:
                    uris[(len(rows),ci)] = prior
    return rows, uris

class Header:
    def __init__(self, code, page_size):
        self.code, self.page_size = code, page_size
    def __call__(self, canvas, doc):
        w, h = self.page_size
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.setFont('BodyBold', 10)
        canvas.drawString(42, h-36, 'CANADIAN GRADS')
        canvas.setFillColor(BRONZE)
        canvas.setFont('BodyBold', 8)
        canvas.drawRightString(w-42, h-36, 'APPENDIX ' + self.code)
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(2)
        canvas.line(42,h-49,w-42,h-49)
        title_style = ParagraphStyle('title', fontName='Times-Bold', fontSize=25 if w==612 else 24, leading=29, textColor=DEEP)
        title = Paragraph(esc(TITLES[self.code]), title_style)
        tw, th = title.wrap(w-84, 80)
        title.drawOn(canvas,42,h-65-th)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(.6)
        canvas.line(42,43,w-42,43)
        canvas.setFont('Body',7.3)
        canvas.setFillColor(MUTED)
        canvas.drawString(42,29,'Canadian GRADS | Book appendices')
        canvas.linkURL('https://canadiangrads.shop/book/#resources',(42,23,238,38),relative=0)
        canvas.drawRightString(w-42,29,f'{self.code}  /  {doc.page}')
        canvas.restoreState()

def original_figure(source_page, index, width, max_height):
    """Embed the original chart image with all original pixels and no lossy conversion."""
    source_image=source_page.images[index]
    sw,sh=source_image.image.size
    scale=min(width/sw,max_height/sh)
    stream=source_image.indirect_reference.get_object()
    encoded=decode_stream_data(stream)
    if not encoded.startswith(b'\xff\xd8'):
        buffer=io.BytesIO()
        source_image.image.save(buffer,format='PNG')
        encoded=buffer.getvalue()
    return Image(io.BytesIO(encoded),width=sw*scale,height=sh*scale,hAlign='CENTER')

def paragraph_blocks(page, excluded=()):
    lines = []
    for item in page.extract_text_lines(return_chars=True):
        text = clean(item['text'])
        if not text or item['top'] < 45 or item['top'] > page.height-48 or re.match(r'^Appendix [A-M](\d+)?\s*-',text) or (text.isdigit() and item['top']>page.height*.85):
            continue
        if text=='o':
            if lines:
                lines[-1]['bullet']=True
                lines[-1]['text']='- '+lines[-1]['text']
            continue
        if any(top-1 <= (item['top']+item['bottom'])/2 <= bottom+1 for _,top,_,bottom in excluded):
            continue
        chars = [c for c in item['chars'] if c['text'].strip()]
        ordered=sorted(chars,key=lambda c:c['x0'])
        gaps=[(ordered[j+1]['x0']-ordered[j]['x1'],j) for j in range(len(ordered)-1)]
        if gaps and max(gaps)[0]>35:
            _,j=max(gaps)
            cut=(ordered[j]['x1']+ordered[j+1]['x0'])/2
            left=page.crop((item['x0']-.1,item['top']-.1,cut,item['bottom']+.1)).extract_text()
            right=page.crop((cut,item['top']-.1,item['x1']+.1,item['bottom']+.1)).extract_text()
            text=clean(left)+' | '+clean(right)
        bold = sum('Bold' in c['fontname'] for c in chars) / max(1,len(chars)) > .75
        bullet = bool(re.match(r'^[•]\s*',text)) or bool(re.match(r'^[a-f]\.\s',text))
        text = re.sub(r'^[•]\s*','- ',text)
        lines.append(dict(text=text,top=item['top'],bottom=item['bottom'],bold=bold,bullet=bullet))
    blocks=[]
    for line in lines:
        separate=bool(re.match(r'^(CCB|CESG|IRR|K|Yr\.|Max\.|Min)\s*=',line['text']))
        if blocks and not separate and not line['bold'] and not line['bullet'] and line['top']-blocks[-1]['bottom']<12 and not blocks[-1]['bold']:
            blocks[-1]['text'] += ' ' + line['text']
            blocks[-1]['bottom'] = line['bottom']
        else:
            blocks.append(dict(line))
    return blocks

def merge_category(rows,col=0):
    spans=[]
    start=1
    for ri in range(2,len(rows)+1):
        if ri==len(rows) or clean(rows[ri][col])!=clean(rows[start][col]):
            if ri-start>1:
                spans.append(((col,start),(col,ri-1)))
                for j in range(start+1,ri): rows[j][col]=''
            start=ri
    return spans

def narratives(page, excluded=()):
    return [para(b['text'], 'heading' if b['bold'] else ('bullet' if b['bullet'] else 'body')) for b in paragraph_blocks(page,excluded)]

def general_tables(code, doc, width):
    story=[]
    if code=='B':
        story += [para('Alberta designated trades | August 2025','small'), para('Source: tradesecrets.alberta.ca/trades-in-alberta/designated-trades-profiles/','small','https://tradesecrets.alberta.ca/trades-in-alberta/designated-trades-profiles/'), Spacer(1,8)]
        rows=[]
        for i,p in enumerate(doc.pages):
            r,_=extracted(p,start=1 if i==0 else 0)
            rows+=r
        story += [make_table([['Trade','Classroom instruction','Red Seal','Compulsory']]+rows,[width*.64,width*.15,width*.10,width*.11], centercols=(1,2,3),padding=3)]
    elif code=='C':
        for i,p in enumerate(doc.pages):
            if i==0:
                story.append(heading('Companies with Scholarships/Bursaries (Except Employee only)'))
            if i<4:
                table=p.find_tables()[0]
                raw=table.extract()
                cols=[1,2,3] if len(raw[0])==4 else [0,1,2]
                r,u=extracted(p,cols=cols,start=0 if i==2 else 1)
                merged, merged_urls=[],{}
                for ri,row in enumerate(r,1):
                    if not clean(row[0]) and merged:
                        # A source grid line occasionally splits one URL across two rows.
                        for ci,value in enumerate(row):
                            if value:
                                merged[-1][ci]=str(merged[-1][ci] or '')+'\n'+str(value)
                        continue
                    if not clean(row[0]): continue
                    merged.append(row)
                    for ci in range(len(row)):
                        if (ri,ci) in u: merged_urls[(len(merged),ci)]=u[(ri,ci)]
                r,u=merged,merged_urls
                if i==0:
                    combined,urls=[],{}
                offset=len(combined)
                urls.update({(ri+offset,ci):uri for (ri,ci),uri in u.items()})
                combined+=r
                if i==3:
                    story.append(make_table([['Company','Source','Primary fields / targets']]+combined,[width*.24,width*.49,width*.27],urlcols=(1,),uris=urls,size=8.6,padding=4))
                    story.append(PageBreak())
            elif i in (4,5):
                raw=p.extract_tables()[0]
                if i==4: foundations={}
                # Each source column is its own regional list. Treat the all-caps
                # province labels as section changes rather than fixed column headings.
                for ci in range(3):
                    region=None
                    for row in raw:
                        value=clean(row[ci])
                        if value.isupper():
                            region=value
                            foundations.setdefault(region,[])
                        elif value:
                            if region is None: raise ValueError('Foundation missing regional heading')
                            foundations[region].append(value)
                if i==5:
                    story.append(heading('Community Foundations'))
                    for region,names in foundations.items():
                        rows=[[region,'','']]
                        rows += [names[j:j+3]+['']*(3-len(names[j:j+3])) for j in range(0,len(names),3)]
                        story.append(make_table(rows,[width/3]*3,size=8.8,padding=4,spans=[((0,0),(2,0))]))
                        story.append(Spacer(1,12))
                    story.append(PageBreak())
            else:
                story.append(heading('Sample of Public & Non-Profit Organizations with Scholarships'))
                r,u=extracted(p)
                story.append(make_table([['Organization name','Link','Scope / themes']]+r,[width*.34,width*.41,width*.25],urlcols=(1,),uris=u))
    elif code=='D':
        p=doc.pages[0]
        r,u=extracted(p,fillcols=(0,))
        rows=[['Category','Prov.','Full name','Website']]+r
        story.append(make_table(rows,[width*.18,width*.07,width*.43,width*.32],urlcols=(3,),uris=u,size=8.2,padding=3,spans=merge_category(rows)))
        story.append(Spacer(1,10))
        story += [para(row[0],'small') for row in p.extract_tables()[1]]
    elif code=='E':
        story += [para('Source: Taxtips - Glossary age of Majority','small','https://www.taxtips.ca/glossary/age-of-majority.htm'), Spacer(1,8), para('Definition: The age a person is considered an adult, can legally enter contracts, and when parental, child support and guardianship obligations end.'), Spacer(1,10)]
        raw=doc.pages[0].extract_tables()[0]
        story.append(make_table(raw,[width*.68,width*.16,width*.16],centercols=(1,2),padding=9,size=10))
    elif code in ('F','I'):
        for i,p in enumerate(doc.pages):
            if i:
                story.append(PageBreak())
            r,u=extracted(p,fillcols=(0,))
            if code=='F':
                rows=[['Chapter','Sponsor','Funding source','No.']]+r
                story.append(make_table(rows,[width*.23,width*.11,width*.60,width*.06],size=8.4,padding=3,spans=merge_category(rows)))
                if i==2:
                    story += [heading('Summary Count by Sponsor Type'), make_table(p.extract_tables()[1],[width*.85,width*.15],padding=5)]
                    # The source's final "Combinations 7" row is just below its table border.
                    story.append(para('Combinations: 7','small'))
            else:
                if i==0:
                    story.append(para('No contributions needed','small'))
                rows=[['Chapter','No.','Funding source']]+r
                story.append(make_table(rows,[width*.26,width*.07,width*.67],size=8.6,padding=3,spans=merge_category(rows)))
                if i==1:
                    story += [Spacer(1,10),para('(1) Includes direct benefits for children & indirect for families (any increase to after tax family income).','small')]
    elif code=='G':
        rows,urls=[],{}
        for p in doc.pages:
            r,u=extracted(p,cols=[1,2,3,4],start=3,fillcols=(0,2,3))
            offset=len(rows)
            urls.update({(ri+offset,ci):uri for (ri,ci),uri in u.items()})
            rows+=r
        # Correct only line wrapping inside this word; do not change any credential.
        rows=[[v.replace('Salespers\non','Salesperson') if isinstance(v,str) else v for v in r] for r in rows]
        story.append(make_table([['Private sector expert','Certif.','Professional association','Website']]+rows,[width*.24,width*.09,width*.39,width*.28],urlcols=(3,),uris=urls))
    elif code=='H':
        p=doc.pages[0]
        r,u=extracted(p)
        story.append(make_table([['Organization name','Target audience','Website']]+r,[width*.40,width*.25,width*.35],urlcols=(2,),uris=u,padding=3,size=8.2))
        story.append(heading('Other Financial Literacy Training Resources'))
        for row in p.extract_tables()[1]:
            if row[0].startswith('www.'):
                story.append(para(row[0],'small','https://'+url_text(row[0])))
            else:
                story.append(para('- '+row[0],'bullet'))
    return story

def tax_matrix(doc,width):
    story=[]
    raw=doc.pages[0].extract_tables()[0]
    for p in doc.pages[1:]: raw+=p.extract_tables()[0][2:]
    groups=[['Funding source','Avoid tax','','Decrease tax','','','','','Split income','','','Defer tax','']]
    labels=['','0% tax income','0% tax benefit','Ded. contrib.','Ded. expenses','Low tax rate','Ref. tax credit','Non-ref. tax credit','1st gen. income','>1st gen. income','Capital gains','Income','Capital gains']
    rows=groups+[labels]+raw[2:]
    if rows:
        spans=[((0,0),(0,1)),((1,0),(2,0)),((3,0),(7,0)),((8,0),(10,0)),((11,0),(12,0))]
        for ri,row in enumerate(rows[2:],2):
            if row[1] and len(clean(row[1]))>3:
                spans.append(((1,ri),(12,ri)))
        table=make_table(rows,[width*.35]+[width*.65/12]*12,header=2,centercols=tuple(range(1,13)),spans=spans,size=7.7,padding=3)
        wrapped=['','0%<br/>tax<br/>inc.','0%<br/>tax<br/>ben.','Ded.<br/>con.','Ded.<br/>exp.','Low<br/>tax<br/>rate','Ref.<br/>tax<br/>cr.','Non-ref.<br/>tax<br/>cr.','1st<br/>gen.<br/>inc.','&gt;1st<br/>gen.<br/>inc.','Cap.<br/>gains','Inc.','Cap.<br/>gains']
        for ci,value in enumerate(wrapped):
            table._cellvalues[1][ci]=Paragraph(value,ParagraphStyle('taxhead',parent=STYLES['th'],fontSize=6.8,leading=9.5,alignment=TA_CENTER))
        story.append(table)
        story += [Spacer(1,7),para('Inc. = income; Ben. = benefit; Ded. = deduction; Con. = contributions; Exp. = expenses; Ref. = refundable; Cr. = credit; Gen. = generation; Cap. = capital. Marks and conditional notes retain the original classifications.','small')]
    return story

def demographic_matrix(doc,width):
    story=[]
    labels=['Funding source','Parents','Grandparents','High school students','Post-sec. students','Adults &/or spouses','Indigenous people','People with disabilities','Youth in care','Athletes','Immigrants','Veterans']
    rows=[labels]
    selected=[]
    for i,p in enumerate(doc.pages):
        original=p.find_tables()[0]
        raw=original.extract()
        offset=len(rows)-1
        for ri,row in enumerate(raw[1:],1):
            values=[row[0]]+['']*11
            for ci,bbox in enumerate(original.rows[ri].cells[1:],1):
                if not bbox: continue
                x0,t,x1,b=bbox
                cx,cy=(x0+x1)/2,(t+b)/2
                filled=any(rect.get('fill') and isinstance(rect.get('non_stroking_color'),(tuple,list)) and len(rect['non_stroking_color'])==3 and rect['non_stroking_color'][1]>.5 and rect['non_stroking_color'][0]<.9 and rect['x0']<=cx<=rect['x1'] and rect['top']<=cy<=rect['bottom'] for rect in p.rects)
                if filled:
                    values[ci]='X'
                    selected.append((ci,ri+offset))
            rows.append(values)
    table=make_table(rows,[width*.29]+[width*.71/11]*11,centercols=tuple(range(1,12)),size=8.0,padding=2.5)
    wrapped=['Funding source','Parents','Grand-<br/>parents','High school<br/>students','Post-sec.<br/>students','Adults &/or<br/>spouses','Indigenous<br/>people','People with<br/>disabilities','Youth<br/>in care','Athletes','Immigrants','Veterans']
    for ci,value in enumerate(wrapped):
        table._cellvalues[0][ci]=Paragraph(value,ParagraphStyle('demohead',parent=STYLES['th'],fontSize=6.2 if ci==10 else 6.4,leading=9.2,alignment=TA_LEFT if ci==0 else TA_CENTER))
    for ci,ri in selected:
        table.setStyle(TableStyle([('BACKGROUND',(ci,ri),(ci,ri),colors.HexColor('#ede4cd'))]))
    story.append(table)
    story += [Spacer(1,8),para('X = highlighted as applicable in the original appendix.','small')]
    return story

def student_tax(doc,width):
    story=[]
    for pi,p in enumerate(doc.pages):
        tables=p.find_tables()
        blocks=paragraph_blocks(p,[t.bbox for t in tables])
        table_inserted=False
        for b in blocks:
            if tables and not table_inserted and b['top']>tables[0].bbox[3]:
                raw=tables[0].extract()
                footnotes=[]
                if pi==1:
                    footnotes=[row[0] for row in raw[1:] if not clean(row[0]).isdigit()]
                    raw=[raw[0]]+[row for row in raw[1:] if clean(row[0]).isdigit()]
                widths=[width*.05,width*.26,width*.10,width*.15,width*.44] if pi==1 else [width*.12,width*.44,width*.18,width*.26]
                table=make_table(raw,widths,size=8.3,padding=5)
                story.append(KeepTogether(table) if pi==6 else table)
                story.extend(para(note,'small') for note in footnotes)
                story.append(Spacer(1,8))
                table_inserted=True
            text=b['text']
            # Keep URLs legible and clickable even when the source split them at a line end.
            rendered=html.escape(text)
            for link in p.hyperlinks:
                uri=link.get('uri')
                if uri and b['top']-2 <= (link['top']+link['bottom'])/2 <= b['bottom']+2:
                    if uri.startswith('http://Source:%20'):
                        uri='https://'+uri.split('%20',1)[1]
                    # Attach the source link to its whole paragraph, preserving printed words.
                    rendered=f'<link href="{html.escape(uri,quote=True)}" color="#80652d">{rendered}</link>'
                    break
            style='heading' if b['bold'] else ('bullet' if b['bullet'] else 'body')
            story.append(Paragraph(rendered,STYLES[style]))
        if tables and not table_inserted:
            raw=tables[0].extract()
            widths=[width*.05,width*.26,width*.10,width*.15,width*.44] if pi==1 else [width*.12,width*.44,width*.18,width*.26]
            table=make_table(raw,widths,size=8.3,padding=5)
            story.append(KeepTogether(table) if pi==6 else table)
        story.append(Spacer(1,5))
    return story

def resp_models(doc,reader,width):
    story=[]
    page_labels={0:'RESP Modeling Process',1:'Assumptions and scenarios',2:'Summary of Select Modeling Results',3:'Model C1 - Contributions',4:'Model C1 - Account growth',5:'Model C1 - Composition and inputs',6:'Model C15 - Contributions',7:'Model C15 - Account growth',8:'Model C15 - Composition and inputs',9:'The Big Picture - Model C',10:'Model E1 - Contributions',11:'Model E1 - Account growth',12:'Model E1 - Composition and inputs',13:'The Big Picture - Model E',14:'Model F1 - Contributions',15:'Model F1 - Account growth',16:'Model F1 - Composition and inputs',17:'Model F15 - Contributions',18:'Model F15 - Account growth',19:'Model F15 - Composition and inputs',20:'The Big Picture - Model F'}
    for pi,p in enumerate(doc.pages):
        if pi: story.append(PageBreak())
        story.append(heading(page_labels[pi]))
        tables=p.find_tables()
        excludes=[t.bbox for t in tables]
        # Images in the source are charts; their contents stay exact, including labels/data.
        images=sorted(p.images,key=lambda im:im['top'])
        blocks=paragraph_blocks(p,excludes)
        items=[]
        for b in blocks:
            if b['text']==page_labels[pi]: continue
            if pi==0 and re.match(r'^(CCB|CESG|IRR|K|Yr\.|Max\.|Min)\s*=',b['text']): continue
            style=STYLES['heading' if b['bold'] else ('bullet' if b['bullet'] else 'body')]
            if pi in (0,1) and not b['bold']:
                style=ParagraphStyle('overview',parent=style,fontSize=9.2,leading=12.8,spaceAfter=3.5)
            items.append((b['top'],para(b['text'],style)))
        for image_index,image in enumerate(images):
            bbox=(image['x0'],image['top'],image['x1'],image['bottom'])
            items.append((image['top'],original_figure(reader.pages[pi],image_index,width,185 if tables else (280 if len(blocks)>5 else 365))))
        for t in tables:
            raw=t.extract()
            label=raw[0][0]
            if pi==0:
                rr=[raw[2]]+[row for row in raw[3:] if any(clean(v) for v in row)]
                last=''
                for row in rr[1:]:
                    if row[0] is None: row[0]=last
                    elif row[0]: last=row[0]
                obj=make_table(rr,[width*.10,width*.10,width*.80],spans=merge_category(rr),size=7.8,padding=2)
            elif pi==1:
                obj=make_table(raw[2:],[width*.39,width*.15,width*.15,width*.14,width*.17],size=8.2,padding=5)
            elif pi==2:
                rr=[['Ref','RESP question / parameter','Start year','Low income','Medium income','High income']]
                previous=''
                for row in raw[4:]:
                    if row[0]: previous=row[0]
                    rr.append([previous]+row[1:])
                obj=make_table(rr,[width*.07,width*.43,width*.08,width*.14,width*.14,width*.14],size=8,padding=5)
            else:
                rr=[['Assumption / input','Value']]+raw[1:]
                spans=[((0,ri),(1,ri)) for ri,row in enumerate(rr) if clean(row[0])=='Performance:']
                obj=make_table(rr,[width*.76,width*.24],spans=spans,size=8.0,padding=2.5)
            items.append((t.bbox[1],heading(label)))
            items.append((t.bbox[1]+.1,obj))
        for _,item in sorted(items,key=lambda pair:pair[0]):
            story.append(item)
            if not isinstance(item,Paragraph) or not getattr(item.style,'keepWithNext',False):
                story.append(Spacer(1,3))
        if pi==0:
            abbr=[[b['text'].split('=',1)[0].strip(),b['text'].split('=',1)[1].strip()] for b in blocks if re.match(r'^(CCB|CESG|IRR|K|Yr\.|Max\.|Min)\s*=',b['text'])]
            story.append(make_table(abbr,[width*.15,width*.85],header=False,size=8,padding=1.5))
    return story

def build_all(input_assets,output_assets):
    output_assets.mkdir(parents=True,exist_ok=True)
    report=[]
    for code in TITLES:
        matches=list(input_assets.glob(f'*-Appendix-{code}-*.pdf'))
        if len(matches)!=1: raise ValueError(f'Expected one source PDF for {code}, got {len(matches)}')
        source=matches[0]
        output=output_assets/source.name
        if source.resolve()==output.resolve(): raise ValueError('Input and output paths must differ')
        size=landscape(letter) if code in ('C','G','K','M') else letter
        width=size[0]-84
        with pdfplumber.open(source) as original:
            if code=='K': story=tax_matrix(original,width)
            elif code=='M': story=demographic_matrix(original,width)
            elif code=='J': story=student_tax(original,width)
            elif code=='L': story=resp_models(original,PdfReader(source),width)
            else: story=general_tables(code,original,width)
            if not story: raise ValueError('Empty appendix '+code)
            writer=SimpleDocTemplate(str(output),pagesize=size,leftMargin=42,rightMargin=42,topMargin=136 if size[0]==612 else 133,bottomMargin=57,title='Appendix '+code+' - '+TITLES[code],author='Canadian GRADS',subject='Canadian GRADS book appendix',pageCompression=1,invariant=1)
            chrome=Header(code,size)
            writer.build(story,onFirstPage=chrome,onLaterPages=chrome)
        result=PdfReader(output)
        if result.get_fields(): raise ValueError('Unexpected interactive field')
        report.append(dict(code=code,filename=output.name,pages=len(result.pages),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
        print(f'Appendix {code}: {len(result.pages)} pages, {output.stat().st_size:,} bytes',flush=True)
    (output_assets/'appendix-design-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=='__main__':
    build_all(Path(sys.argv[1]),Path(sys.argv[2]))
