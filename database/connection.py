"""
database/connection.py
======================
Central DatabaseManager: handles all SQLite operations for companies,
printers, counter readings, invoices, and settings.
Every public method is a single responsibility unit so business
logic in services/ never needs to touch raw SQL.
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

# Resolve DB path relative to project root regardless of CWD
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_HERE, "printbill.db")


class DatabaseManager:
    """
    Wraps all SQLite access.
    Usage:
        db = DatabaseManager()
        db.initialize()          # create tables once at startup
        companies = db.get_all_companies()
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    # ------------------------------------------------------------------ #
    #  Core connection helper                                              #
    # ------------------------------------------------------------------ #

    @contextmanager
    def get_connection(self):
        """Context manager that commits on success or rolls back on error."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row          # rows behave like dicts
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    #  Schema initialisation                                               #
    # ------------------------------------------------------------------ #

    def initialize(self):
        """Create all tables and seed default settings if missing."""
        with self.get_connection() as conn:
            conn.executescript("""
                -- ── Companies ──────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS companies (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT    NOT NULL,
                    address        TEXT    DEFAULT '',
                    gst_number     TEXT    DEFAULT '',
                    rate_per_print REAL    DEFAULT 0.0,
                    contact_person TEXT    DEFAULT '',
                    contact_phone  TEXT    DEFAULT '',
                    email          TEXT    DEFAULT '',
                    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                    updated_at     TEXT    DEFAULT CURRENT_TIMESTAMP
                );

                -- ── Printers ────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS printers (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id   INTEGER NOT NULL,
                    printer_id   TEXT    NOT NULL,
                    printer_name TEXT    DEFAULT '',
                    model        TEXT    DEFAULT '',
                    location     TEXT    DEFAULT '',
                    is_active    INTEGER DEFAULT 1,
                    created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE(company_id, printer_id)
                );

                -- ── Counter Readings ─────────────────────────────────────
                CREATE TABLE IF NOT EXISTS counter_readings (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    printer_id       INTEGER NOT NULL,
                    company_id       INTEGER NOT NULL,
                    month            INTEGER NOT NULL,
                    year             INTEGER NOT NULL,
                    opening_counter  INTEGER DEFAULT 0,
                    closing_counter  INTEGER DEFAULT 0,
                    total_prints     INTEGER DEFAULT 0,
                    created_at       TEXT    DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(printer_id, month, year),
                    FOREIGN KEY (printer_id)  REFERENCES printers(id)  ON DELETE CASCADE,
                    FOREIGN KEY (company_id)  REFERENCES companies(id) ON DELETE CASCADE
                );

                -- ── Invoices ─────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS invoices (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT    UNIQUE NOT NULL,
                    company_id     INTEGER NOT NULL,
                    month          INTEGER NOT NULL,
                    year           INTEGER NOT NULL,
                    total_prints   INTEGER DEFAULT 0,
                    rate_per_print REAL    DEFAULT 0.0,
                    subtotal       REAL    DEFAULT 0.0,
                    cgst_rate      REAL    DEFAULT 0.0,
                    sgst_rate      REAL    DEFAULT 0.0,
                    igst_rate      REAL    DEFAULT 0.0,
                    cgst_amount    REAL    DEFAULT 0.0,
                    sgst_amount    REAL    DEFAULT 0.0,
                    igst_amount    REAL    DEFAULT 0.0,
                    total_amount   REAL    DEFAULT 0.0,
                    invoice_date   TEXT    DEFAULT CURRENT_DATE,
                    pdf_path       TEXT    DEFAULT '',
                    status         TEXT    DEFAULT 'generated',
                    notes          TEXT    DEFAULT '',
                    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, month, year),
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                );

                -- ── Invoice Line Items ───────────────────────────────────
                CREATE TABLE IF NOT EXISTS invoice_items (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id       INTEGER NOT NULL,
                    printer_id       INTEGER NOT NULL,
                    printer_name     TEXT    DEFAULT '',
                    printer_serial   TEXT    DEFAULT '',
                    location         TEXT    DEFAULT '',
                    opening_counter  INTEGER DEFAULT 0,
                    closing_counter  INTEGER DEFAULT 0,
                    total_prints     INTEGER DEFAULT 0,
                    rate_per_print   REAL    DEFAULT 0.0,
                    amount           REAL    DEFAULT 0.0,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
                );

                -- ── Invoice Extra Charges / Discounts ────────────────────
                -- extra_type: 'charge' (adds to bill) or 'discount' (subtracts)
                -- taxable: 1 = GST applies, 0 = excluded from GST base
                CREATE TABLE IF NOT EXISTS invoice_extras (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id  INTEGER NOT NULL,
                    description TEXT    NOT NULL DEFAULT '',
                    extra_type  TEXT    NOT NULL DEFAULT 'charge',
                    amount      REAL    NOT NULL DEFAULT 0.0,
                    taxable     INTEGER NOT NULL DEFAULT 1,
                    sort_order  INTEGER          DEFAULT 0,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
                );

                -- ── App Settings ──────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                -- Seed defaults (ignored if already present)
                INSERT OR IGNORE INTO settings (key, value) VALUES
                    ('my_company_name',    'Your Printing Services'),
                    ('my_company_address', '123, Business Park, City - 400001'),
                    ('my_company_phone',   '+91 99999 99999'),
                    ('my_company_email',   'billing@yourcompany.com'),
                    ('my_company_gst',     ''),
                    ('invoice_prefix',     'INV'),
                    ('financial_year_start','4'),
                    ('default_cgst_rate',  '9'),
                    ('default_sgst_rate',  '9'),
                    ('default_igst_rate',  '18'),
                    ('logo_path',          ''),
                    ('terms',              'Payment due within 30 days of invoice date.');
            """)
            self._run_migrations(conn)

    def _run_migrations(self, conn):
        """Add new columns to existing DBs without breaking them (safe ALTER TABLE)."""
        cols = {r[1] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()}
        if "extras_total" not in cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN extras_total REAL DEFAULT 0.0")
        if "discount_total" not in cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN discount_total REAL DEFAULT 0.0")

    # ================================================================== #
    #  COMPANY CRUD                                                        #
    # ================================================================== #

    def add_company(self, name, address='', gst_number='', rate_per_print=0.0,
                    contact_person='', contact_phone='', email='') -> int:
        """Insert a new company and return its new primary key."""
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO companies
                       (name, address, gst_number, rate_per_print,
                        contact_person, contact_phone, email)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, address, gst_number, float(rate_per_print),
                 contact_person, contact_phone, email)
            )
            return cur.lastrowid

    def update_company(self, company_id, name, address='', gst_number='',
                       rate_per_print=0.0, contact_person='',
                       contact_phone='', email=''):
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE companies
                   SET name=?, address=?, gst_number=?, rate_per_print=?,
                       contact_person=?, contact_phone=?, email=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (name, address, gst_number, float(rate_per_print),
                 contact_person, contact_phone, email, company_id)
            )

    def delete_company(self, company_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM companies WHERE id=?", (company_id,))

    def get_company(self, company_id) -> dict | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE id=?", (company_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_companies(self, search: str = '') -> list[dict]:
        with self.get_connection() as conn:
            if search:
                rows = conn.execute(
                    """SELECT * FROM companies
                       WHERE name LIKE ? OR gst_number LIKE ? OR contact_person LIKE ?
                       ORDER BY name""",
                    (f'%{search}%', f'%{search}%', f'%{search}%')
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM companies ORDER BY name"
                ).fetchall()
            return [dict(r) for r in rows]

    # ================================================================== #
    #  PRINTER CRUD                                                        #
    # ================================================================== #

    def add_printer(self, company_id, printer_id, printer_name='',
                    model='', location='') -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO printers
                       (company_id, printer_id, printer_name, model, location)
                   VALUES (?, ?, ?, ?, ?)""",
                (company_id, printer_id, printer_name, model, location)
            )
            return cur.lastrowid

    def update_printer(self, printer_pk, printer_id, printer_name='',
                       model='', location='', is_active=True):
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE printers
                   SET printer_id=?, printer_name=?, model=?, location=?, is_active=?
                   WHERE id=?""",
                (printer_id, printer_name, model, location,
                 1 if is_active else 0, printer_pk)
            )

    def delete_printer(self, printer_pk):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM printers WHERE id=?", (printer_pk,))

    def get_printer(self, printer_pk) -> dict | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM printers WHERE id=?", (printer_pk,)
            ).fetchone()
            return dict(row) if row else None

    def get_printers_by_company(self, company_id,
                                 active_only: bool = False) -> list[dict]:
        with self.get_connection() as conn:
            sql = ("SELECT * FROM printers WHERE company_id=?"
                   + (" AND is_active=1" if active_only else "")
                   + " ORDER BY printer_id")
            return [dict(r) for r in conn.execute(sql, (company_id,)).fetchall()]

    def get_all_printers(self, search: str = '') -> list[dict]:
        with self.get_connection() as conn:
            if search:
                rows = conn.execute(
                    """SELECT p.*, c.name AS company_name
                       FROM printers p JOIN companies c ON p.company_id = c.id
                       WHERE p.printer_id LIKE ? OR p.printer_name LIKE ?
                          OR c.name LIKE ? OR p.location LIKE ?
                       ORDER BY c.name, p.printer_id""",
                    (f'%{search}%',) * 4
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT p.*, c.name AS company_name
                       FROM printers p JOIN companies c ON p.company_id = c.id
                       ORDER BY c.name, p.printer_id"""
                ).fetchall()
            return [dict(r) for r in rows]

    # ================================================================== #
    #  COUNTER READING CRUD                                                #
    # ================================================================== #

    def save_counter_reading(self, printer_id, company_id, month, year,
                              opening_counter, closing_counter):
        """Insert or update counter reading (upsert)."""
        total_prints = max(0, int(closing_counter) - int(opening_counter))
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO counter_readings
                       (printer_id, company_id, month, year,
                        opening_counter, closing_counter, total_prints)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(printer_id, month, year) DO UPDATE SET
                       opening_counter = excluded.opening_counter,
                       closing_counter = excluded.closing_counter,
                       total_prints    = excluded.total_prints""",
                (printer_id, company_id, month, year,
                 opening_counter, closing_counter, total_prints)
            )

    def delete_counter_reading(self, reading_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM counter_readings WHERE id=?", (reading_id,))

    def get_counter_reading(self, printer_id, month, year) -> dict | None:
        with self.get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM counter_readings
                   WHERE printer_id=? AND month=? AND year=?""",
                (printer_id, month, year)
            ).fetchone()
            return dict(row) if row else None

    def get_counter_readings_for_company_month(self, company_id, month, year) -> list[dict]:
        """All readings for a company in one month — used during billing."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT cr.*,
                          p.printer_id  AS printer_serial,
                          p.printer_name,
                          p.location,
                          p.model
                   FROM counter_readings cr
                   JOIN printers p ON cr.printer_id = p.id
                   WHERE cr.company_id=? AND cr.month=? AND cr.year=?
                   ORDER BY p.printer_id""",
                (company_id, month, year)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_counter_readings(self, company_id=None, month=None,
                                  year=None) -> list[dict]:
        with self.get_connection() as conn:
            sql = (
                """SELECT cr.*,
                          p.printer_id  AS printer_serial,
                          p.printer_name,
                          c.name        AS company_name
                   FROM counter_readings cr
                   JOIN printers  p ON cr.printer_id  = p.id
                   JOIN companies c ON cr.company_id  = c.id
                   WHERE 1=1"""
            )
            params = []
            if company_id:
                sql += " AND cr.company_id=?"; params.append(company_id)
            if month:
                sql += " AND cr.month=?";      params.append(month)
            if year:
                sql += " AND cr.year=?";       params.append(year)
            sql += " ORDER BY c.name, cr.year DESC, cr.month DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ================================================================== #
    #  INVOICE CRUD                                                        #
    # ================================================================== #

    def create_invoice(self, invoice_data: dict, items: list,
                       extras: list | None = None) -> int:
        """
        Insert invoice header + line items + optional extra charges atomically.
        invoice_data keys must match column names.
        extras = list of {description, extra_type, amount, taxable, sort_order}
        Returns the new invoice id.
        """
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO invoices
                       (invoice_number, company_id, month, year, total_prints,
                        rate_per_print, subtotal, extras_total, discount_total,
                        cgst_rate, sgst_rate, igst_rate,
                        cgst_amount, sgst_amount, igst_amount,
                        total_amount, invoice_date, notes)
                   VALUES
                       (:invoice_number, :company_id, :month, :year, :total_prints,
                        :rate_per_print, :subtotal, :extras_total, :discount_total,
                        :cgst_rate, :sgst_rate, :igst_rate,
                        :cgst_amount, :sgst_amount, :igst_amount,
                        :total_amount, :invoice_date, :notes)""",
                invoice_data
            )
            invoice_id = cur.lastrowid
            for item in items:
                item['invoice_id'] = invoice_id
                conn.execute(
                    """INSERT INTO invoice_items
                           (invoice_id, printer_id, printer_name, printer_serial,
                            location, opening_counter, closing_counter,
                            total_prints, rate_per_print, amount)
                       VALUES
                           (:invoice_id, :printer_id, :printer_name, :printer_serial,
                            :location, :opening_counter, :closing_counter,
                            :total_prints, :rate_per_print, :amount)""",
                    item
                )
            for idx, extra in enumerate(extras or []):
                conn.execute(
                    """INSERT INTO invoice_extras
                           (invoice_id, description, extra_type, amount, taxable, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (invoice_id, extra['description'], extra['extra_type'],
                     float(extra['amount']), int(extra.get('taxable', 1)), idx)
                )
            return invoice_id

    def update_invoice_pdf_path(self, invoice_id, pdf_path: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE invoices SET pdf_path=? WHERE id=?", (pdf_path, invoice_id)
            )

    def delete_invoice(self, invoice_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))

    def get_invoice(self, invoice_id) -> dict | None:
        """Fetch invoice header + items + company details."""
        with self.get_connection() as conn:
            row = conn.execute(
                """SELECT i.*,
                          c.name    AS company_name,
                          c.address AS company_address,
                          c.gst_number AS company_gst,
                          c.contact_person, c.contact_phone, c.email AS company_email
                   FROM invoices i
                   JOIN companies c ON i.company_id = c.id
                   WHERE i.id=?""",
                (invoice_id,)
            ).fetchone()
            if not row:
                return None
            inv = dict(row)
            items = conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id",
                (invoice_id,)
            ).fetchall()
            inv['items'] = [dict(i) for i in items]
            extras = conn.execute(
                "SELECT * FROM invoice_extras WHERE invoice_id=? ORDER BY sort_order",
                (invoice_id,)
            ).fetchall()
            inv['extras'] = [dict(e) for e in extras]
            return inv

    def invoice_exists(self, company_id, month, year) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM invoices WHERE company_id=? AND month=? AND year=?",
                (company_id, month, year)
            ).fetchone()
            return row is not None

    def get_invoice_by_company_month(self, company_id, month, year) -> dict | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM invoices WHERE company_id=? AND month=? AND year=?",
                (company_id, month, year)
            ).fetchone()
            return self.get_invoice(row['id']) if row else None

    def get_all_invoices(self, company_id=None, year=None,
                          search: str = '') -> list[dict]:
        with self.get_connection() as conn:
            sql = (
                """SELECT i.*, c.name AS company_name
                   FROM invoices i JOIN companies c ON i.company_id = c.id
                   WHERE 1=1"""
            )
            params = []
            if company_id:
                sql += " AND i.company_id=?";   params.append(company_id)
            if year:
                sql += " AND i.year=?";          params.append(year)
            if search:
                sql += " AND (c.name LIKE ? OR i.invoice_number LIKE ?)"
                params += [f'%{search}%', f'%{search}%']
            sql += " ORDER BY i.year DESC, i.month DESC, c.name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_next_invoice_number(self) -> str:
        """
        Auto-generate invoice number in format:
            <PREFIX>/<FY>/<SEQUENCE>
        e.g.  INV/25-26/0001
        Financial year determined by 'financial_year_start' setting.
        """
        prefix     = self.get_setting('invoice_prefix', 'INV')
        fy_start_m = int(self.get_setting('financial_year_start', '4'))
        now        = datetime.now()

        if now.month >= fy_start_m:
            fy_start = now.year
        else:
            fy_start = now.year - 1
        fy_end = fy_start + 1
        fy_str = f"{str(fy_start)[-2:]}-{str(fy_end)[-2:]}"
        pattern = f"{prefix}/{fy_str}/%"

        with self.get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE ?",
                (pattern,)
            ).fetchone()[0]

        return f"{prefix}/{fy_str}/{count + 1:04d}"

    # ================================================================== #
    #  INVOICE EXTRAS CRUD                                                 #
    # ================================================================== #

    def add_invoice_extra(self, invoice_id: int, description: str,
                          extra_type: str, amount: float,
                          taxable: bool = True, sort_order: int = 0) -> int:
        """Add a single extra charge or discount to an existing invoice."""
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO invoice_extras
                       (invoice_id, description, extra_type, amount, taxable, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, description, extra_type,
                 float(amount), 1 if taxable else 0, sort_order)
            )
            return cur.lastrowid

    def update_invoice_extra(self, extra_id: int, description: str,
                             extra_type: str, amount: float,
                             taxable: bool = True):
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE invoice_extras
                   SET description=?, extra_type=?, amount=?, taxable=?
                   WHERE id=?""",
                (description, extra_type, float(amount),
                 1 if taxable else 0, extra_id)
            )

    def delete_invoice_extra(self, extra_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM invoice_extras WHERE id=?", (extra_id,))

    def get_invoice_extras(self, invoice_id: int) -> list[dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM invoice_extras WHERE invoice_id=? ORDER BY sort_order",
                (invoice_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def recalculate_invoice_totals(self, invoice_id: int):
        """Recompute extras_total, discount_total, and total_amount after editing extras."""
        with self.get_connection() as conn:
            inv_row = conn.execute("SELECT * FROM invoices WHERE id=?",
                                   (invoice_id,)).fetchone()
            if not inv_row:
                return
            inv = dict(inv_row)
            extras = conn.execute(
                "SELECT * FROM invoice_extras WHERE invoice_id=?", (invoice_id,)
            ).fetchall()

            extras_total   = sum(float(e["amount"]) for e in extras if e["extra_type"] == "charge")
            discount_total = sum(float(e["amount"]) for e in extras if e["extra_type"] == "discount")
            taxable_extras = sum(float(e["amount"]) for e in extras
                                 if e["extra_type"] == "charge" and e["taxable"])
            taxable_disc   = sum(float(e["amount"]) for e in extras
                                 if e["extra_type"] == "discount" and e["taxable"])

            taxable_base = round(inv["subtotal"] + taxable_extras - taxable_disc, 2)
            taxable_base = max(taxable_base, 0.0)

            cgst_amount = round(taxable_base * inv["cgst_rate"] / 100, 2)
            sgst_amount = round(taxable_base * inv["sgst_rate"] / 100, 2)
            igst_amount = round(taxable_base * inv["igst_rate"] / 100, 2)

            total_amount = round(
                inv["subtotal"] + extras_total - discount_total
                + cgst_amount + sgst_amount + igst_amount, 2
            )

            conn.execute(
                """UPDATE invoices
                   SET extras_total=?, discount_total=?,
                       cgst_amount=?, sgst_amount=?, igst_amount=?,
                       total_amount=?
                   WHERE id=?""",
                (extras_total, discount_total,
                 cgst_amount, sgst_amount, igst_amount,
                 total_amount, invoice_id)
            )

    # ================================================================== #
    #  SETTINGS                                                            #
    # ================================================================== #

    def get_setting(self, key: str, default: str = '') -> str:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

    def get_all_settings(self) -> dict:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM settings").fetchall()
            return {r['key']: r['value'] for r in rows}

    # ================================================================== #
    #  DASHBOARD / REPORTING HELPERS                                       #
    # ================================================================== #

    def get_dashboard_stats(self) -> dict:
        now = datetime.now()
        with self.get_connection() as conn:
            def scalar(sql, params=()):
                return conn.execute(sql, params).fetchone()[0] or 0

            return {
                'total_companies':        scalar("SELECT COUNT(*) FROM companies"),
                'total_printers':         scalar("SELECT COUNT(*) FROM printers WHERE is_active=1"),
                'total_invoices':         scalar("SELECT COUNT(*) FROM invoices"),
                'current_month_invoices': scalar(
                    "SELECT COUNT(*) FROM invoices WHERE month=? AND year=?",
                    (now.month, now.year)
                ),
                'current_month_revenue':  scalar(
                    "SELECT COALESCE(SUM(total_amount),0) FROM invoices WHERE month=? AND year=?",
                    (now.month, now.year)
                ),
                'total_revenue':          scalar(
                    "SELECT COALESCE(SUM(total_amount),0) FROM invoices"
                ),
                'pending_counter_entries': self._pending_counter_count(conn, now.month, now.year),
            }

    def _pending_counter_count(self, conn, month, year) -> int:
        """Count active printers that have no counter reading for this month."""
        row = conn.execute(
            """SELECT COUNT(*) FROM printers p
               WHERE p.is_active = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM counter_readings cr
                     WHERE cr.printer_id=p.id AND cr.month=? AND cr.year=?
                 )""",
            (month, year)
        ).fetchone()
        return row[0] or 0
