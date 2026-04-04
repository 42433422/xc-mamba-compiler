#!/usr/bin/env python3
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def create_resume():
    doc = SimpleDocTemplate(
        "LIJIALONG_Resume.pdf",
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='NameStyle',
        parent=styles['Heading1'],
        fontSize=22,
        spaceAfter=4,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1a1a2e')
    ))
    styles.add(ParagraphStyle(
        name='ContactStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.HexColor('#4a4a6a')
    ))
    styles.add(ParagraphStyle(
        name='SectionTitle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor('#16213e'),
        borderPadding=(0, 0, 2, 0)
    ))
    styles.add(ParagraphStyle(
        name='SubTitle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=2,
        spaceBefore=6,
        textColor=colors.HexColor('#333333'),
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=4,
        leading=12,
        textColor=colors.HexColor('#333333')
    ))
    styles.add(ParagraphStyle(
        name='BulletBody',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=2,
        leading=11,
        leftIndent=12,
        textColor=colors.HexColor('#444444')
    ))

    story = []

    story.append(Paragraph("LIJIALONG", styles['NameStyle']))

    contact_info = "970882904@qq.com  |  https://github.com/42433422/xc-mamba-compiler"
    story.append(Paragraph(contact_info, styles['ContactStyle']))

    story.append(Paragraph("Technical Skills", styles['SectionTitle']))

    skills_data = [
        ['Languages:', 'Python / JavaScript'],
        ['AI Engineering:', 'LLM Fine-tuning / AI Code Generation / End-to-end Model Training'],
        ['Compiler:', 'Lexer & Parser Design / AST Construction / IR Optimization / Code Generation'],
        ['Infrastructure:', 'Git / Docker / Linux / QEMU / RISC-V64']
    ]

    for skill in skills_data:
        row = Paragraph(f"<b>{skill[0]}</b> {skill[1]}", styles['CustomBody'])
        story.append(row)

    story.append(Paragraph("Project Experience", styles['SectionTitle']))

    story.append(Paragraph("XC-to-Assembly AI Compilation", styles['SubTitle']))

    story.append(Paragraph(
        "Fine-tuned <b>Mamba SSM</b> for XC language to RISC-V64 assembly generation, replacing traditional compiler backends.",
        styles['CustomBody']
    ))

    story.append(Paragraph("<b>Technical Stack:</b>", styles['CustomBody']))
    tech_items = [
        "Base model: Mamba state space model (SSM) for sequence-to-sequence code generation",
        "Fine-tuning: LoRA + ORPO reinforcement learning",
        "Inference: Hierarchical beam search with multi-candidate expansion",
        "Validation: Automated assembly testing with QEMU"
    ]
    for item in tech_items:
        story.append(Paragraph(f"• {item}", styles['BulletBody']))

    story.append(Paragraph("<b>Results (10-sample validation):</b>", styles['CustomBody']))

    results_data = [
        ['Metric', 'Value'],
        ['Oracle runtime correctness', '100%'],
        ['Model prediction runtime correctness', '70%'],
        ['Runtime match rate', '50%'],
        ['Mean generation time', '44.4s/sample'],
        ['Median generation time', '44.2s/sample']
    ]

    results_table = Table(results_data, colWidths=[5*cm, 4*cm])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(results_table)

    story.append(Spacer(1, 8))

    story.append(Paragraph("XC Language Compiler", styles['SubTitle']))

    story.append(Paragraph(
        "A full-stack programming language with lexer, parser, AST, IR, and multi-target code generators.",
        styles['CustomBody']
    ))

    story.append(Paragraph("<b>Technical Stack:</b>", styles['CustomBody']))

    xc_items = [
        "Lexer: Regex-based tokenizer (60+ tokens)",
        "Parser: Recursive descent parser (structs, unions, switch, goto)",
        "AST: 20+ node types for full language coverage",
        "IR: Custom IR with constant folding & dead code elimination",
        "Targets: C / Rust / Mojo / RISC-V64 ASM"
    ]
    for item in xc_items:
        story.append(Paragraph(f"• {item}", styles['BulletBody']))

    story.append(Spacer(1, 10))

    story.append(Paragraph("GitHub", styles['SectionTitle']))
    story.append(Paragraph(
        "https://github.com/42433422/xc-mamba-compiler",
        styles['CustomBody']
    ))
    story.append(Paragraph(
        "XC-to-RISC-V64 AI Compiler (Mamba SSM + Oracle Hybrid)",
        styles['CustomBody']
    ))

    doc.build(story)
    print("Resume generated: LIJIALONG_Resume.pdf")

if __name__ == "__main__":
    create_resume()