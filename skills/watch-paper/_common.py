#!/usr/bin/env python3
"""watch-paper: shared plumbing for the fetch / render / commit scripts.

Kept dependency-free (stdlib only) so every script and the unit tests can
import it without the `arxiv` dependency installed.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
TEMPLATE_PATH = Path(__file__).parent / "config.example.json"


def config_path(data_dir):
    """Path of the live config: <data_dir>/config.json."""
    return Path(data_dir) / "config.json"


def ensure_config(data_dir):
    """Copy the bundled template into the data dir if no live config exists.

    Returns (path, created): created is True when the template was copied to
    create a new config (the caller should stop and let the user edit it),
    False when an existing config.json is already present. Raises OSError if
    the template cannot be read or copied.
    """
    dst = config_path(data_dir)
    if dst.exists():
        return dst, False
    shutil.copyfile(TEMPLATE_PATH, dst)
    print(f"[watch-paper] created {dst} from template", file=sys.stderr)
    return dst, True


def resolve_data_dir(arg_data_dir):
    """--data-dir if given, else <cwd>/watch-paper."""
    if arg_data_dir:
        return Path(arg_data_dir)
    return Path.cwd() / "watch-paper"


def load_config(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def now_local_date():
    return datetime.now().date().isoformat()


def setup_data_dir(arg_data_dir):
    """Resolve the data dir, print the banner, ensure state/ and digests/ exist.

    Raises OSError if the directories cannot be created (caller returns rc=2).
    """
    data_dir = resolve_data_dir(arg_data_dir)
    print(f"[watch-paper] data_dir = {data_dir}", file=sys.stderr)
    (data_dir / "state").mkdir(parents=True, exist_ok=True)
    (data_dir / "digests").mkdir(parents=True, exist_ok=True)
    return data_dir


def load_run_inputs(data_dir, scores_path):
    """Read scores.json + candidates.json for render/commit.

    Returns (candidates_doc, scores); (None, None) on read/parse error (logged).
    """
    try:
        with open(scores_path, "r", encoding="utf-8") as f:
            scores = json.load(f)
        with (data_dir / "candidates.json").open("r", encoding="utf-8") as f:
            candidates_doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[watch-paper] FATAL: cannot read scores/candidates: {e}",
              file=sys.stderr)
        return None, None
    return candidates_doc, scores
