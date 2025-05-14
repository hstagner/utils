import os
import re
from textwrap import wrap
from mrkdwn_analysis import MarkdownAnalyzer
from reportlab.lib.pagesizes import letter, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageTemplate, Frame, PageBreak
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

# ===== PAGE SETTINGS =====
PAGE_WIDTH, PAGE_HEIGHT = letter
PAGE_LEFT_MARGIN = 1.75 * inch
PAGE_RIGHT_MARGIN = 1.75 * inch
PAGE_TOP_MARGIN = 1 * inch
PAGE_BOTTOM_MARGIN = 1 * inch

# ===== CARD SETTINGS =====
CARD_WIDTH = 5 * inch
CARD_HEIGHT = 3 * inch
CARD_MARGIN = 12  # 12pt = 1/6" margin on all sides
CONTENT_WIDTH = CARD_WIDTH - 2*CARD_MARGIN
CONTENT_HEIGHT = CARD_HEIGHT - 2*CARD_MARGIN

# ===== FONT SETTINGS =====
TITLE_FONT_NAME = 'Helvetica-Bold'
BODY_FONT_NAME = 'Helvetica'
MIN_FONT_SIZE = 6
MAX_TITLE_SIZE = 12
MAX_BODY_SIZE = 10
LINE_SPACING = 1.2

# ===== FOOTER SETTINGS =====
FOOTER_HEIGHT = 36  # 0.5" (fixed)
PAGE_COL_WIDTH = 48  # Fixed width for page column (48pt = 0.67")
MAX_FOOTER_FONT_SIZE = 8
MIN_FOOTER_FONT_SIZE = 6

def auto_scale_text(text, max_width, max_height):
    """Find maximum font size that fits text in available space"""
    font_size = MAX_BODY_SIZE
    best_size = MIN_FONT_SIZE
    best_wrapped = []
    
    while font_size >= MIN_FONT_SIZE:
        avg_char_width = pdfmetrics.stringWidth("n", BODY_FONT_NAME, font_size)
        chars_per_line = int(max_width / avg_char_width)
        wrapped = wrap(text[:2000], width=chars_per_line)
        line_height = font_size * LINE_SPACING
        needed_height = len(wrapped) * line_height
        
        if needed_height <= max_height:
            return font_size, '<br/>'.join(wrapped)
        
        font_size -= 0.5
    
    # Fallback to minimum size with truncation
    wrapped = wrap(text, width=int(max_width/avg_char_width))[:int(max_height/(MIN_FONT_SIZE*LINE_SPACING))]
    return MIN_FONT_SIZE, '<br/>'.join(wrapped)

def fit_title_font(title, max_width):
    font_size = MAX_TITLE_SIZE
    while font_size >= MIN_FONT_SIZE:
        text_width = pdfmetrics.stringWidth(title, TITLE_FONT_NAME, font_size)
        if text_width <= max_width:
            return font_size
        font_size -= 1
    return MIN_FONT_SIZE

def calculate_footer_font(source_text, page_text):
    """Calculate maximum font size that fits both footer columns"""
    font_size = MAX_FOOTER_FONT_SIZE
    while font_size >= MIN_FOOTER_FONT_SIZE:
        source_width = pdfmetrics.stringWidth(source_text, BODY_FONT_NAME, font_size)
        page_width = pdfmetrics.stringWidth(page_text, BODY_FONT_NAME, font_size)
        available_source_width = CONTENT_WIDTH - PAGE_COL_WIDTH - 6  # 6pt padding
        
        if source_width <= available_source_width and page_width <= PAGE_COL_WIDTH:
            return font_size
        font_size -= 0.5  # Fine-grained scaling
    return MIN_FOOTER_FONT_SIZE

def create_card_content(card_title, quote, analysis, source, page_number):
    styles = getSampleStyleSheet()
    
    # Auto-scale title
    title_font_size = fit_title_font(card_title, CONTENT_WIDTH)
    title_height = title_font_size * LINE_SPACING + 6  # + red line
    
    # Available space for paragraphs
    para_available_height = CONTENT_HEIGHT - title_height - 12 - FOOTER_HEIGHT
    
    # Auto-scale quote and analysis
    quote_font, quote_content = auto_scale_text(quote, CONTENT_WIDTH, para_available_height/2)
    analysis_font, analysis_content = auto_scale_text(analysis, CONTENT_WIDTH, para_available_height/2)
    body_font_size = min(quote_font, analysis_font)

    # Create styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontName=TITLE_FONT_NAME,
        fontSize=title_font_size,
        leading=title_font_size * LINE_SPACING,
        alignment=1,
        spaceAfter=0
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName=BODY_FONT_NAME,
        fontSize=body_font_size,
        leading=body_font_size * LINE_SPACING,
        spaceBefore=0,
        spaceAfter=0
    )

    # Auto-scale footer
    source_text = f"Source: {source}"
    page_text = f"Page: {page_number}"
    footer_font_size = calculate_footer_font(source_text, page_text)
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName=BODY_FONT_NAME,
        fontSize=footer_font_size,
        leading=footer_font_size * 1.2,
        spaceBefore=0,
        spaceAfter=0
    )

    # Title with red line
    title_table = Table(
        [[Paragraph(f"<b>{card_title}</b>", title_style)]],
        colWidths=CONTENT_WIDTH,
        rowHeights=[title_height-2],
        style=TableStyle([
            ('LINEBELOW', (0,0), (-1,0), 1.5, colors.red),
            ('BOTTOMPADDING', (0,0), (-1,0), 6)
        ])
    )

    # Paragraph content
    para_flowables = [
        Paragraph(f"<b>Quote:</b> {quote_content}", body_style),
        Spacer(1, 6),
        Paragraph(f"<b>Analysis:</b> {analysis_content}", body_style)
    ]
    para_table = Table(
        [[para_flowables]],
        colWidths=CONTENT_WIDTH,
        rowHeights=[para_available_height],
        style=TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0)
        ])
    )

    # Footer table with auto-scaling
    footer_table = Table(
        [[
            Paragraph(f"<b>Source:</b> {source}", footer_style),
            Paragraph(f"<b>Page:</b> {page_number}", footer_style)
        ]],
        colWidths=[None, PAGE_COL_WIDTH],  # Source expands, Page fixed
        rowHeights=[FOOTER_HEIGHT],
        style=TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ])
    )

    return Table(
        [
            [title_table],
            [Spacer(1, 12)],
            [para_table],
            [footer_table]
        ],
        colWidths=CARD_WIDTH,
        rowHeights=[
            title_height,
            12,  # Spacer
            para_available_height,
            FOOTER_HEIGHT
        ],
        style=TableStyle([
            ('PADDING', (0,0), (-1,-1), CARD_MARGIN),
            ('BOTTOMPADDING', (-1,-1), (-1,-1), CARD_MARGIN)
        ])
    )

def parse_markdown(filename):
    analyzer = MarkdownAnalyzer(filename)
    headers = analyzer.identify_headers().get("Header", [])
    if not headers:
        raise ValueError(f"No headers found in {filename}")
    header_text = headers[0].get('text', '')
    page_match = re.match(r'Page\s*(\d+)\s*-\s*(.*)', header_text)
    if not page_match:
        raise ValueError(f"Header format error in {filename}")
    page_number, card_title = page_match.groups()
    paragraphs = analyzer.identify_paragraphs().get("Paragraph", [])
    source = "Unknown"
    if paragraphs:
        source_match = re.search(r'\[\[(.*?)\]\]', paragraphs[0])
        if source_match:
            source = source_match.group(1)
    blockquotes = analyzer.identify_blockquotes().get("Blockquote", [])
    quote = blockquotes[0] if blockquotes else ""
    analysis = ""
    for para in paragraphs:
        if para.strip().startswith("**Analysis:**"):
            analysis = para.replace("**Analysis:**", "").strip()
            break
    return card_title, quote, analysis, source, page_number

def avery5388_page_template():
    available_height = PAGE_HEIGHT - PAGE_TOP_MARGIN - PAGE_BOTTOM_MARGIN
    vertical_gap = (available_height - 3*CARD_HEIGHT) / 2
    return PageTemplate(
        frames=[
            Frame(PAGE_LEFT_MARGIN, PAGE_BOTTOM_MARGIN + 2*CARD_HEIGHT + 2*vertical_gap, CARD_WIDTH, CARD_HEIGHT),
            Frame(PAGE_LEFT_MARGIN, PAGE_BOTTOM_MARGIN + CARD_HEIGHT + vertical_gap, CARD_WIDTH, CARD_HEIGHT),
            Frame(PAGE_LEFT_MARGIN, PAGE_BOTTOM_MARGIN, CARD_WIDTH, CARD_HEIGHT)
        ],
        pagesize=letter
    )

def make_avery5388_pdf(md_dir, output_file):
    doc = BaseDocTemplate(
        output_file,
        pagesize=letter,
        leftMargin=0,
        rightMargin=0,
        topMargin=0,
        bottomMargin=0
    )
    doc.addPageTemplates([avery5388_page_template()])
    elements = []
    md_files = sorted([f for f in os.listdir(md_dir) if f.endswith('.md')])
    for i, md_file in enumerate(md_files):
        try:
            full_path = os.path.join(md_dir, md_file)
            card_data = parse_markdown(full_path)
            elements.append(create_card_content(*card_data))
            if (i + 1) % 3 == 0:
                elements.append(PageBreak())
        except Exception as e:
            print(f"Skipping {md_file}: {str(e)}")
    if elements and isinstance(elements[-1], PageBreak):
        elements.pop()
    doc.build(elements)

if __name__ == "__main__":
    input_directory = "/Users/hstagner/Documents/dev/bear-export/"
    output_file = "avery_5388_cards.pdf"
    make_avery5388_pdf(input_directory, output_file)
    print(f"Generated {output_file} with full auto-scaling text and footer.")
