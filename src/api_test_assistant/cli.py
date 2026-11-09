from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .git_changes import GitAnalysisError, analyze_git_changes
from .impact import correlate_impact
from .openapi_diff import (
    OpenAPIAnalysisError,
    load_and_compare_openapi,
    load_spec_from_revision,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara cambios Git y OpenAPI y emite impactos como JSON."
    )
    parser.add_argument("--base", required=True, help="Referencia Git base.")
    parser.add_argument("--head", required=True, help="Referencia Git destino.")
    parser.add_argument("--repo", default=".", help="Ruta al repositorio Git (por defecto: directorio actual).")
    parser.add_argument(
        "--spec",
        default="examples/sample_api/openapi.json",
        help="Ruta relativa a la especificación OpenAPI versionada.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Archivo JSON de salida (por defecto, stdout).",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        git_analysis = analyze_git_changes(args.repo, args.base, args.head)
    except GitAnalysisError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        openapi_diff = load_and_compare_openapi(
            git_analysis.repository,
            git_analysis.base,
            git_analysis.head,
            args.spec,
        )
        base_spec = load_spec_from_revision(git_analysis.repository, git_analysis.base, args.spec)
        head_spec = load_spec_from_revision(git_analysis.repository, git_analysis.head, args.spec)
    except OpenAPIAnalysisError as error:
        result = {
            "git": git_analysis.to_dict(),
            "openapi": {"status": "no_se_pudo_analizar", "error": str(error)},
            "impacts": [],
        }
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        _write_output(args.output, output)
        return 2

    impacts = correlate_impact(git_analysis, openapi_diff, base_spec, head_spec)
    result = {
        "git": git_analysis.to_dict(),
        "openapi": openapi_diff,
        "impacts": impacts,
    }
    _write_output(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


def _write_output(destination: str, content: str) -> None:
    if destination == "-":
        sys.stdout.write(content)
        return
    Path(destination).write_text(content, encoding="utf-8")
