"""Version history for data/ via a nested git repo (subprocess, no extra deps)."""

import subprocess
from datetime import datetime
from pathlib import Path

TRACKED_FILES = ["template.txt", "subject.txt", "recipients.json"]


class GitError(RuntimeError):
    pass


def _run_git(data_dir, *args):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise GitError("git executable not found. Please install git.")
    except subprocess.TimeoutExpired:
        raise GitError("git command timed out")
    if proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout or "git failed").strip())
    return proc.stdout


def is_repo(data_dir):
    return (Path(data_dir) / ".git").is_dir()


def ensure_repo(data_dir):
    """Init repo + initial commit if needed. Returns (repo_ok, message)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not is_repo(data_dir):
            _run_git(data_dir, "init")
            _run_git(data_dir, "add", ".")
            try:
                _run_git(data_dir, "commit", "-m", "initial import", "--quiet")
            except GitError as e:
                if "nothing to commit" not in str(e):
                    raise
            return True, "Initialized git history in data/"
        return True, "History repo ready"
    except GitError as e:
        return False, str(e)


def commit(data_dir, message=None, filenames=None):
    """Stage + commit tracked files if anything changed. Returns (committed, info)."""
    data_dir = Path(data_dir)
    if not is_repo(data_dir):
        ok, msg = ensure_repo(data_dir)
        if not ok:
            return False, msg
    files = filenames or TRACKED_FILES
    existing = [f for f in files if (data_dir / f).exists()]
    if not existing:
        return False, "Nothing to commit"
    try:
        _run_git(data_dir, "add", *existing)
        status = _run_git(data_dir, "status", "--porcelain").strip()
        if not status:
            return False, "No changes"
        msg = message or f"update {datetime.now():%Y-%m-%d %H:%M:%S}"
        _run_git(data_dir, "commit", "-m", msg, "--quiet")
        short = _run_git(data_dir, "rev-parse", "--short", "HEAD").strip()
        return True, f"Committed {short}: {msg}"
    except GitError as e:
        if "nothing to commit" in str(e):
            return False, "No changes"
        return False, str(e)


def log(data_dir, limit=50):
    """Return list of {hash, short, date, message} (newest first)."""
    data_dir = Path(data_dir)
    if not is_repo(data_dir):
        return []
    try:
        out = _run_git(
            data_dir, "log", f"--max-count={limit}",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s", "--date=iso",
        )
    except GitError:
        return []
    entries = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            entries.append(
                {"hash": parts[0], "short": parts[1], "date": parts[2], "message": parts[3]}
            )
    return entries


def file_log(data_dir, filename, limit=50):
    if not is_repo(Path(data_dir)):
        return []
    try:
        out = _run_git(
            Path(data_dir), "log", f"--max-count={limit}",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s", "--date=iso", "--", filename,
        )
    except GitError:
        return []
    entries = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            entries.append(
                {"hash": parts[0], "short": parts[1], "date": parts[2], "message": parts[3]}
            )
    return entries


def diff(data_dir, filename, rev=None, rev2=None):
    """Diff of filename: worktree vs HEAD (rev=None) or between revs."""
    args = ["diff", "--", filename] if rev is None else ["diff", rev, rev2 or "", "--", filename]
    args = [a for a in args if a]
    try:
        return _run_git(Path(data_dir), *args)
    except GitError as e:
        return str(e)


def show(data_dir, filename, rev):
    try:
        return _run_git(Path(data_dir), "show", f"{rev}:{filename}")
    except GitError as e:
        return f"Cannot show {filename} at {rev}: {e}"


def restore(data_dir, filename, rev):
    """Checkout filename from rev, then commit the restore."""
    data_dir = Path(data_dir)
    try:
        _run_git(data_dir, "checkout", rev, "--", filename)
    except GitError as e:
        return False, str(e)
    return commit(data_dir, message=f"restore {filename} from {rev[:7]}", filenames=[filename])
