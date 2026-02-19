#!/usr/bin/env python3
"""
PDF table extraction tool for financial statement analysis.

Extracts text and tables from PDFs in statements/, auto-detects number format
(lacs, thousands, crores, etc.), and converts all values to crores.

Outputs to statements/extracted/{pdf-name}/:
  metadata.json  — format detected, pages, tables found, company name, period
  summary.txt    — human-readable overview
  raw/           — CSVs with original numbers as-is
  converted/     — CSVs with numbers converted to crores
  text/          — full text per page (fallback for manual reading)

Usage:
  python3 tools/extract.py                          # process all PDFs in statements/
  python3 tools/extract.py statements/filename.pdf  # process a specific file
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Check for pdfplumber availability
# ---------------------------------------------------------------------------

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# ---------------------------------------------------------------------------
# Indian number parsing
# ---------------------------------------------------------------------------

def parse_indian_number(text):
    """Parse Indian-formatted numbers including parenthesized negatives and dashes.

    Handles:
      "12,563.39"    -> 12563.39
      "(1,897.73)"   -> -1897.73
      "1,00,000"     -> 100000.0
      "-"            -> 0.0
      ""             -> None (not a number)
      "N/A"          -> None
    """
    if text is None:
        return None

    text = str(text).strip()

    # Dashes and common nil indicators
    if text in ("-", "—", "–", "nil", "Nil", "NIL", "N/A", "n/a", ""):
        return 0.0

    # Detect parenthesized negatives: (1,897.73)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()
    elif text.startswith("-"):
        negative = True
        text = text[1:].strip()

    # Strip currency symbols and whitespace
    text = re.sub(r"[₹$€£\s]", "", text)

    # Remove commas (Indian or international)
    text = text.replace(",", "")

    # Try to parse
    try:
        value = float(text)
    except (ValueError, TypeError):
        return None

    return -value if negative else value


# ---------------------------------------------------------------------------
# Number format detection
# ---------------------------------------------------------------------------

# Patterns to look for in page text, ordered by specificity
FORMAT_PATTERNS = [
    # Crores
    (r"(?:amount|figures?|rs\.?|₹|rupees?)\s*(?:are\s+)?(?:in\s+)?(?:₹\s*)?(?:in\s+)?cr(?:ore)?s?",
     "crores", 1),
    (r"(?:\(?\s*₹\s*(?:in\s+)?cr(?:ore)?s?\s*\)?)",
     "crores", 1),
    (r"in\s+crore",
     "crores", 1),

    # Lakhs / Lacs
    (r"(?:amount|figures?|rs\.?|₹|rupees?)\s*(?:are\s+)?(?:in\s+)?(?:₹\s*)?(?:in\s+)?la(?:kh|c)s?",
     "lacs", 100),
    (r"(?:\(?\s*₹\s*(?:in\s+)?la(?:kh|c)s?\s*\)?)",
     "lacs", 100),
    (r"in\s+la(?:kh|c)s?",
     "lacs", 100),
    (r"amount\s+in\s+₹\s+lacs",
     "lacs", 100),
    (r"amount\s+in\s+₹\s+lakhs",
     "lacs", 100),

    # Millions
    (r"(?:amount|figures?|rs\.?|₹|rupees?)\s*(?:are\s+)?(?:in\s+)?(?:₹\s*)?(?:in\s+)?millions?",
     "millions", 10),
    (r"in\s+millions?",
     "millions", 10),

    # Thousands
    (r"(?:amount|figures?|rs\.?|₹|rupees?)\s*(?:are\s+)?(?:in\s+)?(?:₹\s*)?(?:in\s+)?thousands?",
     "thousands", 10000),
    (r"(?:₹\s*['\u2018\u2019]000)",
     "thousands", 10000),
    (r"in\s+thousands?",
     "thousands", 10000),

    # Absolute rupees (least specific — match last)
    (r"(?:amount|figures?)\s+(?:are\s+)?in\s+(?:rs\.?|₹|rupees?)\s*$",
     "rupees", 10000000),
]


def detect_number_format(full_text):
    """Detect the number format from document text.

    Returns (unit_name, divisor_to_crores) or (None, None) if not detected.
    """
    text_lower = full_text.lower()
    for pattern, unit, divisor in FORMAT_PATTERNS:
        if re.search(pattern, text_lower):
            return unit, divisor
    return None, None


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_pages(pdf):
    """Extract full text from every page. Returns list of (page_num, text)."""
    pages = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        pages.append((i + 1, text))
    return pages


# ---------------------------------------------------------------------------
# Table extraction (two-pass)
# ---------------------------------------------------------------------------

def extract_tables_from_page(page, page_num):
    """Extract tables from a single page using two-pass strategy.

    Pass 1: Use explicit grid lines (most reliable for ruled tables).
    Pass 2: Fall back to text-based extraction for tables without rules.
    Returns list of (page_num, table_index, rows).
    """
    results = []

    # Pass 1: grid-line based
    tables = page.extract_tables(
        table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        }
    )
    if tables:
        for idx, table in enumerate(tables):
            if table and len(table) > 1:
                results.append((page_num, idx, table))
        if results:
            return results

    # Pass 2: text-based fallback
    tables = page.extract_tables(
        table_settings={
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 5,
            "join_tolerance": 5,
            "min_words_vertical": 2,
            "min_words_horizontal": 1,
        }
    )
    if tables:
        for idx, table in enumerate(tables):
            if table and len(table) > 1:
                results.append((page_num, idx, table))

    return results


def extract_all_tables(pdf):
    """Extract tables from all pages. Returns list of (page_num, table_index, rows)."""
    all_tables = []
    for i, page in enumerate(pdf.pages):
        tables = extract_tables_from_page(page, i + 1)
        all_tables.extend(tables)
    return all_tables


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert_to_crores(value, divisor):
    """Convert a numeric value to crores given the divisor."""
    if value is None or divisor is None or divisor == 0:
        return None
    return round(value / divisor, 4)


def convert_table_to_crores(rows, divisor):
    """Convert numeric cells in a table to crores. Returns new rows."""
    converted = []
    for row in rows:
        new_row = []
        for cell in row:
            parsed = parse_indian_number(cell)
            if parsed is not None and cell and not re.match(r"^\d{4}[-/]", str(cell).strip()):
                # It's a number — convert
                in_crores = convert_to_crores(parsed, divisor)
                if in_crores is not None:
                    new_row.append(f"{in_crores:.4f}")
                else:
                    new_row.append(cell)
            else:
                new_row.append(cell)
        converted.append(new_row)
    return converted


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def extract_metadata(text_pages, unit, divisor, total_tables):
    """Try to extract company name and period from page text."""
    meta = {
        "unit": unit,
        "divisor": divisor,
        "total_pages": len(text_pages),
        "total_tables": total_tables,
        "company_name": None,
        "period": None,
    }

    if not text_pages:
        return meta

    # Use first few pages to find company name and period
    first_pages_text = "\n".join(text for _, text in text_pages[:5])

    # Company name: often the first non-empty line, or after common prefixes
    for _, text in text_pages[:3]:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            # Skip common header lines
            if any(skip in line.lower() for skip in
                   ["balance sheet", "profit and loss", "cash flow",
                    "statement of", "notes to", "independent auditor",
                    "amount in", "particulars", "schedule", "annexure"]):
                continue
            # Company names often contain "limited", "ltd", "pvt", "private"
            if re.search(r"\b(?:limited|ltd|pvt|private|inc|corp|llp)\b", line, re.I):
                meta["company_name"] = line.strip()
                break
        if meta["company_name"]:
            break

    # Period: look for date patterns like "31st March 2025", "March 31, 2025",
    # "year ended", "period ended", "as at", "as on"
    period_patterns = [
        r"(?:year|period)\s+ended?\s+(.+?\d{4})",
        r"(?:as\s+(?:at|on))\s+(.+?\d{4})",
        r"for\s+the\s+(?:year|period)\s+(.+?\d{4})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
    ]
    for pattern in period_patterns:
        match = re.search(pattern, first_pages_text, re.I)
        if match:
            meta["period"] = match.group(1).strip()
            break

    return meta


# ---------------------------------------------------------------------------
# File writing helpers
# ---------------------------------------------------------------------------

def write_csv(filepath, rows):
    """Write rows to a CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def write_text(filepath, text):
    """Write text to a file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)


def slugify(name):
    """Convert a filename to a clean slug for directory names."""
    name = Path(name).stem
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def process_pdf(pdf_path, output_base):
    """Process a single PDF and write extracted data."""
    pdf_path = Path(pdf_path)
    slug = slugify(pdf_path.name)
    output_dir = Path(output_base) / slug

    print(f"\nProcessing: {pdf_path.name}")
    print(f"Output to:  {output_dir}/")

    if not HAS_PDFPLUMBER:
        # Text-only fallback: just dump what we can read
        print("  WARNING: pdfplumber not installed. Only basic text extraction available.")
        print("  Install it:  pip install pdfplumber")
        print("  Tables will not be extracted.")

        # We can't do anything without pdfplumber
        print("  SKIPPED — install pdfplumber to extract data.")
        return False

    # Open and extract
    with pdfplumber.open(pdf_path) as pdf:
        # Step 1: Extract all text
        print(f"  Extracting text from {len(pdf.pages)} pages...")
        text_pages = extract_text_pages(pdf)

        # Step 2: Detect number format from all text
        full_text = "\n".join(text for _, text in text_pages)
        unit, divisor = detect_number_format(full_text)
        if unit:
            print(f"  Detected format: {unit} (divide by {divisor} for crores)")
        else:
            print("  WARNING: Could not detect number format. Numbers will not be converted.")
            unit = "unknown"
            divisor = None

        # Step 3: Extract tables
        print("  Extracting tables (two-pass)...")
        tables = extract_all_tables(pdf)
        print(f"  Found {len(tables)} tables across {len(pdf.pages)} pages")

        # Step 4: Write text files
        text_dir = output_dir / "text"
        for page_num, text in text_pages:
            write_text(text_dir / f"page-{page_num:03d}.txt", text)
        print(f"  Wrote {len(text_pages)} text files to text/")

        # Step 5: Write raw CSVs
        raw_dir = output_dir / "raw"
        for page_num, table_idx, rows in tables:
            filename = f"page-{page_num:03d}-table-{table_idx + 1}.csv"
            write_csv(raw_dir / filename, rows)
        print(f"  Wrote {len(tables)} raw CSVs to raw/")

        # Step 6: Write converted CSVs
        converted_dir = output_dir / "converted"
        if divisor and divisor != 1:
            for page_num, table_idx, rows in tables:
                converted_rows = convert_table_to_crores(rows, divisor)
                filename = f"page-{page_num:03d}-table-{table_idx + 1}.csv"
                write_csv(converted_dir / filename, converted_rows)
            print(f"  Wrote {len(tables)} converted CSVs to converted/")
        elif divisor == 1:
            # Already in crores — just copy raw
            for page_num, table_idx, rows in tables:
                filename = f"page-{page_num:03d}-table-{table_idx + 1}.csv"
                write_csv(converted_dir / filename, rows)
            print(f"  Already in crores — copied raw CSVs to converted/")
        else:
            print("  Skipped conversion (unknown format)")

        # Step 7: Write metadata
        meta = extract_metadata(text_pages, unit, divisor, len(tables))
        meta_path = output_dir / "metadata.json"
        os.makedirs(output_dir, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        print(f"  Wrote metadata.json")

        # Step 8: Write summary
        summary_lines = [
            f"Extraction Summary",
            f"==================",
            f"",
            f"Source: {pdf_path.name}",
            f"Company: {meta['company_name'] or '(not detected)'}",
            f"Period: {meta['period'] or '(not detected)'}",
            f"",
            f"Format: {unit}" + (f" (÷{divisor} for crores)" if divisor and divisor != 1 else ""),
            f"Pages: {meta['total_pages']}",
            f"Tables extracted: {meta['total_tables']}",
            f"",
            f"Output structure:",
            f"  metadata.json  — this metadata",
            f"  summary.txt    — this file",
            f"  text/          — full text per page ({len(text_pages)} files)",
            f"  raw/           — tables with original numbers ({len(tables)} CSVs)",
        ]
        if divisor and divisor != 1:
            summary_lines.append(
                f"  converted/     — tables with numbers in crores ({len(tables)} CSVs)")
        elif divisor == 1:
            summary_lines.append(
                f"  converted/     — tables already in crores ({len(tables)} CSVs)")

        summary_lines.extend([
            f"",
            f"Table inventory:",
        ])
        for page_num, table_idx, rows in tables:
            n_rows = len(rows)
            n_cols = max(len(r) for r in rows) if rows else 0
            header = rows[0] if rows else []
            header_preview = " | ".join(str(c)[:30] for c in header[:4])
            summary_lines.append(
                f"  page {page_num}, table {table_idx + 1}: "
                f"{n_rows} rows × {n_cols} cols — {header_preview}"
            )

        write_text(output_dir / "summary.txt", "\n".join(summary_lines) + "\n")
        print(f"  Wrote summary.txt")

    print(f"  Done.")
    return True


def main():
    # Determine the project root (parent of tools/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    statements_dir = project_root / "statements"
    output_base = statements_dir / "extracted"

    if len(sys.argv) > 1:
        # Process specific file(s)
        pdf_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Process all PDFs in statements/
        if not statements_dir.exists():
            print(f"No statements/ folder found at {statements_dir}")
            sys.exit(1)

        pdf_paths = sorted(statements_dir.glob("*.pdf"))
        if not pdf_paths:
            print(f"No PDF files found in {statements_dir}/")
            sys.exit(1)

    if not HAS_PDFPLUMBER:
        print("=" * 60)
        print("WARNING: pdfplumber is not installed.")
        print("Install it with:  pip install pdfplumber")
        print("=" * 60)

    success = 0
    failed = 0
    for pdf_path in pdf_paths:
        try:
            if process_pdf(pdf_path, output_base):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n  ERROR processing {pdf_path.name}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Processed: {success} succeeded, {failed} failed")
    if success > 0:
        print(f"Output in: {output_base}/")


if __name__ == "__main__":
    main()
