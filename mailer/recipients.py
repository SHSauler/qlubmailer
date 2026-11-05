"""Recipient model: fixed schema (firstName, lastName, mail)."""

import csv
import json

FIELDS = ["firstName", "lastName", "mail"]


def normalize(recipient):
    """Return a dict with exactly the fixed fields (missing -> '')."""
    rec = dict(recipient or {})
    return {field: str(rec.get(field, "") or "") for field in FIELDS}


def display_name(recipient):
    rec = recipient or {}
    if rec.get("name"):
        return str(rec["name"])
    full = f"{rec.get('firstName', '')} {rec.get('lastName', '')}".strip()
    return full or rec.get("mail", "Unknown")


def template_vars(recipient):
    """Variables exposed to the Jinja template (incl. legacy 'name')."""
    rec = dict(recipient or {})
    if "name" not in rec:
        if rec.get("firstName") and rec.get("lastName"):
            rec["name"] = f"{rec['firstName']} {rec['lastName']}"
        else:
            rec["name"] = rec.get("mail", "Unknown")
    return rec


def validate_recipient(recipient):
    """Return a list of error strings (empty = valid)."""
    errors = []
    rec = recipient or {}
    if not (rec.get("lastName") or "").strip():
        errors.append("lastName is required")
    mail = (rec.get("mail") or "").strip()
    if not mail:
        errors.append("mail is required")
    elif "@" not in mail or "." not in mail.split("@")[-1]:
        errors.append(f"mail looks invalid: {mail!r}")
    return errors


def load_recipients(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("recipients file must contain a JSON list")
    return [normalize(r) if isinstance(r, dict) else normalize({}) for r in data]


def save_recipients(path, recipients):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([normalize(r) for r in recipients], f, ensure_ascii=False, indent=4)
        f.write("\n")


def load_csv(path):
    """Read a CSV with firstName/lastName/mail columns (case-insensitive)."""
    recipients = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
        for row in reader:
            recipients.append(
                {
                    field: (row.get(cols.get(field, ""), "") or "").strip()
                    if field in cols
                    else ""
                    for field in FIELDS
                }
            )
    return recipients


def save_csv(path, recipients):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in recipients:
            writer.writerow(normalize(r))
