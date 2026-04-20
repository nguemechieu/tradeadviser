from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class ReportGenerator:

    def generate_report(self, filename, trades):
        c = canvas.Canvas(filename, pagesize=letter)

        y = 750

        for trade in trades:
            line = f"{trade}"

            c.drawString(100, y, line)

            y -= 20

        c.save()
