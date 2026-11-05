"""Shared path constants for the QlubSender project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ENV_PATH = PROJECT_ROOT / ".env"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

TEMPLATE_PATH = DATA_DIR / "template.txt"
RECIPIENTS_PATH = DATA_DIR / "recipients.json"
SUBJECT_PATH = DATA_DIR / "subject.txt"

LOG_PATH = PROJECT_ROOT / "email_sender.log"

SEEDED_FILES = ("template.txt", "subject.txt", "recipients.json")


def ensure_data_files():
    """Seed missing data/ files from examples/ (first run).

    Copies each of template.txt / subject.txt / recipients.json from
    ``examples/`` to ``data/`` only if the destination does not exist.
    Returns the list of seeded filenames. Never overwrites productive data.
    """
    seeded = []
    for name in SEEDED_FILES:
        dest = DATA_DIR / name
        src = EXAMPLES_DIR / name
        if not dest.exists() and src.exists():
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(src.read_bytes())
                seeded.append(name)
            except OSError:
                pass
    return seeded
