from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess


class GitAnalysisError(RuntimeError):
    """Error al consultar el repositorio o las revisiones solicitadas."""


@dataclass(frozen=True)
class FileChange:
    status: str
    path: str
    previous_path: str | None = None


@dataclass(frozen=True)
class GitAnalysis:
    repository: str
    base: str
    head: str
    changes: list[FileChange]
    code_diffs: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "repository": self.repository,
            "base": self.base,
            "head": self.head,
            "changes": [asdict(change) for change in self.changes],
        }


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as error:
        raise GitAnalysisError("No se encontró el ejecutable git en PATH.") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or "Error desconocido de Git."
        raise GitAnalysisError(message) from error


def _resolve_revision(repo: Path, revision: str) -> str:
    result = _git(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{revision}^{{commit}}",
        check=False,
    )
    if result.returncode != 0:
        raise GitAnalysisError(f"La referencia Git no existe o no apunta a un commit: {revision}")
    return result.stdout.strip()


def _parse_name_status(output: str) -> list[FileChange]:
    tokens = output.split("\0")
    if tokens and not tokens[-1]:
        tokens.pop()

    changes: list[FileChange] = []
    index = 0
    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        status = status_token[0]
        if status in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise GitAnalysisError("Git devolvió un diff de renombre/copia incompleto.")
            previous_path = tokens[index]
            path = tokens[index + 1]
            index += 2
            changes.append(
                FileChange(
                    status="renamed" if status == "R" else "copied",
                    path=path,
                    previous_path=previous_path,
                )
            )
        else:
            if index >= len(tokens):
                raise GitAnalysisError("Git devolvió una entrada de diff incompleta.")
            path = tokens[index]
            index += 1
            status_names = {
                "A": "added",
                "D": "deleted",
                "M": "modified",
                "T": "type_changed",
                "U": "unmerged",
            }
            changes.append(FileChange(status=status_names.get(status, "modified"), path=path))
    return changes


def analyze_git_changes(repo_path: str | Path, base: str, head: str) -> GitAnalysis:
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise GitAnalysisError(f"La ruta del repositorio no es un directorio: {repo}")

    result = _git(repo, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise GitAnalysisError(f"La ruta no pertenece a un repositorio Git: {repo}")
    repository = str(Path(result.stdout.strip()).resolve())

    base_commit = _resolve_revision(repo, base)
    head_commit = _resolve_revision(repo, head)
    diff = _git(
        repo,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        base_commit,
        head_commit,
        "--",
    )
    changes = _parse_name_status(diff.stdout)
    code_diffs: dict[str, str] = {}

    for change in changes:
        paths = {change.path}
        if change.previous_path:
            paths.add(change.previous_path)
        if not any(path.endswith(".py") for path in paths):
            continue
        patch = _git(
            repo,
            "diff",
            "--no-ext-diff",
            "--unified=0",
            base_commit,
            head_commit,
            "--",
            *sorted(paths),
        )
        code_diffs[change.path] = patch.stdout

    return GitAnalysis(
        repository=repository,
        base=base_commit,
        head=head_commit,
        changes=changes,
        code_diffs=code_diffs,
    )
