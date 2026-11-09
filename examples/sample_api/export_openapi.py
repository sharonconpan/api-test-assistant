import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from examples.sample_api.app.main import create_app


output_path = Path(__file__).with_name("openapi.json")
output_path.write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
