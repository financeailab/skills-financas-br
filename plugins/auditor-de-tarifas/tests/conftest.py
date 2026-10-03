import sys
from pathlib import Path

# os testes importam `scripts.engine...` da skill
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "auditor-de-tarifas"))
