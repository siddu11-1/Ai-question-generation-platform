"""
=============================================================================
certificates/certificate_gen.py
Description:
    Generates a downloadable PDF completion certificate for students
    who pass an exam (score >= 60%).
    
    Uses the reportlab library for PDF generation.
    Install: pip install reportlab
=============================================================================
"""

import io
from datetime import datetime


def generate_certificate(student_name: str, course_name: str,
                          score: float, date_str: str = None) -> bytes:
    """
    Generates a styled PDF certificate for a student who passed an exam.

    Args:
        student_name : Full name or username of the student
        course_name  : Name of the question bank / course completed
        score        : Final percentage score (e.g. 85.5)
        date_str     : Date string for the certificate (defaults to today)

    Returns:
        PDF file as bytes (can be used with st.download_button)
    """
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        if date_str is None:
            date_str = datetime.now().strftime("%B %d, %Y")

        # Use landscape A4 for a classic certificate look
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=60, leftMargin=60,
            topMargin=40, bottomMargin=40
        )

        styles = getSampleStyleSheet()

        # ── CUSTOM STYLES ────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "CertTitle",
            parent=styles["Title"],
            fontSize=36,
            textColor=colors.HexColor("#1a3c5e"),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold"
        )

        subtitle_style = ParagraphStyle(
            "CertSubtitle",
            parent=styles["Normal"],
            fontSize=16,
            textColor=colors.HexColor("#4a6fa5"),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName="Helvetica"
        )

        body_style = ParagraphStyle(
            "CertBody",
            parent=styles["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#333333"),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName="Helvetica"
        )

        name_style = ParagraphStyle(
            "CertName",
            parent=styles["Normal"],
            fontSize=28,
            textColor=colors.HexColor("#c0392b"),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName="Helvetica-BoldOblique"
        )

        course_style = ParagraphStyle(
            "CertCourse",
            parent=styles["Normal"],
            fontSize=20,
            textColor=colors.HexColor("#1a3c5e"),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold"
        )

        score_style = ParagraphStyle(
            "CertScore",
            parent=styles["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#27ae60"),
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold"
        )

        footer_style = ParagraphStyle(
            "CertFooter",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.gray,
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName="Helvetica-Oblique"
        )

        # ── BUILD CERTIFICATE CONTENT ────────────────────────────────────────
        story = []

        story.append(Spacer(1, 0.3 * inch))

        # Top decorative line
        story.append(HRFlowable(width="90%", thickness=3,
                                color=colors.HexColor("#1a3c5e"), spaceAfter=12))

        story.append(Paragraph("🎓 Certificate of Completion", title_style))
        story.append(Paragraph("AI-Powered Question Generation and Learning System", subtitle_style))

        story.append(HRFlowable(width="60%", thickness=1,
                                color=colors.HexColor("#4a6fa5"), spaceAfter=18))

        story.append(Paragraph("This is to proudly certify that", body_style))
        story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph(student_name.upper(), name_style))
        story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph("has successfully completed the assessment on", body_style))
        story.append(Spacer(1, 0.05 * inch))

        story.append(Paragraph(course_name, course_style))
        story.append(Spacer(1, 0.15 * inch))

        story.append(Paragraph(f"with a score of  {score:.1f}%", score_style))
        story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph(f"Date of Completion: {date_str}", body_style))
        story.append(Spacer(1, 0.3 * inch))

        # Bottom decorative line
        story.append(HRFlowable(width="90%", thickness=3,
                                color=colors.HexColor("#1a3c5e"), spaceAfter=12))

        story.append(Paragraph(
            "This certificate was generated by the AI-Powered Learning Support System. "
            "Issued automatically upon achieving a passing score of 60% or above.",
            footer_style
        ))

        # Build the PDF
        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        # Return a simple text fallback if reportlab not installed
        fallback = f"""
CERTIFICATE OF COMPLETION
==========================
Student   : {student_name}
Course    : {course_name}
Score     : {score:.1f}%
Date      : {date_str or datetime.now().strftime('%B %d, %Y')}
Status    : PASSED ✓
==========================
Install reportlab for a proper PDF certificate:
pip install reportlab
        """
        return fallback.encode("utf-8")
    except Exception as e:
        return f"Error generating certificate: {e}".encode("utf-8")
