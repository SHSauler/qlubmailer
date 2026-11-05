"""Load/save SMTP + app settings from the project .env file.

Settings (all editable in the GUI Settings tab, password shown in plain text
per user request):
  SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
  FROM_EMAIL, FROM_NAME, BCC_EMAIL (single, optional),
  SEND_DELAY (seconds between mails, float).
"""

import os

from dotenv import dotenv_values, load_dotenv, set_key

from .paths import ENV_PATH

FIELD_DEFS = [
    ("SMTP_SERVER", "SMTP server", ""),
    ("SMTP_PORT", "SMTP port", "587"),
    ("SMTP_USERNAME", "SMTP username", ""),
    ("SMTP_PASSWORD", "SMTP password", ""),
    ("FROM_EMAIL", "From email", ""),
    ("FROM_NAME", "From display name", ""),
    ("BCC_EMAIL", "BCC address (optional, single)", ""),
    ("SEND_DELAY", "Delay between mails (seconds)", "60"),
]

DEFAULTS = {key: default for key, _, default in FIELD_DEFS}


def load_config(env_path=ENV_PATH):
    """Return config dict; missing keys fall back to DEFAULTS."""
    values = {}
    if os.path.exists(env_path):
        values = dotenv_values(env_path) or {}
    config = dict(DEFAULTS)
    for key in config:
        val = values.get(key)
        if val is not None:
            config[key] = str(val)
    return config


def save_config(config, env_path=ENV_PATH):
    """Persist known keys to .env, creating the file if needed."""
    env_path = str(env_path)
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8"):
            pass
    for key, _, _ in FIELD_DEFS:
        set_key(env_path, key, str(config.get(key, DEFAULTS[key])))
    load_dotenv(env_path, override=True)


def get_smtp_port(config):
    try:
        return int(float(config.get("SMTP_PORT", "587")))
    except (TypeError, ValueError):
        return 587


def get_send_delay(config):
    try:
        return float(config.get("SEND_DELAY", "60"))
    except (TypeError, ValueError):
        return 60.0
