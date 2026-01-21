# report_utils.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_daily_pdf(
    filename,
    date,
    loss_24h,
    loss_yesterday,
    actions_df
):
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    c = canvas.Canvas(filename, pagesize=A4)
    w, h = A4

    logo_path = "assets/logo.png"

    if os.path.exists(logo_path):
        c.drawImage(
            logo_path,
            50,
            h - 80,
            width=50,
            height=50,
            preserveAspectRatio=True,
            mask="auto"
        )

    c.setFont("Helvetica-Bold", 16)
    c.drawString(110, h - 55, "HVAC ENERGY DAILY REPORT")


    c.setFont("Helvetica", 11)
    c.drawString(50, h - 90, f"Date: {date}")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        50,
        h - 165,
        "Top actions below represent the largest contributors to the last 24h loss, not the full sum."
    )

    c.drawString(50, h - 150, f"Yesterday: Rs. {int(loss_yesterday):,}")

    y = h - 190
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Top Actions")
    y -= 25

    c.setFont("Helvetica", 11)
    for _, r in actions_df.iterrows():
        c.drawString(
            60,
            y,
            f"- {r['Type']} | {r['Asset']} | Rs. {int(r['Cost']):,}"
        )
        y -= 18

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        50,
        40,
        "Advisory analytics only. No automated control actions performed."
    )

    c.save()
