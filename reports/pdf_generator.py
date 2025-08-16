"""
reports/pdf_generator.py
Helpers for receipts & report PDF generation (fpdf2).
"""
import os
from fpdf import FPDF
from datetime import datetime

RECEIPT_DIR = "receipts"
os.makedirs(RECEIPT_DIR, exist_ok=True)


def format_receipt_text(store_name, invoice_no, cart_items, subtotal, paid, change, footer):
    lines = []
    lines.append(store_name)
    lines.append(f"Invoice No: {invoice_no}")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-" * 48)
    lines.append(f"{'No':<3} {'Item':<24} {'Qty':>3} {'Price':>8} {'Total':>8}")
    lines.append("-" * 48)
    for idx, it in enumerate(cart_items, start=1):
        name = it['name'] if len(it['name']) <= 24 else it['name'][:21] + "..."
        lines.append(f"{idx:<3} {name:<24} {it['qty']:>3} {it['unit_price']:>8.2f} {it['line_total']:>8.2f}")
    lines.append("-" * 48)
    lines.append(f"{'Subtotal:':>36} {subtotal:>8.2f}")
    lines.append(f"{'Paid:':>36} {paid:>8.2f}")
    lines.append(f"{'Change:':>36} {change:>8.2f}")
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def save_receipt_pdf(store_name, invoice_no, cart_items, subtotal, paid, change, footer):
    filename = f"{invoice_no}.pdf"
    path = os.path.join(RECEIPT_DIR, filename)
    try:
        pdf = FPDF(unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 8, store_name, ln=True, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 5, f"Invoice No: {invoice_no}", ln=True, align="L")
        pdf.cell(0, 5, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="L")
        pdf.ln(4)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(10, 6, "No", border=0)
        pdf.cell(80, 6, "Item", border=0)
        pdf.cell(20, 6, "Qty", border=0, align="R")
        pdf.cell(30, 6, "Unit", border=0, align="R")
        pdf.cell(30, 6, "Total", border=0, align="R")
        pdf.ln(8)
        pdf.set_font("Arial", size=10)
        for idx, it in enumerate(cart_items, start=1):
            pdf.cell(10, 6, str(idx), border=0)
            pdf.cell(80, 6, it['name'][:40], border=0)
            pdf.cell(20, 6, str(it['qty']), border=0, align="R")
            pdf.cell(30, 6, f"{it['unit_price']:.2f}", border=0, align="R")
            pdf.cell(30, 6, f"{it['line_total']:.2f}", border=0, align="R")
            pdf.ln(6)
        pdf.ln(4); pdf.line(100, pdf.get_y(), 200, pdf.get_y()); pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, f"Subtotal: PKR {subtotal:.2f}", ln=True, align="R")
        pdf.cell(0, 6, f"Paid: PKR {paid:.2f}", ln=True, align="R")
        pdf.cell(0, 6, f"Change: PKR {change:.2f}", ln=True, align="R")
        pdf.ln(8); pdf.set_font("Arial", size=10); pdf.multi_cell(0, 6, footer, align="C")
        pdf.output(path)
        return path
    except Exception:
        # fallback to text receipt
        txt_path = os.path.join(RECEIPT_DIR, f"{invoice_no}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(format_receipt_text(store_name, invoice_no, cart_items, subtotal, paid, change, footer))
        return txt_path
