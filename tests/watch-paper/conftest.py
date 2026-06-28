import sys
from pathlib import Path

# tests/watch-paper/ から見て ../../skills/watch-paper を import パスに追加（CWD 非依存）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "watch-paper"))
