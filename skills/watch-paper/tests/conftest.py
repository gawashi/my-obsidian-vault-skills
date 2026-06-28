import sys
from pathlib import Path

# tests/ から見て親（skills/watch-paper）を import パスに追加し fetch_arxiv を解決（CWD 非依存）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
