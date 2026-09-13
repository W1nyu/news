"""A4 morning brief: section overview and a slim research-style margin."""
from pathlib import Path
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                               Spacer, PageBreak, NextPageTemplate, KeepTogether,
                               Table, TableStyle, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
TEAL = HexColor('#008b88')
INK = HexColor('#253630')
GRAY = HexColor('#77847d')
LINE = HexColor('#dbe5df')


def build_pdf(report):
    pdfmetrics.registerFont(TTFont('Korean', 'C:/Windows/Fonts/malgun.ttf'))
    pdfmetrics.registerFont(TTFont('KoreanBold', 'C:/Windows/Fonts/malgunbd.ttf'))
    target = ROOT / 'dist/reports' / f"{report['date']}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp.pdf')
    width, height = A4
    body = ParagraphStyle('body', fontName='Korean', fontSize=10, leading=17,
                          textColor=INK, wordWrap='CJK', spaceAfter=6)
    title = ParagraphStyle('title', parent=body, fontName='KoreanBold', fontSize=12,
                           leading=19, spaceAfter=8, keepWithNext=True)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=12, textColor=GRAY)
    label = ParagraphStyle('label', parent=body, fontName='KoreanBold', textColor=TEAL)
    doc = BaseDocTemplate(str(temporary), pagesize=A4, title=f"아침 경제 브리핑 {report['date']}",
                          author='아침 경제', leftMargin=40, rightMargin=40)
    def footer(c, d):
        c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(40,42,width-40,42)
        c.setFont('Korean',8); c.setFillColor(GRAY)
        c.drawString(40,27,'아침 경제 | NAVER ECONOMY · 원문 핵심 문장 발췌')
        c.drawRightString(width-40,27,f"{report['date']}   /   {d.page}")
    def cover(c, d):
        c.setFillColor(HexColor('#f5f3ed')); c.rect(0,0,width,height,fill=1,stroke=0)
        c.setFillColor(TEAL); c.rect(40,height-65,38,4,fill=1,stroke=0)
        c.setFont('Korean',10); c.drawString(40,height-94,'MORNING ECONOMY BRIEF')
        c.setFont('KoreanBold',34); c.setFillColor(INK); c.drawString(40,height-143,'하루의 경제, 한눈에')
        c.setFont('Korean',11); c.setFillColor(GRAY)
        c.drawString(42,height-173,report['date']+'  |  네이버 경제 8개 섹션')
        footer(c,d)
    templates=[PageTemplate(id='cover',frames=[Frame(40,66,width-80,height-275,
                leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=cover)]
    story=[Paragraph('오늘의 분야별 헤드라인',label),Spacer(1,12)]
    for topic in report['topics']:
        articles=topic['articles']
        headline=articles[0]['title'] if articles else '검증 기준을 통과한 기사 없음'
        headline=escape(headline)
        if articles: headline=f'<link href="#section-{topic["id"]}" color="#253630">{headline}</link>'
        table=Table([[Paragraph(escape(topic['name']),label),Paragraph(headline,body),
                      Paragraph(f'{len(articles)}건',small)]],colWidths=[86,width-208,42])
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),9),
                                   ('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,-1),.5,LINE)]))
        story.append(table)
    story += [Spacer(1,18),Paragraph('위의 분야별 헤드라인을 누르면 해당 섹션으로 이동합니다. 기사 제목의 키워드 가중치와 네이버 목록 순서로 선별한 뉴스입니다. 투자 의견이나 매매 추천을 제공하지 않습니다.',small)]
    bookmarked=set()
    for topic in report['topics']:
        if not topic['articles']: continue
        def section_page(c,d,t=topic):
            footer(c,d)
            c.setFillColor(TEAL); c.rect(130,64,3,height-106,fill=1,stroke=0)
            c.setFillColor(HexColor('#f2f7f4'));c.rect(40,64,90,height-106,fill=1,stroke=0)
            c.setFillColor(TEAL);c.setFont('KoreanBold',13);c.drawString(50,height-86,t['name'])
            c.setFont('Korean',9);c.setFillColor(GRAY);c.drawString(50,height-110,f"{len(t['articles'])}개 기사")
            c.drawString(50,height-129,report['date'])
            p=Paragraph('네이버 경제<br/>섹션 '+escape(t['id'])+'<br/><br/>무료 공개 기사<br/>발행 시각 확인<br/><br/>원문 핵심<br/>문장 발췌',small)
            _,h=p.wrap(70,400);p.drawOn(c,50,height-171-h)
            c.setFont('Korean',8);c.setFillColor(TEAL);c.drawRightString(width-40,height-30,'아침 경제 · MORNING BRIEF')
            if t['id'] not in bookmarked:
                c.bookmarkPage('section-'+t['id']);c.addOutlineEntry(t['name'],'section-'+t['id'])
                bookmarked.add(t['id'])
        template_id='section-'+topic['id']
        templates.append(PageTemplate(id=template_id,frames=[Frame(153,64,width-193,height-119,
                         leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=section_page))
        story += [NextPageTemplate(template_id),PageBreak(),
                  Paragraph(escape(topic['name']),ParagraphStyle('section',parent=title,fontSize=25,leading=34,textColor=TEAL)),
                  Paragraph('주요 경제 뉴스 | DAILY NEWS SUMMARY',small),Spacer(1,18)]
        for i,article in enumerate(topic['articles'],1):
            url=escape(article['url'],{'"':'&quot;'})
            stamp=datetime.fromisoformat(article['published_at']).strftime('%Y.%m.%d %H:%M')
            block=[Paragraph(f'{i:02d}  '+escape(article['title']),title)]
            block += [Paragraph(escape(s),body) for s in article['summary']]
            block += [Spacer(1,3),Paragraph(escape(article['source']+' | '+stamp+' KST 발행')+f' · <link href="{url}" color="#008b88">원문 보기</link>',small),
                      Spacer(1,10),HRFlowable(width='100%',thickness=.5,color=LINE),Spacer(1,16)]
            story.append(KeepTogether(block))
    doc.addPageTemplates(templates)
    doc.build(story)
    temporary.replace(target)
    out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
    (out/'economy-report.pdf').write_bytes(target.read_bytes())
    return target
