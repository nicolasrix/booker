import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import re
from rich.console import Console
from rich.progress import Progress
import logging
from datetime import datetime

# Set up logging
log = logging.getLogger("pdf_generator")


class NumberedCanvas(canvas.Canvas):
    """Custom canvas to add page numbers and headers."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.page_count = 0

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        self.page_count += 1

    def save(self):
        """Add page numbers to all pages."""
        num_pages = len(self._saved_page_states)
        for (page_num, state) in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self.draw_page_number(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num, total_pages):
        """Draw page number at bottom of page."""
        self.setFont("Helvetica", 9)
        self.drawRightString(
            letter[0] - 0.75 * inch,
            0.5 * inch,
            f"Page {page_num} of {total_pages}"
        )

        # Add generation timestamp on first page
        if page_num == 1:
            self.drawString(
                0.75 * inch,
                0.5 * inch,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )


def parse_content_sections(text):
    """Parse the text into different content sections (tables, text, OCR)."""
    sections = []
    current_section = {'type': 'text', 'content': '', 'page': None}

    lines = text.split('\n')

    for line in lines:
        line = line.strip()

        # Detect table start
        if re.match(r'$TABLE \d+.*?$', line):
            # Save current section if it has content
            if current_section['content'].strip():
                sections.append(current_section)

            # Extract table info
            table_match = re.search(r'$TABLE (\d+).*?Page (\d+).*?$', line)
            table_num = table_match.group(1) if table_match else "Unknown"
            page_num = table_match.group(2) if table_match else "Unknown"

            current_section = {
                'type': 'table',
                'content': '',
                'table_num': table_num,
                'page': page_num
            }
            continue

        # Detect table end
        elif re.match(r'$/TABLE.*?$', line):
            if current_section['type'] == 'table':
                sections.append(current_section)
                current_section = {'type': 'text', 'content': '', 'page': None}
            continue

        # Detect text section start
        elif re.match(r'$TEXT - Page (\d+)$', line):
            if current_section['content'].strip():
                sections.append(current_section)

            page_match = re.search(r'Page (\d+)', line)
            page_num = page_match.group(1) if page_match else "Unknown"

            current_section = {
                'type': 'text',
                'content': '',
                'page': page_num
            }
            continue

        # Detect OCR section start
        elif re.match(r'$OCR - Page (\d+)$', line):
            if current_section['content'].strip():
                sections.append(current_section)

            page_match = re.search(r'Page (\d+)', line)
            page_num = page_match.group(1) if page_match else "Unknown"

            current_section = {
                'type': 'ocr',
                'content': '',
                'page': page_num
            }
            continue

        # Detect section end
        elif re.match(r'$/(TEXT|OCR)$', line):
            if current_section['content'].strip():
                sections.append(current_section)
                current_section = {'type': 'text', 'content': '', 'page': None}
            continue

        # Add content to current section
        else:
            if line:  # Only add non-empty lines
                current_section['content'] += line + '\n'

    # Add final section if it has content
    if current_section['content'].strip():
        sections.append(current_section)

    return sections


def create_table_from_markdown(table_content):
    """Convert markdown table to ReportLab Table."""
    lines = [line.strip() for line in table_content.split('\n') if line.strip()]

    # Filter out markdown table separators
    data_lines = []
    for line in lines:
        if not re.match(r'^[\|\-\+\s]+$', line):  # Skip separator lines
            data_lines.append(line)

    if not data_lines:
        return None

    # Parse table data
    table_data = []
    for line in data_lines:
        # Split by | and clean up
        cells = [cell.strip() for cell in line.split('|')]
        # Remove empty cells at start/end (from leading/trailing |)
        if cells and not cells[0]:
            cells = cells[1:]
        if cells and not cells[-1]:
            cells = cells[:-1]

        if cells:  # Only add non-empty rows
            table_data.append(cells)

    if not table_data:
        return None

    # Create ReportLab table
    table = Table(table_data)

    # Style the table
    table_style = TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),

        # Data rows styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ])

    table.setStyle(table_style)
    return table


def text_to_pdf(text, output_path, title="Cleaned Document"):
    """Convert cleaned text (with tables) to a formatted PDF."""
    console = Console()

    console.print(f"[cyan]Creating PDF: {output_path}[/cyan]")

    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        canvasmaker=NumberedCanvas
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkred
    )

    text_style = ParagraphStyle(
        'CustomText',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        leftIndent=0,
        rightIndent=0
    )

    ocr_style = ParagraphStyle(
        'OCRText',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=6,
        alignment=TA_LEFT,
        leftIndent=20,
        textColor=colors.darkgreen,
        fontName='Helvetica-Oblique'
    )

    # Parse content into sections
    console.print("[yellow]Parsing content sections...[/yellow]")
    sections = parse_content_sections(text)
    console.print(f"Found {len(sections)} content sections")

    # Count sections by type
    section_counts = {}
    for section in sections:
        section_type = section['type']
        section_counts[section_type] = section_counts.get(section_type, 0) + 1

    console.print(f"Section breakdown: {section_counts}")

    # Build PDF content
    story = []

    # Add title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 20))

    # Add document info
    info_text = f"Document processed on {datetime.now().strftime('%B %d, %Y at %H:%M')}<br/>"
    info_text += f"Total sections: {len(sections)} | "
    info_text += " | ".join([f"{k.title()}: {v}" for k, v in section_counts.items()])
    story.append(Paragraph(info_text, styles['Normal']))
    story.append(Spacer(1, 30))

    # Process sections
    with Progress() as progress:
        task = progress.add_task("[green]Building PDF content...", total=len(sections))

        for i, section in enumerate(sections):
            section_type = section['type']
            content = section['content'].strip()

            if not content:
                progress.advance(task)
                continue

            # Add page reference
            if section.get('page'):
                page_ref = f"[Original Page {section['page']}]"
                story.append(Paragraph(page_ref, styles['Caption']))

            if section_type == 'table':
                # Add table heading
                table_title = f"Table {section.get('table_num', 'Unknown')}"
                story.append(Paragraph(table_title, heading_style))

                # Create and add table
                table = create_table_from_markdown(content)
                if table:
                    story.append(table)
                    story.append(Spacer(1, 20))
                else:
                    # Fallback: add as preformatted text
                    story.append(Paragraph("Table data (raw):", styles['Heading3']))
                    for line in content.split('\n'):
                        if line.strip():
                            story.append(Paragraph(line, styles['Code']))
                    story.append(Spacer(1, 20))

            elif section_type == 'text':
                # Add regular text
                story.append(Paragraph("Text Content", heading_style))
                paragraphs = content.split('\n\n')
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        # Clean up the text for PDF
                        para = para.replace('\n', ' ')
                        story.append(Paragraph(para, text_style))
                story.append(Spacer(1, 15))

            elif section_type == 'ocr':
                # Add OCR content
                story.append(Paragraph("OCR Content", heading_style))
                paragraphs = content.split('\n\n')
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        para = para.replace('\n', ' ')
                        story.append(Paragraph(para, ocr_style))
                story.append(Spacer(1, 15))

            progress.advance(task)

    # Build PDF
    console.print("[yellow]Generating PDF...[/yellow]")
    try:
        doc.build(story)
        console.print(f"[green]✓ PDF created successfully: {output_path}[/green]")

        # Get file size
        file_size = os.path.getsize(output_path)
        console.print(f"[blue]File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)[/blue]")

        return True

    except Exception as e:
        console.print(f"[red]Error creating PDF: {e}[/red]")
        log.error(f"PDF generation failed: {e}")
        return False


def create_summary_pdf(text, output_path, title="Document Summary"):
    """Create a summary PDF with statistics and sample content."""
    console = Console()

    sections = parse_content_sections(text)

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 30))

    # Statistics
    story.append(Paragraph("Document Statistics", styles['Heading1']))

    section_counts = {}
    total_chars = 0
    for section in sections:
        section_type = section['type']
        section_counts[section_type] = section_counts.get(section_type, 0) + 1
        total_chars += len(section['content'])

    stats = [
        f"Total sections: {len(sections)}",
        f"Total characters: {total_chars:,}",
        f"Tables found: {section_counts.get('table', 0)}",
        f"Text sections: {section_counts.get('text', 0)}",
        f"OCR sections: {section_counts.get('ocr', 0)}"
    ]

    for stat in stats:
        story.append(Paragraph(stat, styles['Normal']))

    story.append(Spacer(1, 30))

    # Sample tables
    if section_counts.get('table', 0) > 0:
        story.append(Paragraph("Sample Tables", styles['Heading1']))

        table_sections = [s for s in sections if s['type'] == 'table'][:3]  # First 3 tables
        for section in table_sections:
            story.append(
                Paragraph(f"Table {section.get('table_num', 'Unknown')} (Page {section.get('page', 'Unknown')})",
                          styles['Heading2']))

            # Show first few lines of table
            lines = section['content'].split('\n')[:5]
            for line in lines:
                if line.strip():
                    story.append(Paragraph(line, styles['Code']))
            story.append(Spacer(1, 20))

    doc.build(story)
    console.print(f"[green]✓ Summary PDF created: {output_path}[/green]")


# Utility functions
def batch_convert_texts_to_pdfs(text_files_dir, output_dir):
    """Convert multiple text files to PDFs."""
    console = Console()
    os.makedirs(output_dir, exist_ok=True)

    text_files = [f for f in os.listdir(text_files_dir) if f.endswith('.txt')]

    console.print(f"Found {len(text_files)} text files to convert")

    for text_file in text_files:
        text_path = os.path.join(text_files_dir, text_file)
        pdf_name = os.path.splitext(text_file)[0] + '_cleaned.pdf'
        pdf_path = os.path.join(output_dir, pdf_name)

        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()

        text_to_pdf(text, pdf_path, title=f"Cleaned: {os.path.splitext(text_file)[0]}")
