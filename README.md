# QlubSender

Generic club mail sender: templated bulk mail via SMTP, with a PySide6 GUI
(one window, four tabs) and a CLI. Recipient list, template and subject live
in `data/` (local only, never committed); dummy starting content lives in
`examples/`.

## Setup (fresh clone)

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp examples/.env.example .env   # then edit .env with real credentials
# data/ files are seeded automatically from examples/ on first start,
# or copy manually:
cp examples/recipients.json data/recipients.json
cp examples/template.txt data/template.txt
cp examples/subject.txt data/subject.txt
```

`data/recipients.json`, `data/template.txt`, `data/subject.txt` and `.env`
are productive/private and are **never committed** — see `.gitignore`.
Only the dummy content in `examples/` is published.

Requires Python 3.10+ and the `git` executable (for `data/` version history).

## Run

```bash
venv/bin/python main.py         # GUI
# or CLI:
venv/bin/python cli.py data/template.txt -r data/recipients.json -s "Invitation" -d 60
```

## Layout

- `main.py` — GUI entry point
- `cli.py` — command-line interface (thin wrapper around `mailer.sender`)
- `mailer/` — shared logic
  - `config.py` — `.env` settings (`SMTP_*`, `FROM_EMAIL`, `FROM_NAME`,
    `BCC_EMAIL` single/optional, `SEND_DELAY`)
  - `sender.py` — mail creation, SMTP, templated bulk send with
    progress/cancel callbacks
  - `recipients.py` — fixed schema `firstName | lastName | mail`,
    validation, CSV import/export
  - `history.py` — nested-git versioning of `data/` via subprocess
  - `paths.py` — central file locations
- `gui/` — PySide6 tabs: Compose & Send, Recipients, History, Settings
- `data/` — your private content (ignored by git, versioned in a nested repo):
  `template.txt`, `subject.txt`, `recipients.json`
- `examples/` — dummy content for new users (committed)

## Behavior notes

- Saving in Compose or Recipients auto-commits to `data/.git`.
- History tab shows per-file log, diff of each commit, and restore
  (restore itself is committed).
- `.env` holds the password in plain text and is **never**
  committed — see `.gitignore`.
- Sending runs in a worker thread: progress bar, log pane, Cancel,
  test-send of first recipient (`Test send`), `Send all others` skips the
  tester, live Jinja preview.
- `BCC_EMAIL` empty = no extra copy.

See `LICENSE` for terms.
