from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.service import process_paths

parser = argparse.ArgumentParser(description="Processa um diretório de transcrições TXT.")
parser.add_argument("directory", type=Path)
parser.add_argument("--name", default="Lote local")
args = parser.parse_args()
paths = sorted(args.directory.glob("*.txt"))
if not paths:
    parser.error("Nenhum TXT encontrado")
print(json.dumps(process_paths(paths, args.name), ensure_ascii=False, indent=2))
