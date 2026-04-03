"""Script temporaire pour explorer la structure des fichiers ODS de notes de colles."""
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf import teletype
import os

ODS_DIR = "/Users/sjulliot/Dropbox/Janson/PC/notes de colles"
files = sorted([
    f for f in os.listdir(ODS_DIR)
    if f.endswith(".ods") and "Copy" not in f and f != "TEMPLATE.ods"
])


def get_cell_value(cell):
    return teletype.extractText(cell).strip()


def read_sheet(sheet):
    rows = []
    for row in sheet.getElementsByType(TableRow):
        cells = row.getElementsByType(TableCell)
        row_data = []
        for cell in cells:
            repeat = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            val = get_cell_value(cell)
            row_data.extend([val] * repeat)
        while row_data and row_data[-1] == "":
            row_data.pop()
        if row_data:
            rows.append(row_data)
    return rows


for fname in files:
    path = os.path.join(ODS_DIR, fname)
    doc = load(path)
    sheets = doc.spreadsheet.getElementsByType(Table)
    print(f"\n{'='*60}")
    print(f"FILE: {fname}  ({len(sheets)} feuilles)")
    for sheet in sheets:
        name = sheet.getAttribute("name")
        print(f"\n  --- Feuille: {name} ---")
        rows = read_sheet(sheet)
        for i, row in enumerate(rows[:35]):
            print(f"    {i:2d}: {row}")
