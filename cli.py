#!/usr/bin/env python3
"""Command-line interface. Thin wrapper around mailer.sender.

Examples:
  python cli.py data/template.txt -r data/recipients.json -s "Invitation" -d 60
"""
import argparse
import logging
import sys

from mailer import recipients as recipients_mod
from mailer.config import get_send_delay, load_config
from mailer.paths import LOG_PATH, ensure_data_files
from mailer.sender import send_emails

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main(argv=None):
    ensure_data_files()
    parser = argparse.ArgumentParser(description="Send templated emails to recipients")
    parser.add_argument("template", help="Path to the template file")
    parser.add_argument("--recipients", "-r", default="data/recipients.json")
    parser.add_argument("--subject", "-s", default=None)
    parser.add_argument("--delay", "-d", type=float, default=None)
    parser.add_argument("--bcc", default=None, help="Override BCC address (empty = none)")
    args = parser.parse_args(argv)

    config = load_config()

    # Subject default: CLI arg > data/subject.txt > "Einladung"
    from mailer.sender import sanitize_header_value

    subject = args.subject
    if subject is None:
        try:
            from mailer.paths import SUBJECT_PATH

            subject = SUBJECT_PATH.read_text(encoding="utf-8") or "Einladung"
        except FileNotFoundError:
            subject = "Einladung"
    subject = sanitize_header_value(subject) or "Einladung"

    delay = args.delay if args.delay is not None else get_send_delay(config)
    bcc = args.bcc if args.bcc is not None else config.get("BCC_EMAIL", "")

    try:
        with open(args.template, encoding="utf-8") as f:
            template_text = f.read()
    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        return 1

    try:
        recipients = recipients_mod.load_recipients(args.recipients)
    except FileNotFoundError:
        logger.error("Recipients file %s not found", args.recipients)
        return 1
    except Exception as e:
        logger.error("Invalid recipients file: %s", e)
        return 1

    result = send_emails(template_text, recipients, subject, delay, config, bcc_email=bcc)
    return 0 if result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
