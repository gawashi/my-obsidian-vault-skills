import json
from pathlib import Path

import _common as cm


def test_resolve_data_dir_default_is_cwd_watch_paper():
    assert cm.resolve_data_dir(None) == Path.cwd() / "watch-paper"


def test_resolve_data_dir_override():
    assert cm.resolve_data_dir("/tmp/foo") == Path("/tmp/foo")


def test_now_local_date_is_iso_yyyy_mm_dd():
    s = cm.now_local_date()
    # YYYY-MM-DD: three dash-separated numeric parts of widths 4-2-2
    parts = s.split("-")
    assert len(parts) == 3
    assert [len(p) for p in parts] == [4, 2, 2]
    assert all(p.isdigit() for p in parts)


def test_setup_data_dir_creates_state_and_digests(tmp_path):
    data_dir = cm.setup_data_dir(str(tmp_path / "wp"))
    assert data_dir == tmp_path / "wp"
    assert (data_dir / "state").is_dir()
    assert (data_dir / "digests").is_dir()


def test_load_run_inputs_reads_both(tmp_path):
    data_dir = tmp_path / "wp"
    (data_dir).mkdir()
    (data_dir / "candidates.json").write_text(
        json.dumps({"themes": [{"id": "t1"}]}), encoding="utf-8")
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps({"t1": {}}), encoding="utf-8")
    candidates_doc, scores = cm.load_run_inputs(data_dir, str(scores_path))
    assert candidates_doc == {"themes": [{"id": "t1"}]}
    assert scores == {"t1": {}}


def test_load_run_inputs_missing_file_returns_none(tmp_path):
    data_dir = tmp_path / "wp"
    data_dir.mkdir()
    candidates_doc, scores = cm.load_run_inputs(data_dir, str(tmp_path / "nope.json"))
    assert candidates_doc is None
    assert scores is None


def test_config_path_is_data_dir_config_json(tmp_path):
    assert cm.config_path(tmp_path) == tmp_path / "config.json"


def test_ensure_config_copies_template_when_absent(tmp_path):
    path, created = cm.ensure_config(tmp_path)
    assert created is True
    assert path == tmp_path / "config.json"
    assert path.read_text(encoding="utf-8") == cm.TEMPLATE_PATH.read_text(encoding="utf-8")


def test_ensure_config_is_noop_when_present(tmp_path):
    existing = tmp_path / "config.json"
    existing.write_text('{"defaults": {}, "themes": []}', encoding="utf-8")
    path, created = cm.ensure_config(tmp_path)
    assert created is False
    assert path == existing
    assert path.read_text(encoding="utf-8") == '{"defaults": {}, "themes": []}'
