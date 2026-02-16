"""
utils/helpers.py
================
Standalone helper functions used across the whole application.
No imports from other project modules (avoids circular imports).
"""

import calendar
from datetime import datetime


# ── Month / Year helpers ─────────────────────────────────────────────────────

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]


def month_name(month_number: int) -> str:
    """Return full month name for a 1-based month integer."""
    return MONTHS[month_number - 1]


def month_year_label(month: int, year: int) -> str:
    """E.g. 'March 2025'"""
    return f"{month_name(month)} {year}"


def current_month() -> int:
    return datetime.now().month


def current_year() -> int:
    return datetime.now().year


def year_range(start: int = 2020) -> list[int]:
    """Return list of years from start up to current year + 1."""
    return list(range(start, current_year() + 2))


# ── Financial year helpers ───────────────────────────────────────────────────

def financial_year_label(year: int, start_month: int = 4) -> str:
    """
    Return e.g. '2024-25' given year=2024.
    year is the calendar year in which the FY starts.
    """
    end = year + 1
    return f"{year}-{str(end)[-2:]}"


def get_financial_year(month: int, year: int, start_month: int = 4) -> str:
    """Determine financial year label for a given month/year."""
    if month >= start_month:
        fy_start = year
    else:
        fy_start = year - 1
    return financial_year_label(fy_start)


# ── Currency / number helpers ────────────────────────────────────────────────

def format_currency(amount: float, symbol: str = "₹") -> str:
    """Format a float as Indian currency string: ₹ 1,23,456.78"""
    try:
        # Indian comma grouping
        amount = round(amount, 2)
        s = f"{amount:,.2f}"
        parts = s.split(".")
        integer_part = parts[0].replace(",", "")
        decimals = parts[1]
        # Apply Indian grouping: last 3 then every 2
        if len(integer_part) > 3:
            last3 = integer_part[-3:]
            rest  = integer_part[:-3]
            grouped = ",".join(
                [rest[max(0, i-2):i] for i in range(len(rest), 0, -2)][::-1]
            )
            integer_part = f"{grouped},{last3}" if grouped else last3
        return f"{symbol} {integer_part}.{decimals}"
    except Exception:
        return f"{symbol} {amount:.2f}"


def amount_in_words(amount: float) -> str:
    """Convert numeric amount to Indian words (up to crores)."""
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
            'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
            'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen',
            'Nineteen']
    tens_w = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
              'Sixty', 'Seventy', 'Eighty', 'Ninety']

    def two_digits(n):
        if n < 20:
            return ones[n]
        return tens_w[n // 10] + (' ' + ones[n % 10] if n % 10 else '')

    def three_digits(n):
        if n >= 100:
            return ones[n // 100] + ' Hundred' + (
                ' and ' + two_digits(n % 100) if n % 100 else ''
            )
        return two_digits(n)

    rupees = int(amount)
    paise  = round((amount - rupees) * 100)

    if rupees == 0:
        words = 'Zero'
    else:
        parts = []
        crore = rupees // 10_000_000;  rupees %= 10_000_000
        lakh  = rupees // 100_000;     rupees %= 100_000
        thousand = rupees // 1000;     rupees %= 1000
        rest = rupees

        if crore:
            parts.append(three_digits(crore) + ' Crore')
        if lakh:
            parts.append(three_digits(lakh) + ' Lakh')
        if thousand:
            parts.append(three_digits(thousand) + ' Thousand')
        if rest:
            parts.append(three_digits(rest))
        words = ' '.join(parts)

    result = words + ' Rupees'
    if paise:
        result += ' and ' + two_digits(paise) + ' Paise'
    return result + ' Only'


# ── Validation ───────────────────────────────────────────────────────────────

def is_valid_gst(gst: str) -> bool:
    """Basic 15-char GST number format check."""
    import re
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, gst.upper())) if gst else True   # blank is OK


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
