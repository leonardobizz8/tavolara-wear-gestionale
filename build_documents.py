import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import subprocess

def create_clean_excel():
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    
    # -------------------------------------------------------------
    # MINIMALIST CORPORATE STYLES (NO EMOJIS, HIGH LEGIBILITY)
    # -------------------------------------------------------------
    font_title = Font(name="Arial", size=14, bold=True, color="111827")
    font_sub = Font(name="Arial", size=10, italic=True, color="4B5563")
    font_section = Font(name="Arial", size=11, bold=True, color="111827")
    font_header = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Arial", size=10, bold=True, color="111827")
    font_regular = Font(name="Arial", size=10, color="111827")
    
    fill_header = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid") # Dark Charcoal
    fill_header_sec = PatternFill(start_color="374151", end_color="374151", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    fill_total = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    fill_highlight = PatternFill(start_color="E5E7EB", end_color="E5E7EB", fill_type="solid")
    
    thin_border = Side(style="thin", color="D1D5DB")
    double_bottom = Side(style="double", color="111827")
    thick_bottom = Side(style="medium", color="111827")
    
    border_cell = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    border_total = Border(left=thin_border, right=thin_border, top=thin_border, bottom=double_bottom)
    border_header = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thick_bottom)
    
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # =============================================================
    # SHEET 1: TABELLA COMPARATIVA 65 E 100 CAPI
    # =============================================================
    ws1 = wb.create_sheet(title="Pianificazione Fabbisogno")
    ws1.views.sheetView[0].showGridLines = True
    
    ws1.cell(row=2, column=2, value="TAVOLARA WEAR S.R.L. — PIANIFICAZIONE ACQUISTI").font = font_title
    ws1.cell(row=3, column=2, value="Fabbisogno taglie e colori calcolato su storico vendite reali (59 ordini)").font = font_sub
    
    # Table 1: Lotto 65 Capi
    ws1.cell(row=5, column=2, value="OPZIONE A: LOTTO DA 65 CAPI (FABBISOGNO BASE)").font = font_section
    
    headers_65 = ["Taglia", "Blu Navy", "Bianco", "Totale Capi", "Quota %"]
    for idx, h in enumerate(headers_65, start=2):
        c = ws1.cell(row=6, column=idx, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_header
        c.alignment = align_center if idx > 2 else align_left
        
    data_65 = [
        ("Taglia S", 3, 5, 0.123),
        ("Taglia M", 24, 5, 0.446),
        ("Taglia L", 11, 8, 0.292),
        ("Taglia XL", 4, 2, 0.092),
        ("Taglia XXL", 2, 1, 0.046)
    ]
    
    for i, (size, blu, bnc, pct) in enumerate(data_65, start=7):
        ws1.cell(row=i, column=2, value=size).font = font_bold if "M" in size else font_regular
        ws1.cell(row=i, column=2).alignment = align_left
        ws1.cell(row=i, column=2).border = border_cell
        
        c_b = ws1.cell(row=i, column=3, value=blu)
        c_b.font = font_bold if "M" in size else font_regular
        c_b.alignment = align_center
        c_b.border = border_cell
        c_b.number_format = "#,##0"
        
        c_w = ws1.cell(row=i, column=4, value=bnc)
        c_w.font = font_regular
        c_w.alignment = align_center
        c_w.border = border_cell
        c_w.number_format = "#,##0"
        
        c_tot = ws1.cell(row=i, column=5, value=f"=C{i}+D{i}")
        c_tot.font = font_bold
        c_tot.alignment = align_center
        c_tot.border = border_cell
        c_tot.number_format = "#,##0"
        c_tot.fill = fill_zebra
        
        c_p = ws1.cell(row=i, column=6, value=pct)
        c_p.font = font_regular
        c_p.alignment = align_center
        c_p.border = border_cell
        c_p.number_format = "0.0%"

    tot_r65 = 12
    ws1.cell(row=tot_r65, column=2, value="TOTALE CAPI").font = font_bold
    ws1.cell(row=tot_r65, column=2).alignment = align_left
    ws1.cell(row=tot_r65, column=2).border = border_total
    ws1.cell(row=tot_r65, column=2).fill = fill_total

    ws1.cell(row=tot_r65, column=3, value="=SUM(C7:C11)").font = font_bold
    ws1.cell(row=tot_r65, column=4, value="=SUM(D7:D11)").font = font_bold
    ws1.cell(row=tot_r65, column=5, value="=SUM(E7:E11)").font = font_bold
    ws1.cell(row=tot_r65, column=6, value="=SUM(F7:F11)").font = font_bold

    for c in range(3, 7):
        cell = ws1.cell(row=tot_r65, column=c)
        cell.alignment = align_center
        cell.border = border_total
        cell.fill = fill_total
        cell.number_format = "0.0%" if c == 6 else "#,##0"

    # Table 2: Lotto 100 Capi
    ws1.cell(row=15, column=2, value="OPZIONE B: LOTTO DA 100 CAPI (SCENARIO ESTESO)").font = font_section
    
    headers_100 = ["Taglia", "Blu Navy", "Bianco", "Totale Capi", "Quota %"]
    for idx, h in enumerate(headers_100, start=2):
        c = ws1.cell(row=16, column=idx, value=h)
        c.font = font_header
        c.fill = fill_header_sec
        c.border = border_header
        c.alignment = align_center if idx > 2 else align_left

    data_100 = [
        ("Taglia S", 4, 8, 0.120),
        ("Taglia M", 37, 7, 0.440),
        ("Taglia L", 17, 12, 0.290),
        ("Taglia XL", 7, 3, 0.100),
        ("Taglia XXL", 3, 2, 0.050)
    ]
    
    for i, (size, blu, bnc, pct) in enumerate(data_100, start=17):
        ws1.cell(row=i, column=2, value=size).font = font_bold if "M" in size else font_regular
        ws1.cell(row=i, column=2).alignment = align_left
        ws1.cell(row=i, column=2).border = border_cell
        
        c_b = ws1.cell(row=i, column=3, value=blu)
        c_b.font = font_bold if "M" in size else font_regular
        c_b.alignment = align_center
        c_b.border = border_cell
        c_b.number_format = "#,##0"
        
        c_w = ws1.cell(row=i, column=4, value=bnc)
        c_w.font = font_regular
        c_w.alignment = align_center
        c_w.border = border_cell
        c_w.number_format = "#,##0"
        
        c_tot = ws1.cell(row=i, column=5, value=f"=C{i}+D{i}")
        c_tot.font = font_bold
        c_tot.alignment = align_center
        c_tot.border = border_cell
        c_tot.number_format = "#,##0"
        c_tot.fill = fill_zebra
        
        c_p = ws1.cell(row=i, column=6, value=pct)
        c_p.font = font_regular
        c_p.alignment = align_center
        c_p.border = border_cell
        c_p.number_format = "0.0%"

    tot_r100 = 22
    ws1.cell(row=tot_r100, column=2, value="TOTALE CAPI").font = font_bold
    ws1.cell(row=tot_r100, column=2).alignment = align_left
    ws1.cell(row=tot_r100, column=2).border = border_total
    ws1.cell(row=tot_r100, column=2).fill = fill_total

    ws1.cell(row=tot_r100, column=3, value="=SUM(C17:C21)").font = font_bold
    ws1.cell(row=tot_r100, column=4, value="=SUM(D17:D21)").font = font_bold
    ws1.cell(row=tot_r100, column=5, value="=SUM(E17:E21)").font = font_bold
    ws1.cell(row=tot_r100, column=6, value="=SUM(F17:F21)").font = font_bold

    for c in range(3, 7):
        cell = ws1.cell(row=tot_r100, column=c)
        cell.alignment = align_center
        cell.border = border_total
        cell.fill = fill_total
        cell.number_format = "0.0%" if c == 6 else "#,##0"

    # Financial Comparison Section
    ws1.cell(row=25, column=2, value="RIASSUNTO ECONOMICO COMPARATO").font = font_section
    
    fin_headers = ["Voce di Costo / Ricavo", "Lotto 65 Capi", "Lotto 100 Capi", "Variazione"]
    for idx, h in enumerate(fin_headers, start=2):
        c = ws1.cell(row=26, column=idx, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_header
        c.alignment = align_left if idx == 2 else align_right

    fin_items = [
        ("Costo Unitario Fornitura", 12.00, 12.00, "€ #,##0.00"),
        ("Spesa Totale Fornitura (Merci)", "=E12*C27", "=E22*D27", "€ #,##0.00"),
        ("Prezzo Vendita Unitario", 25.00, 25.00, "€ #,##0.00"),
        ("Incasso Lordo Potenziale", "=E12*C29", "=E22*D29", "€ #,##0.00"),
        ("Utile Lordo Stimato", "=C30-C28", "=D30-D28", "€ #,##0.00"),
        ("Margine di Profitto Lordo", "=C31/C30", "=D31/D30", "0.0%")
    ]
    
    for idx, (label, v65, v100, fmt) in enumerate(fin_items, start=27):
        ws1.cell(row=idx, column=2, value=label).font = font_bold if "Utile" in label else font_regular
        ws1.cell(row=idx, column=2).border = border_cell
        ws1.cell(row=idx, column=2).alignment = align_left
        
        c65 = ws1.cell(row=idx, column=3, value=v65)
        c65.font = font_bold if "Utile" in label else font_regular
        c65.border = border_cell
        c65.alignment = align_right
        c65.number_format = fmt
        if "Utile" in label: c65.fill = fill_highlight
        
        c100 = ws1.cell(row=idx, column=4, value=v100)
        c100.font = font_bold if "Utile" in label else font_regular
        c100.border = border_cell
        c100.alignment = align_right
        c100.number_format = fmt
        if "Utile" in label: c100.fill = fill_highlight
        
        c_diff = ws1.cell(row=idx, column=5, value=f"=D{idx}-C{idx}" if "%" not in fmt and "Unitario" not in label else ("=D32-C32" if "%" in fmt else "-"))
        c_diff.font = font_bold if "Utile" in label else font_regular
        c_diff.border = border_cell
        c_diff.alignment = align_right
        c_diff.number_format = fmt

    # =============================================================
    # SHEET 2: MODULO ORDINE FORNITORE (65 CAPI)
    # =============================================================
    ws2 = wb.create_sheet(title="Ordine Fornitore - 65 Capi")
    ws2.views.sheetView[0].showGridLines = True
    
    ws2.cell(row=2, column=2, value="TAVOLARA WEAR S.R.L.").font = font_title
    ws2.cell(row=3, column=2, value="BUONO D'ORDINE FORNITURA MERCI — LOTTO 65 PEZZI").font = font_sub
    
    ws2.cell(row=5, column=2, value="Committente:").font = font_bold
    ws2.cell(row=5, column=3, value="Tavolara Wear S.r.l.").font = font_regular
    ws2.cell(row=6, column=2, value="Data emissione:").font = font_bold
    ws2.cell(row=6, column=3, value="15 Novembre 2026").font = font_regular
    ws2.cell(row=7, column=2, value="Rif. Documento:").font = font_bold
    ws2.cell(row=7, column=3, value="ORD-TVL-2026-65").font = font_bold

    ws2.cell(row=5, column=5, value="Destinazione:").font = font_bold
    ws2.cell(row=5, column=6, value="Magazzino Tavolara Wear").font = font_regular
    ws2.cell(row=6, column=5, value="Consegna:").font = font_bold
    ws2.cell(row=6, column=6, value="Corriere Espresso GLS / DHL").font = font_regular
    ws2.cell(row=7, column=5, value="Packaging:").font = font_bold
    ws2.cell(row=7, column=6, value="Polybag singolo con etichetta taglia").font = font_regular

    ws2.cell(row=10, column=2, value="DISTINTA QUANTITÀ PER TAGLIA E COLORE").font = font_section
    
    ord_headers = ["N°", "Descrizione Articolo", "Colore", "Taglia", "Quantità", "Prezzo Unit.", "Totale"]
    for idx, h in enumerate(ord_headers, start=2):
        c = ws2.cell(row=11, column=idx, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_header
        c.alignment = align_left if idx in [2, 3] else (align_right if idx in [7, 8] else align_center)

    items_65 = [
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "S", 3, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "M", 24, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "L", 11, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "XL", 4, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "XXL", 2, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "S", 5, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "M", 5, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "L", 8, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "XL", 2, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "XXL", 1, 12.00)
    ]

    r_start = 12
    for idx, (desc, col, sz, qty, prc) in enumerate(items_65, start=1):
        r = r_start + idx - 1
        ws2.cell(row=r, column=2, value=idx).font = font_regular
        ws2.cell(row=r, column=2).alignment = align_center
        ws2.cell(row=r, column=2).border = border_cell
        
        ws2.cell(row=r, column=3, value=desc).font = font_regular
        ws2.cell(row=r, column=3).alignment = align_left
        ws2.cell(row=r, column=3).border = border_cell
        
        ws2.cell(row=r, column=4, value=col).font = font_bold if col == "Blu Navy" else font_regular
        ws2.cell(row=r, column=4).alignment = align_left
        ws2.cell(row=r, column=4).border = border_cell
        
        ws2.cell(row=r, column=5, value=sz).font = font_bold
        ws2.cell(row=r, column=5).alignment = align_center
        ws2.cell(row=r, column=5).border = border_cell
        
        ws2.cell(row=r, column=6, value=qty).font = font_bold
        ws2.cell(row=r, column=6).alignment = align_center
        ws2.cell(row=r, column=6).border = border_cell
        ws2.cell(row=r, column=6).number_format = "#,##0"
        
        ws2.cell(row=r, column=7, value=prc).font = font_regular
        ws2.cell(row=r, column=7).alignment = align_right
        ws2.cell(row=r, column=7).border = border_cell
        ws2.cell(row=r, column=7).number_format = "€ #,##0.00"
        
        ws2.cell(row=r, column=8, value=f"=F{r}*G{r}").font = font_bold
        ws2.cell(row=r, column=8).alignment = align_right
        ws2.cell(row=r, column=8).border = border_cell
        ws2.cell(row=r, column=8).number_format = "€ #,##0.00"

    tot_r2 = r_start + len(items_65)
    ws2.cell(row=tot_r2, column=2, value="TOTALE ORDINE").font = font_bold
    ws2.cell(row=tot_r2, column=2).alignment = align_left
    ws2.cell(row=tot_r2, column=2).border = border_total
    ws2.cell(row=tot_r2, column=2).fill = fill_total
    ws2.merge_cells(start_row=tot_r2, start_column=2, end_row=tot_r2, end_column=5)

    c_qtot = ws2.cell(row=tot_r2, column=6, value=f"=SUM(F{r_start}:F{tot_r2-1})")
    c_qtot.font = font_bold
    c_qtot.alignment = align_center
    c_qtot.border = border_total
    c_qtot.fill = fill_total
    c_qtot.number_format = "#,##0"

    ws2.cell(row=tot_r2, column=7, value="").border = border_total
    ws2.cell(row=tot_r2, column=7).fill = fill_total

    c_vtot = ws2.cell(row=tot_r2, column=8, value=f"=SUM(H{r_start}:H{tot_r2-1})")
    c_vtot.font = font_bold
    c_vtot.alignment = align_right
    c_vtot.border = border_total
    c_vtot.fill = fill_total
    c_vtot.number_format = "€ #,##0.00"

    # Specifics
    ws2.cell(row=tot_r2+2, column=2, value="SPECIFICHE TECNICHE FORNITURA:").font = font_bold
    specs = [
        "- Tessuto: 100% Cotone Pettinato Ring-Spun, grammatura 180-190 gr/mq.",
        "- Colori: Blu Navy scuro pantone coordinato, Bianco ottico standard.",
        "- Stampa logo: Serigrafia ad alta resistenza ai lavaggi a 30-40°C.",
        "- Confezionamento: Polybag singolo trasparente con adesivo taglia visibile."
    ]
    for idx, s in enumerate(specs, start=tot_r2+3):
        ws2.cell(row=idx, column=2, value=s).font = font_regular

    # =============================================================
    # SHEET 3: MODULO ORDINE FORNITORE (100 CAPI)
    # =============================================================
    ws3 = wb.create_sheet(title="Ordine Fornitore - 100 Capi")
    ws3.views.sheetView[0].showGridLines = True
    
    ws3.cell(row=2, column=2, value="TAVOLARA WEAR S.R.L.").font = font_title
    ws3.cell(row=3, column=2, value="BUONO D'ORDINE FORNITURA MERCI — LOTTO 100 PEZZI").font = font_sub
    
    ws3.cell(row=5, column=2, value="Committente:").font = font_bold
    ws3.cell(row=5, column=3, value="Tavolara Wear S.r.l.").font = font_regular
    ws3.cell(row=6, column=2, value="Data emissione:").font = font_bold
    ws3.cell(row=6, column=3, value="15 Novembre 2026").font = font_regular
    ws3.cell(row=7, column=2, value="Rif. Documento:").font = font_bold
    ws3.cell(row=7, column=3, value="ORD-TVL-2026-100").font = font_bold

    ws3.cell(row=5, column=5, value="Destinazione:").font = font_bold
    ws3.cell(row=5, column=6, value="Magazzino Tavolara Wear").font = font_regular
    ws3.cell(row=6, column=5, value="Consegna:").font = font_bold
    ws3.cell(row=6, column=6, value="Corriere Espresso GLS / DHL").font = font_regular
    ws3.cell(row=7, column=5, value="Packaging:").font = font_bold
    ws3.cell(row=7, column=6, value="Polybag singolo con etichetta taglia").font = font_regular

    ws3.cell(row=10, column=2, value="DISTINTA QUANTITÀ PER TAGLIA E COLORE").font = font_section
    
    for idx, h in enumerate(ord_headers, start=2):
        c = ws3.cell(row=11, column=idx, value=h)
        c.font = font_header
        c.fill = fill_header
        c.border = border_header
        c.alignment = align_left if idx in [2, 3] else (align_right if idx in [7, 8] else align_center)

    items_100 = [
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "S", 4, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "M", 37, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "L", 17, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "XL", 7, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Blu Navy", "XXL", 3, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "S", 8, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "M", 7, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "L", 12, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "XL", 3, 12.00),
        ("T-Shirt Classic Unisex 100% Cotone", "Bianco", "XXL", 2, 12.00)
    ]

    for idx, (desc, col, sz, qty, prc) in enumerate(items_100, start=1):
        r = r_start + idx - 1
        ws3.cell(row=r, column=2, value=idx).font = font_regular
        ws3.cell(row=r, column=2).alignment = align_center
        ws3.cell(row=r, column=2).border = border_cell
        
        ws3.cell(row=r, column=3, value=desc).font = font_regular
        ws3.cell(row=r, column=3).alignment = align_left
        ws3.cell(row=r, column=3).border = border_cell
        
        ws3.cell(row=r, column=4, value=col).font = font_bold if col == "Blu Navy" else font_regular
        ws3.cell(row=r, column=4).alignment = align_left
        ws3.cell(row=r, column=4).border = border_cell
        
        ws3.cell(row=r, column=5, value=sz).font = font_bold
        ws3.cell(row=r, column=5).alignment = align_center
        ws3.cell(row=r, column=5).border = border_cell
        
        ws3.cell(row=r, column=6, value=qty).font = font_bold
        ws3.cell(row=r, column=6).alignment = align_center
        ws3.cell(row=r, column=6).border = border_cell
        ws3.cell(row=r, column=6).number_format = "#,##0"
        
        ws3.cell(row=r, column=7, value=prc).font = font_regular
        ws3.cell(row=r, column=7).alignment = align_right
        ws3.cell(row=r, column=7).border = border_cell
        ws3.cell(row=r, column=7).number_format = "€ #,##0.00"
        
        ws3.cell(row=r, column=8, value=f"=F{r}*G{r}").font = font_bold
        ws3.cell(row=r, column=8).alignment = align_right
        ws3.cell(row=r, column=8).border = border_cell
        ws3.cell(row=r, column=8).number_format = "€ #,##0.00"

    tot_r3 = r_start + len(items_100)
    ws3.cell(row=tot_r3, column=2, value="TOTALE ORDINE").font = font_bold
    ws3.cell(row=tot_r3, column=2).alignment = align_left
    ws3.cell(row=tot_r3, column=2).border = border_total
    ws3.cell(row=tot_r3, column=2).fill = fill_total
    ws3.merge_cells(start_row=tot_r3, start_column=2, end_row=tot_r3, end_column=5)

    c_qtot3 = ws3.cell(row=tot_r3, column=6, value=f"=SUM(F{r_start}:F{tot_r3-1})")
    c_qtot3.font = font_bold
    c_qtot3.alignment = align_center
    c_qtot3.border = border_total
    c_qtot3.fill = fill_total
    c_qtot3.number_format = "#,##0"

    ws3.cell(row=tot_r3, column=7, value="").border = border_total
    ws3.cell(row=tot_r3, column=7).fill = fill_total

    c_vtot3 = ws3.cell(row=tot_r3, column=8, value=f"=SUM(H{r_start}:H{tot_r3-1})")
    c_vtot3.font = font_bold
    c_vtot3.alignment = align_right
    c_vtot3.border = border_total
    c_vtot3.fill = fill_total
    c_vtot3.number_format = "€ #,##0.00"

    for idx, s in enumerate(specs, start=tot_r3+3):
        ws3.cell(row=idx, column=2, value=s).font = font_regular

    # Adjust Column Widths
    for ws in [ws1, ws2, ws3]:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if not val.startswith("="):
                    max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        ws.column_dimensions["A"].width = 3
        ws.column_dimensions["B"].width = 28
        ws.column_dimensions["C"].width = 16
        ws.column_dimensions["D"].width = 16
        ws.column_dimensions["E"].width = 16

    if default_sheet.title in wb.sheetnames:
        wb.remove(default_sheet)

    excel_path = "Pianificazione_Ordini_Stock_Tavolara_Wear.xlsx"
    wb.save(excel_path)
    print(f"Clean Excel file created: {excel_path}")
    return excel_path

create_clean_excel()
