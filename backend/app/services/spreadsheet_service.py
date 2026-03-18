"""
FiscalIA — Servicio de hojas de cálculo
Leer, editar y generar Excel/CSV para autónomos españoles
"""
import io
import csv
import json
from datetime import datetime
from typing import Optional

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter


# ── Paleta corporativa FiscalIA ────────────────────────────────
NAVY     = "0D1B2A"
GOLD     = "C9A84C"
GOLD_L   = "F5E9C4"
WHITE    = "FFFFFF"
GREEN    = "1A7A4A"
RED_     = "C0392B"
GREY_L   = "F5F5F5"
GREY_D   = "CCCCCC"

def _header_fill(color=NAVY):   return PatternFill("solid", start_color=color, fgColor=color)
def _font(bold=False, color="000000", size=11):
    return Font(name="Arial", bold=bold, color=color, size=size)
def _border():
    s = Side(style="thin", color=GREY_D)
    return Border(left=s, right=s, top=s, bottom=s)
def _center(): return Alignment(horizontal="center", vertical="center")
def _right():  return Alignment(horizontal="right",  vertical="center")
def _left():   return Alignment(horizontal="left",   vertical="center", wrap_text=True)

EUR_FMT   = '#,##0.00 €;(#,##0.00 €);"-"'
PCT_FMT   = '0.0%;(0.0%);"-"'
DATE_FMT  = 'DD/MM/YYYY'


# ══════════════════════════════════════════════════════════════
#  LEER — parse Excel / CSV to text for AI
# ══════════════════════════════════════════════════════════════

def parse_spreadsheet_for_ai(file_bytes: bytes, filename: str) -> str:
    """
    Reads an Excel or CSV file and returns a structured text
    summary that the AI can understand and analyze.
    """
    ext = filename.lower().split(".")[-1]

    if ext == "csv":
        return _parse_csv(file_bytes)
    elif ext in ("xlsx", "xls", "xlsm"):
        return _parse_excel(file_bytes)
    else:
        raise ValueError(f"Formato no soportado: {ext}")


def _parse_csv(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return "El archivo CSV está vacío."

    headers = rows[0]
    data_rows = rows[1:]

    lines = [f"ARCHIVO CSV — {len(data_rows)} filas, {len(headers)} columnas"]
    lines.append(f"COLUMNAS: {' | '.join(headers)}")
    lines.append("")

    # Summary stats per column (numeric)
    for col_idx, col_name in enumerate(headers):
        values = []
        for row in data_rows:
            if col_idx < len(row):
                try:
                    values.append(float(row[col_idx].replace("€","").replace(",",".").strip()))
                except ValueError:
                    pass
        if values:
            lines.append(f"{col_name}: total={sum(values):.2f}, promedio={sum(values)/len(values):.2f}, min={min(values):.2f}, max={max(values):.2f}")

    lines.append("")
    lines.append("PRIMERAS 20 FILAS:")
    for i, row in enumerate(data_rows[:20]):
        lines.append(f"  Fila {i+1}: " + " | ".join(f"{headers[j] if j < len(headers) else j}={v}" for j,v in enumerate(row)))

    if len(data_rows) > 20:
        lines.append(f"  ... y {len(data_rows)-20} filas más")

    return "\n".join(lines)


def _parse_excel(file_bytes: bytes) -> str:
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines = [f"ARCHIVO EXCEL — {len(wb.sheetnames)} hoja(s): {', '.join(wb.sheetnames)}"]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lines.append(f"\n== HOJA: {sheet_name} ==")

        # Get all data
        data = []
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                data.append([str(c) if c is not None else "" for c in row])

        if not data:
            lines.append("  (hoja vacía)")
            continue

        lines.append(f"  Dimensiones: {ws.max_row} filas × {ws.max_column} columnas")

        # Headers (first non-empty row)
        headers = data[0]
        lines.append(f"  Columnas: {' | '.join(h for h in headers if h)}")

        # Numeric summary
        for col_idx, col_name in enumerate(headers):
            if not col_name:
                continue
            values = []
            for row in data[1:]:
                if col_idx < len(row):
                    try:
                        v = float(str(row[col_idx]).replace("€","").replace(",",".").strip())
                        values.append(v)
                    except (ValueError, AttributeError):
                        pass
            if values:
                lines.append(f"  {col_name}: total={sum(values):.2f}, promedio={sum(values)/len(values):.2f}, min={min(values):.2f}, max={max(values):.2f}")

        # First 15 data rows
        lines.append("  Datos (primeras 15 filas):")
        for i, row in enumerate(data[1:16]):
            row_str = " | ".join(f"{headers[j] if j < len(headers) else j}={v}" for j,v in enumerate(row) if v)
            lines.append(f"    Fila {i+1}: {row_str}")

        if len(data) > 16:
            lines.append(f"    ... y {len(data)-16} filas más")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  EDITAR — add rows / columns to existing Excel
# ══════════════════════════════════════════════════════════════

def add_rows_to_excel(file_bytes: bytes, new_rows: list[dict], sheet_name: Optional[str] = None) -> bytes:
    """
    Adds new rows to an existing Excel file.
    new_rows: list of dicts where keys match column headers.
    """
    wb = load_workbook(io.BytesIO(file_bytes))
    ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

    # Get headers from first row
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

    # Style for new rows
    fill_new = PatternFill("solid", start_color="E8F4E8", fgColor="E8F4E8")

    for row_data in new_rows:
        next_row = ws.max_row + 1
        for col_idx, header in enumerate(headers, 1):
            if header and header in row_data:
                cell = ws.cell(next_row, col_idx, row_data[header])
                cell.border = _border()
                cell.fill = fill_new
                cell.font = _font()
                # Format numbers
                if isinstance(row_data[header], float):
                    cell.number_format = EUR_FMT
                    cell.alignment = _right()
                else:
                    cell.alignment = _left()

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════
#  GENERAR — create new Excel reports from scratch
# ══════════════════════════════════════════════════════════════

def generate_invoice_report(invoices: list, year: int) -> bytes:
    """Generates a professional Excel report of invoices with fiscal summary."""
    wb = Workbook()

    _build_invoice_sheet(wb, invoices, year)
    _build_summary_sheet(wb, invoices, year)
    _build_quarterly_sheet(wb, invoices, year)

    # Remove default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _build_invoice_sheet(wb: Workbook, invoices: list, year: int):
    ws = wb.create_sheet("Facturas")

    # ── Title ──
    ws.merge_cells("A1:J1")
    ws["A1"] = f"FiscalIA — Registro de Facturas {year}"
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color=WHITE)
    ws["A1"].fill = _header_fill(NAVY)
    ws["A1"].alignment = _center()
    ws.row_dimensions[1].height = 28

    ws["A2"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = _font(color="888888", size=9)
    ws.row_dimensions[2].height = 16

    # ── Headers ──
    headers = ["#", "Fecha", "Tipo", "Emisor", "Concepto", "Base Imp. (€)",
               "Tipo IVA (%)", "Cuota IVA (€)", "Total (€)", "Categoría", "Deducible"]
    widths  = [5,  12,    8,     22,     30,          14,          13,          13,          12,       16,        10]

    for col, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(4, col, h)
        cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
        cell.fill = _header_fill(GOLD)
        cell.alignment = _center()
        cell.border = _border()
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[4].height = 20

    # ── Data rows ──
    fill_ing = PatternFill("solid", start_color="E8F5E9", fgColor="E8F5E9")
    fill_gas = PatternFill("solid", start_color="FFF3E0", fgColor="FFF3E0")

    for i, inv in enumerate(invoices, 1):
        row = 4 + i
        fecha = None
        if hasattr(inv, 'fecha') and inv.fecha:
            fecha = inv.fecha
        elif hasattr(inv, 'created_at') and inv.created_at:
            fecha = inv.created_at

        fill = fill_ing if getattr(inv, 'tipo', '') == 'ingreso' else fill_gas

        values = [
            i,
            fecha.strftime("%d/%m/%Y") if fecha else "",
            getattr(inv, 'tipo', '').upper(),
            getattr(inv, 'emisor', '') or "",
            getattr(inv, 'concepto', '') or "",
            float(getattr(inv, 'base_imponible', 0) or 0),
            float(getattr(inv, 'tipo_iva', 21) or 21),
            float(getattr(inv, 'cuota_iva', 0) or 0),
            float(getattr(inv, 'total', 0) or 0),
            getattr(inv, 'categoria', '') or "",
            "Sí" if getattr(inv, 'deducible', False) else "No",
        ]

        for col, val in enumerate(values, 1):
            cell = ws.cell(row, col, val)
            cell.fill = fill
            cell.border = _border()
            cell.font = _font()
            if col in (6, 8, 9):
                cell.number_format = EUR_FMT
                cell.alignment = _right()
            elif col == 7:
                cell.number_format = '0.0"%"'
                cell.alignment = _center()
            elif col in (1,):
                cell.alignment = _center()
            else:
                cell.alignment = _left()

        ws.row_dimensions[row].height = 16

    # ── Totals ──
    last_data = 4 + len(invoices)
    total_row = last_data + 2
    ws.merge_cells(f"A{total_row}:E{total_row}")
    ws[f"A{total_row}"] = "TOTALES"
    ws[f"A{total_row}"].font = Font(name="Arial", bold=True, color=WHITE)
    ws[f"A{total_row}"].fill = _header_fill(NAVY)
    ws[f"A{total_row}"].alignment = _right()

    for col, formula_col in [(6, "F"), (8, "H"), (9, "I")]:
        cell = ws.cell(total_row, col, f"=SUM({formula_col}5:{formula_col}{last_data})")
        cell.font = Font(name="Arial", bold=True, color=WHITE)
        cell.fill = _header_fill(NAVY)
        cell.number_format = EUR_FMT
        cell.alignment = _right()
        cell.border = _border()

    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}4"


def _build_summary_sheet(wb: Workbook, invoices: list, year: int):
    ws = wb.create_sheet("Resumen Fiscal")

    ingresos = [i for i in invoices if getattr(i, 'tipo', '') == 'ingreso']
    gastos   = [i for i in invoices if getattr(i, 'tipo', '') == 'gasto']

    total_ing  = sum(float(getattr(i, 'base_imponible', 0) or 0) for i in ingresos)
    total_gas  = sum(float(getattr(i, 'base_imponible', 0) or 0) for i in gastos)
    gas_ded    = sum(
        float(getattr(i, 'base_imponible', 0) or 0) * float(getattr(i, 'porcentaje_deduccion', 0) or 0) / 100
        for i in gastos if getattr(i, 'deducible', False)
    )
    iva_rep    = sum(float(getattr(i, 'cuota_iva', 0) or 0) for i in ingresos)
    iva_sop    = sum(
        float(getattr(i, 'cuota_iva', 0) or 0) * float(getattr(i, 'porcentaje_deduccion', 0) or 0) / 100
        for i in gastos if getattr(i, 'deducible', False)
    )

    # Title
    ws.merge_cells("A1:D1")
    ws["A1"] = f"Resumen Fiscal {year} — FiscalIA"
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color=WHITE)
    ws["A1"].fill = _header_fill(NAVY)
    ws["A1"].alignment = _center()
    ws.row_dimensions[1].height = 28

    def write_section(start_row, title, rows_data):
        ws.merge_cells(f"A{start_row}:D{start_row}")
        ws[f"A{start_row}"] = title
        ws[f"A{start_row}"].font = Font(name="Arial", bold=True, color=WHITE, size=11)
        ws[f"A{start_row}"].fill = _header_fill(GOLD)
        ws[f"A{start_row}"].alignment = _left()
        ws.row_dimensions[start_row].height = 20

        for offset, (label, value, fmt, note) in enumerate(rows_data, 1):
            r = start_row + offset
            ws[f"A{r}"] = label
            ws[f"A{r}"].font = _font()
            ws[f"A{r}"].fill = PatternFill("solid", start_color=GREY_L, fgColor=GREY_L)
            ws[f"A{r}"].border = _border()
            ws[f"A{r}"].alignment = _left()
            ws[f"A{r}"].font = Font(name="Arial", size=10)

            ws[f"B{r}"] = value
            ws[f"B{r}"].number_format = fmt
            ws[f"B{r}"].font = Font(name="Arial", bold=True, size=10)
            ws[f"B{r}"].border = _border()
            ws[f"B{r}"].alignment = _right()

            if note:
                ws[f"C{r}"] = note
                ws[f"C{r}"].font = Font(name="Arial", size=9, color="888888", italic=True)
                ws[f"C{r}"].alignment = _left()
            ws.row_dimensions[r].height = 16

        return start_row + len(rows_data) + 2

    next_row = write_section(3, "💰 INGRESOS Y GASTOS", [
        ("Ingresos totales (base imponible)",  total_ing,  EUR_FMT, f"{len(ingresos)} facturas de ingreso"),
        ("Gastos totales (base imponible)",    total_gas,  EUR_FMT, f"{len(gastos)} facturas de gasto"),
        ("Gastos deducibles",                  gas_ded,    EUR_FMT, "Aplicando % deducción IA"),
        ("Beneficio neto",                     total_ing - total_gas, EUR_FMT, "Ingresos − Gastos"),
        ("Margen neto (%)",                    (total_ing - total_gas) / total_ing if total_ing else 0, PCT_FMT, ""),
    ])

    next_row = write_section(next_row, "🏛 IVA (Modelo 303)", [
        ("IVA repercutido (cobrado a clientes)", iva_rep,               EUR_FMT, "21% sobre base ingresos"),
        ("IVA soportado deducible",              iva_sop,               EUR_FMT, "IVA pagado en gastos deducibles"),
        ("IVA a ingresar a Hacienda",            max(0, iva_rep-iva_sop), EUR_FMT, "Positivo = pagar, negativo = devolver"),
    ])

    # IRPF estimation
    base_irpf = total_ing - gas_ded
    irpf_est  = _calc_irpf(base_irpf)
    irpf_ret  = total_ing * 0.15

    next_row = write_section(next_row, "📊 IRPF ESTIMADO (Modelo 130)", [
        ("Ingresos totales",            total_ing,        EUR_FMT, ""),
        ("Gastos deducibles",           gas_ded,          EUR_FMT, ""),
        ("Base liquidable IRPF",        base_irpf,        EUR_FMT, "Ingresos − Gastos deducibles"),
        ("IRPF estimado anual",         irpf_est,         EUR_FMT, "Tramos 2026"),
        ("IRPF retenido en facturas",   irpf_ret,         EUR_FMT, "15% retención estimada"),
        ("Diferencia a pagar/devolver", irpf_est-irpf_ret, EUR_FMT, "Positivo = pagar"),
    ])

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 30


def _build_quarterly_sheet(wb: Workbook, invoices: list, year: int):
    ws = wb.create_sheet("Trimestral")

    ws.merge_cells("A1:F1")
    ws["A1"] = f"Desglose Trimestral {year} — FiscalIA"
    ws["A1"].font = Font(name="Arial", bold=True, size=13, color=WHITE)
    ws["A1"].fill = _header_fill(NAVY)
    ws["A1"].alignment = _center()
    ws.row_dimensions[1].height = 26

    headers = ["Trimestre", "Ingresos (€)", "Gastos (€)", "Beneficio (€)", "IVA a pagar (€)", "IRPF (M.130) (€)"]
    widths  = [14, 16, 16, 16, 18, 18]

    for col, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(3, col, h)
        cell.font = Font(name="Arial", bold=True, color=WHITE, size=10)
        cell.fill = _header_fill(GOLD)
        cell.alignment = _center()
        cell.border = _border()
        ws.column_dimensions[get_column_letter(col)].width = w

    # Quarterly data
    quarters = {"T1": [], "T2": [], "T3": [], "T4": []}
    q_map = {1:"T1", 2:"T1", 3:"T1", 4:"T2", 5:"T2", 6:"T2",
             7:"T3", 8:"T3", 9:"T3", 10:"T4", 11:"T4", 12:"T4"}

    for inv in invoices:
        ref = getattr(inv, 'fecha', None) or getattr(inv, 'created_at', None)
        if ref and ref.year == year:
            q = q_map.get(ref.month, "T4")
            quarters[q].append(inv)

    fill_alt = PatternFill("solid", start_color=GREY_L, fgColor=GREY_L)

    for row_idx, (q_name, q_invs) in enumerate(quarters.items(), 4):
        ing   = sum(float(getattr(i,'base_imponible',0) or 0) for i in q_invs if getattr(i,'tipo','')=='ingreso')
        gas   = sum(float(getattr(i,'base_imponible',0) or 0) for i in q_invs if getattr(i,'tipo','')=='gasto')
        iva_r = sum(float(getattr(i,'cuota_iva',0) or 0) for i in q_invs if getattr(i,'tipo','')=='ingreso')
        iva_s = sum(float(getattr(i,'cuota_iva',0) or 0) * float(getattr(i,'porcentaje_deduccion',0) or 0) / 100
                    for i in q_invs if getattr(i,'tipo','')=='gasto' and getattr(i,'deducible',False))
        m130  = max(0, (ing - gas) * 0.20)

        fill = fill_alt if row_idx % 2 == 0 else PatternFill("solid", start_color=WHITE, fgColor=WHITE)
        row_vals = [q_name, ing, gas, ing-gas, max(0,iva_r-iva_s), m130]

        for col, val in enumerate(row_vals, 1):
            cell = ws.cell(row_idx, col, val)
            cell.border = _border()
            cell.fill = fill
            cell.font = _font(bold=(col==1))
            if col == 1:
                cell.alignment = _center()
            else:
                cell.number_format = EUR_FMT
                cell.alignment = _right()
                if col == 4 and isinstance(val, (int,float)) and val < 0:
                    cell.font = Font(name="Arial", color=RED_, bold=False)
        ws.row_dimensions[row_idx].height = 18

    # Annual totals row
    total_row = 8
    ws.cell(total_row, 1, "TOTAL AÑO").font = Font(name="Arial", bold=True, color=WHITE)
    ws.cell(total_row, 1).fill = _header_fill(NAVY)
    ws.cell(total_row, 1).alignment = _center()
    ws.cell(total_row, 1).border = _border()

    for col_letter, col_num in [("B",2),("C",3),("D",4),("E",5),("F",6)]:
        cell = ws.cell(total_row, col_num, f"=SUM({col_letter}4:{col_letter}7)")
        cell.font = Font(name="Arial", bold=True, color=WHITE)
        cell.fill = _header_fill(NAVY)
        cell.number_format = EUR_FMT
        cell.alignment = _right()
        cell.border = _border()
    ws.row_dimensions[total_row].height = 20


def _calc_irpf(base: float) -> float:
    if base <= 0: return 0.0
    tramos = [(12450,.19),(7750,.24),(15000,.30),(24800,.37),(240000,.45)]
    imp, rest = 0.0, base
    for lim, tipo in tramos:
        if rest <= 0: break
        g = min(rest, lim); imp += g * tipo; rest -= g
    if rest > 0: imp += rest * 0.47
    return round(imp, 2)


def generate_csv_export(invoices: list) -> bytes:
    """Simple CSV export of all invoices."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["#","Fecha","Tipo","Emisor","Concepto","Base Imponible","Tipo IVA %",
                     "Cuota IVA","Total","Categoría","Deducible","% Deducción"])

    for i, inv in enumerate(invoices, 1):
        ref = getattr(inv,'fecha',None) or getattr(inv,'created_at',None)
        writer.writerow([
            i,
            ref.strftime("%d/%m/%Y") if ref else "",
            getattr(inv,'tipo',''),
            getattr(inv,'emisor','') or '',
            getattr(inv,'concepto','') or '',
            getattr(inv,'base_imponible',0),
            getattr(inv,'tipo_iva',21),
            getattr(inv,'cuota_iva',0),
            getattr(inv,'total',0),
            getattr(inv,'categoria','') or '',
            'Sí' if getattr(inv,'deducible',False) else 'No',
            getattr(inv,'porcentaje_deduccion',0),
        ])

    return output.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility
