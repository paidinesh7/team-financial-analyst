#!/usr/bin/env python3
"""
Fetch quarterly financial statement PDFs from screener.in.

Usage:
    # List available quarters (discovery mode)
    python3 scripts/fetch_screener.py HDFCBANK

    # Download a date range
    python3 scripts/fetch_screener.py HDFCBANK --from "Mar 2024" --to "Dec 2025" --output statements/

    # Download all available quarters
    python3 scripts/fetch_screener.py HDFCBANK --all --output statements/

    # Clear old PDFs for same ticker before downloading
    python3 scripts/fetch_screener.py HDFCBANK --from "Mar 2024" --to "Dec 2025" --output statements/ --clean

Accepts full screener.in URLs, partial URLs, or bare tickers.
Uses only Python stdlib — no pip install needed.
"""

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
MONTH_NUMBERS = {v: k for k, v in MONTH_NAMES.items()}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def parse_month_year(s):
    """Parse 'Mar 2024' into (month_number, year)."""
    parts = s.strip().split()
    if len(parts) != 2:
        return None
    month_str, year_str = parts
    month_str = month_str.capitalize()[:3]
    if month_str not in MONTH_NUMBERS:
        return None
    try:
        year = int(year_str)
    except ValueError:
        return None
    return (MONTH_NUMBERS[month_str], year)


def month_year_key(month, year):
    """Return a sortable key for (month, year)."""
    return year * 100 + month


def resolve_url(input_str):
    """
    Resolve user input into a screener.in company page URL and a ticker.

    Accepts:
      - Full URL: https://www.screener.in/company/HDFCBANK/consolidated/
      - Partial URL: screener.in/company/HDFCBANK/
      - Bare ticker: HDFCBANK
    """
    input_str = input_str.strip()

    # Full or partial screener.in URL
    match = re.search(r'screener\.in/company/([^/]+)', input_str, re.IGNORECASE)
    if match:
        ticker = match.group(1).upper()
        # Use the URL as-is if it's complete, otherwise build it
        if input_str.startswith("http"):
            url = input_str
        else:
            url = f"https://www.screener.in/company/{ticker}/consolidated/"
        return url, ticker

    # Bare ticker — build the default consolidated URL
    ticker = input_str.upper().strip("/")
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    return url, ticker


def fetch_page(url):
    """Fetch the screener.in page HTML. Returns None on 404."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"Error: HTTP {e.code} fetching {url}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Could not connect to screener.in — {e.reason}", file=sys.stderr)
        sys.exit(1)


def fetch_with_fallback(url, ticker):
    """
    Fetch the company page, trying consolidated first and falling back to
    standalone if consolidated has no quarterly PDFs or fewer than standalone.

    Returns (html, final_url, quarters, view_type).
    """
    html = fetch_page(url)
    quarters = extract_quarters(html) if html else []

    is_consolidated = "/consolidated/" in url
    if is_consolidated:
        standalone_url = url.replace("/consolidated/", "/")

        if not quarters:
            # Consolidated empty or 404 — try standalone
            print(f"No quarterly PDFs on consolidated page. Trying standalone...")
            html_s = fetch_page(standalone_url)
            quarters_s = extract_quarters(html_s) if html_s else []
            if quarters_s:
                return html_s, standalone_url, quarters_s, "standalone"
        else:
            # Consolidated has some PDFs — check if standalone has more
            html_s = fetch_page(standalone_url)
            quarters_s = extract_quarters(html_s) if html_s else []
            if len(quarters_s) > len(quarters):
                print(
                    f"Standalone has more quarters ({len(quarters_s)}) "
                    f"than consolidated ({len(quarters)}). Using standalone."
                )
                return html_s, standalone_url, quarters_s, "standalone"
            return html, url, quarters, "consolidated"

    if not html:
        print("Error: Could not fetch the company page.", file=sys.stderr)
        sys.exit(1)

    view_type = "consolidated" if is_consolidated else "standalone"
    return html, url, quarters, view_type


def extract_quarters(html):
    """
    Extract quarterly PDF links from the page HTML.

    Returns list of dicts: [{"company_id": ..., "month": ..., "year": ..., "path": ...}, ...]
    sorted oldest to newest.
    """
    pattern = r'/company/source/quarter/(\d+)/(\d{1,2})/(\d{4})/'
    matches = re.findall(pattern, html)

    if not matches:
        return []

    seen = set()
    quarters = []
    for company_id, month_str, year_str in matches:
        month = int(month_str)
        year = int(year_str)
        key = (month, year)
        if key in seen:
            continue
        seen.add(key)
        quarters.append({
            "company_id": company_id,
            "month": month,
            "year": year,
            "path": f"/company/source/quarter/{company_id}/{month}/{year}/",
        })

    quarters.sort(key=lambda q: month_year_key(q["month"], q["year"]))
    return quarters


def filter_quarters(quarters, from_spec, to_spec):
    """Filter quarters to those within [from_spec, to_spec] inclusive."""
    from_key = month_year_key(*from_spec) if from_spec else 0
    to_key = month_year_key(*to_spec) if to_spec else 999999

    return [
        q for q in quarters
        if from_key <= month_year_key(q["month"], q["year"]) <= to_key
    ]


def download_pdf(quarter, ticker, output_dir):
    """
    Download a single quarterly PDF.

    Returns (filename, size_bytes) on success, None on failure.
    """
    url = f"https://www.screener.in{quarter['path']}"
    month_name = MONTH_NAMES[quarter["month"]]
    filename = f"{ticker}-{month_name}-{quarter['year']}.pdf"
    filepath = os.path.join(output_dir, filename)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()

        with open(filepath, "wb") as f:
            f.write(data)

        return filename, len(data)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"  Warning: Failed to download {month_name} {quarter['year']} — {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"  Warning: Failed to save {filename} — {e}", file=sys.stderr)
        return None


def clean_ticker_pdfs(ticker, output_dir):
    """Remove existing PDFs for this ticker from the output directory."""
    pattern = re.compile(rf'^{re.escape(ticker)}-\w{{3}}-\d{{4}}\.pdf$', re.IGNORECASE)
    removed = 0
    if not os.path.isdir(output_dir):
        return 0
    for name in os.listdir(output_dir):
        if pattern.match(name):
            os.remove(os.path.join(output_dir, name))
            removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser(
        description="Fetch quarterly financial statement PDFs from screener.in"
    )
    parser.add_argument(
        "company",
        help="Ticker (e.g. HDFCBANK), or screener.in URL"
    )
    parser.add_argument(
        "--from", dest="from_date", metavar="DATE",
        help='Start of date range, e.g. "Mar 2024"'
    )
    parser.add_argument(
        "--to", dest="to_date", metavar="DATE",
        help='End of date range, e.g. "Dec 2025"'
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Download all available quarters"
    )
    parser.add_argument(
        "--output", "-o", default="statements/",
        help="Output directory for downloaded PDFs (default: statements/)"
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove existing PDFs for this ticker before downloading"
    )
    args = parser.parse_args()

    url, ticker = resolve_url(args.company)

    # Validate date args
    from_spec = None
    to_spec = None

    if args.from_date:
        from_spec = parse_month_year(args.from_date)
        if not from_spec:
            print(f'Error: Invalid --from date "{args.from_date}". Use format like "Mar 2024".', file=sys.stderr)
            sys.exit(1)

    if args.to_date:
        to_spec = parse_month_year(args.to_date)
        if not to_spec:
            print(f'Error: Invalid --to date "{args.to_date}". Use format like "Dec 2025".', file=sys.stderr)
            sys.exit(1)

    download_mode = args.all or from_spec or to_spec

    # Fetch and parse (tries consolidated, falls back to standalone)
    print(f"Fetching screener.in page for {ticker}...")
    html, url, quarters, view_type = fetch_with_fallback(url, ticker)

    if not quarters:
        print("No quarterly PDF links found on the page.", file=sys.stderr)
        print("The page structure may have changed, or this company may not have quarterly filings.", file=sys.stderr)
        sys.exit(1)

    # Discovery mode — just list available quarters
    if not download_mode:
        first = quarters[0]
        last = quarters[-1]
        print(f"\nCompany: {ticker}")
        print(f"Source: {url} ({view_type})")
        print(f"\nAvailable quarters ({len(quarters)}):")
        for i, q in enumerate(quarters, 1):
            month_name = MONTH_NAMES[q["month"]]
            print(f"  {i:>2}. {month_name} {q['year']}")
        print(f"\nTo download, run with --from and --to flags, or --all.")
        return

    # Filter quarters
    if args.all:
        selected = quarters
    else:
        selected = filter_quarters(quarters, from_spec, to_spec)

    if not selected:
        print("No quarters found in the specified date range.", file=sys.stderr)
        first = quarters[0]
        last = quarters[-1]
        print(
            f"Available range: {MONTH_NAMES[first['month']]} {first['year']} "
            f"to {MONTH_NAMES[last['month']]} {last['year']}",
            file=sys.stderr
        )
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    # Clean if requested
    if args.clean:
        removed = clean_ticker_pdfs(ticker, args.output)
        if removed:
            print(f"Cleaned {removed} existing PDF(s) for {ticker}.")

    # Download
    print(f"\nDownloading {len(selected)} quarter(s) for {ticker} to {args.output}")
    successes = 0
    for i, q in enumerate(selected, 1):
        month_name = MONTH_NAMES[q["month"]]
        label = f"[{i}/{len(selected)}] {month_name} {q['year']}"
        print(f"  {label} ... ", end="", flush=True)

        result = download_pdf(q, ticker, args.output)
        if result:
            filename, size = result
            size_kb = size / 1024
            print(f"saved ({size_kb:.0f} KB)")
            successes += 1
        else:
            print("FAILED")

        # Polite delay between downloads
        if i < len(selected):
            time.sleep(0.5)

    print(f"\nDone. {successes}/{len(selected)} file(s) downloaded to {args.output}")


if __name__ == "__main__":
    main()
