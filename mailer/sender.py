"""Core mail sending logic (GUI- and CLI-compatible).

The GUI runs :func:`send_emails` in a worker thread and passes callbacks;
the CLI passes ``None`` and just uses logging.
"""

import logging
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from jinja2 import Template

from . import recipients as recipients_mod

logger = logging.getLogger(__name__)


def sanitize_header_value(value):
    """Make a string safe for use in an email header.

    Strips CR/LF characters (header injection / folding errors) by
    replacing any run of ``\\r``/``\\n`` with a single space.
    E.g. ``"Einladung\\nNov Dez"`` -> ``"Einladung Nov Dez"``.
    """
    if value is None:
        return ""
    return re.sub(r"[\r\n]+", " ", str(value)).strip()


def create_email(from_email, to_email, subject, body, reply_to=None, from_name=""):
    # Sanitize all header inputs: embedded newlines would otherwise raise
    # ``HeaderWriteError: folded header contains newline`` on send, and
    # could be abused for header injection.
    from_email = sanitize_header_value(from_email)
    to_email = sanitize_header_value(to_email)
    subject = sanitize_header_value(subject)
    from_name = sanitize_header_value(from_name)
    reply_to = sanitize_header_value(reply_to) or from_email
    msg = MIMEText(body, "plain", "utf-8")
    display = from_name or from_email
    msg["From"] = formataddr((display, from_email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    try:
        msg["Message-ID"] = make_msgid(domain=from_email.split("@")[1])
    except Exception:
        msg["Message-ID"] = make_msgid()
    msg["Reply-To"] = reply_to or from_email
    msg["List-Unsubscribe"] = f"<mailto:{from_email}?subject=unsubscribe>"
    return msg


def connect_smtp(smtp_server, smtp_port, smtp_username, smtp_password, retries=3):
    """Open an SMTP connection (STARTTLS + login), retrying transient failures."""
    last_error = None
    for attempt in range(1, retries + 1):
        server = None
        try:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
            server.login(smtp_username, smtp_password)
            return server
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
            last_error = e
            logger.warning("Connection attempt %d/%d failed: %s", attempt, retries, e)
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass
            if attempt < retries:
                time.sleep(5 * attempt)
    raise last_error


def render_template(template_text, recipient):
    return Template(template_text).render(**recipients_mod.template_vars(recipient))


def test_connection(config, connect_func=None):
    """Try STARTTLS + login only. Returns (ok, message)."""
    from .config import get_smtp_port

    connect = connect_func or connect_smtp
    server = None
    try:
        server = connect(
            config["SMTP_SERVER"],
            get_smtp_port(config),
            config["SMTP_USERNAME"],
            config["SMTP_PASSWORD"],
        )
        return True, "Connection + login OK"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed (username/password)"
    except Exception as e:
        return False, f"Connection failed: {e}"
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def send_emails(
    template_text,
    recipients,
    subject,
    delay_seconds=60,
    config=None,
    bcc_email=None,
    progress_callback=None,
    log_callback=None,
    should_cancel=None,
    sleep_func=None,
    connect_func=None,
):
    """Send templated mails. Returns {'successful': int, 'failed': int, 'cancelled': bool}.

    ``recipients`` is a list of dicts. ``config`` holds SMTP settings.
    Each mail uses its own SMTP session (some providers drop idle sessions).
    """
    from .config import get_smtp_port

    config = dict(config or {})
    sleep = sleep_func or time.sleep
    connect = connect_func or connect_smtp

    def log(msg):
        logger.info(msg)
        if log_callback:
            log_callback(msg)

    smtp_server = config.get("SMTP_SERVER")
    smtp_port = get_smtp_port(config)
    smtp_username = config.get("SMTP_USERNAME")
    smtp_password = config.get("SMTP_PASSWORD")
    from_email = config.get("FROM_EMAIL")
    from_name = config.get("FROM_NAME", "")
    reply_to = config.get("FROM_EMAIL")
    bcc = sanitize_header_value(bcc_email if bcc_email is not None else config.get("BCC_EMAIL", ""))
    subject = sanitize_header_value(subject)

    if not all([smtp_server, smtp_username, smtp_password, from_email]):
        log("Missing required SMTP settings (server/username/password/from email)")
        return {"successful": 0, "failed": len(recipients), "cancelled": False}

    try:
        template = Template(template_text)
    except Exception as e:
        log(f"Invalid template: {e}")
        return {"successful": 0, "failed": len(recipients), "cancelled": False}

    successful = 0
    failed = 0
    cancelled = False
    total = len(recipients)

    for i, recipient in enumerate(recipients):
        if should_cancel and should_cancel():
            cancelled = True
            log("Send cancelled by user")
            break
        to_addr = (recipient.get("mail") or "").strip()
        name = recipients_mod.display_name(recipient)
        if not to_addr:
            failed += 1
            log(f"Skipping {name}: missing mail address")
            continue
        try:
            body = template.render(**recipients_mod.template_vars(recipient))
            msg = create_email(from_email, to_addr, subject, body, reply_to, from_name)
            to_addrs = [to_addr] + ([bcc] if bcc else [])

            sent = False
            last_error = None
            for attempt in range(1, 4):
                server = None
                try:
                    server = connect(smtp_server, smtp_port, smtp_username, smtp_password)
                    server.send_message(msg, to_addrs=to_addrs)
                    sent = True
                    break
                except smtplib.SMTPAuthenticationError:
                    raise
                except (smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException) as e:
                    temporary = isinstance(e, smtplib.SMTPServerDisconnected) or getattr(
                        e, "smtp_code", 500
                    ) < 500
                    last_error = e
                    if attempt == 3 or not temporary:
                        raise
                    log(f"Temporary SMTP problem ({e}). Retrying with a fresh session...")
                finally:
                    if server is not None:
                        try:
                            server.quit()
                        except Exception:
                            pass
            if sent:
                successful += 1
                log(f"Sent to {name} ({to_addr})")
            else:
                raise last_error or RuntimeError("send failed")
        except smtplib.SMTPAuthenticationError:
            failed += 1
            log("SMTP authentication failed. Check username and password. Aborting.")
            break
        except Exception as e:
            failed += 1
            log(f"Failed to send to {name} ({to_addr}): {e}")

        if progress_callback:
            progress_callback(i + 1, total, recipient)
        if i < total - 1 and not (should_cancel and should_cancel()):
            try:
                sleep(delay_seconds)
            except Exception:
                cancelled = True
                break

    log(f"Done. Successful: {successful}, Failed: {failed}")
    return {"successful": successful, "failed": failed, "cancelled": cancelled}
