# GST Invoice & End of Day

Docker-ready Django application for recording supplier invoices, uploading invoice files, completing End of Day reconciliation, and exporting accountant-friendly PDF/Excel/CSV reports.

## Features

- User registration, login, logout, and password reset views.
- Dashboard with invoice totals, recent invoices, latest End of Day records, and quick add actions.
- Supplier add/edit/search with no delete workflow.
- Invoice add/list/view/edit with required upload, filters, and single-invoice PDF.
- End of Day add/history/view/edit with one record per date, automatic formulas, and downloadable PDF.
- Report filters for invoices and End of Day with PDF, Excel, and CSV exports.
- Basic audit log records for edited supplier, invoice, and End of Day fields.

## End of Day formulas

```text
Adjusted United Card = United Card + Store Value Charge - IOU - Drive Offs
Total Value = Uber Eats + DoorDash + EFTPOS + Amex Card + Motorpass + Motorcharge + Fleet Card + Diners Card + Adjusted United Card + IOU + Drive Offs + Cash + Vault Drop
Difference = Total Value - Total Sales
Net Shop Sales = Total Sales - EZY Pin - Less Surcharge
```

If the absolute difference is more than `$5`, a note is required before the record can be saved.

## Run with Docker

```bash
docker compose up --build
```

Open http://localhost:8000.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tests

```bash
python manage.py test
```

## Notes

There are no delete buttons or delete routes in the app. Records are protected for accounting safety.
