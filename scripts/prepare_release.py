from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

SEMVER_TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PROJECT_VERSION = re.compile(
    r'^\[project\]\n(?:(?!^\[).)*?^version\s*=\s*"([^"]+)"',
    re.MULTILINE | re.DOTALL,
)
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT_FILES = frozenset({"findings.md", "progress.md", "task_plan.md"})


def _validate_repository(repository: str) -> None:
    if REPOSITORY.fullmatch(repository) is None:
        raise ValueError("repository must be OWNER/REPOSITORY")


def read_project_version(pyproject: Path) -> str:
    matches = PROJECT_VERSION.findall(pyproject.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise ValueError("pyproject.toml must contain exactly one project version")
    return matches[0]


def validate_release_tag(tag: str, pyproject: Path) -> str:
    if SEMVER_TAG.fullmatch(tag) is None:
        raise ValueError("release tag must be vMAJOR.MINOR.PATCH")
    tag_version = tag[1:]
    project_version = read_project_version(pyproject)
    if tag_version != project_version:
        raise ValueError(
            f"release tag {tag_version} does not match project version {project_version}"
        )
    return tag_version


def render_installer(
    template: Path,
    output: Path,
    repository: str,
    version: str,
) -> None:
    _validate_repository(repository)
    text = template.read_text(encoding="utf-8")
    replacements = {
        "__NEBULA_MCP_REPOSITORY__": repository,
        "__NEBULA_MCP_VERSION__": version,
    }
    for token, value in replacements.items():
        if text.count(token) != 1:
            raise ValueError(f"installer template must contain {token} exactly once")
        text = text.replace(token, value)
    output.write_text(text, encoding="utf-8")


def write_checksums(assets: Sequence[Path], output: Path) -> None:
    lines = [
        f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}"
        for asset in sorted(assets, key=lambda item: item.name)
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_release_notes(repository: str, tag: str, output: Path) -> None:
    _validate_repository(repository)
    if SEMVER_TAG.fullmatch(tag) is None:
        raise ValueError("release tag must be vMAJOR.MINOR.PATCH")
    url = f"https://github.com/{repository}/releases/download/{tag}/install.py"
    output.write_text(
        f"# nebula-mcp {tag}\n\n"
        "The installer does not collect database connection settings. "
        "Configure them in Codex Desktop after installation.\n\n"
        "```bash\n"
        f"curl -fL -o install.py {url}\n"
        "python3 install.py\n\n"
        "# upgrade\n"
        "python3 install.py\n\n"
        "# uninstall\n"
        "python3 install.py --uninstall\n"
        "```\n\n"
        "Windows PowerShell:\n\n"
        "```powershell\n"
        f"Invoke-WebRequest -Uri \"{url}\" -OutFile install.py\n"
        "py -3 install.py\n\n"
        "# upgrade\n"
        "py -3 install.py\n\n"
        "# uninstall\n"
        "py -3 install.py --uninstall\n"
        "```\n",
        encoding="utf-8",
    )


def _distribution_assets(dist: Path, version: str) -> tuple[Path, Path]:
    expected_wheel = dist / f"nebula_mcp-{version}-py3-none-any.whl"
    expected_sdist = dist / f"nebula_mcp-{version}.tar.gz"
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if wheels != [expected_wheel] or sdists != [expected_sdist]:
        raise ValueError(
            "dist must contain exactly one wheel and one sdist for the project version"
        )
    return expected_wheel, expected_sdist


def validate_public_sdist(sdist: Path) -> None:
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            for member in archive.getmembers():
                parts = PurePosixPath(member.name).parts
                relative = parts[1:] if len(parts) > 1 else parts
                is_private_root_file = (
                    len(relative) == 1 and relative[0] in PRIVATE_ROOT_FILES
                )
                is_private_docs = relative[:2] == ("docs", "superpowers")
                if is_private_root_file or is_private_docs:
                    raise ValueError("sdist contains private planning evidence")
    except (OSError, tarfile.TarError) as error:
        raise ValueError("sdist must be a readable gzip tar archive") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare deterministic GitHub Release assets")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dist", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    version = validate_release_tag(args.tag, ROOT / "pyproject.toml")
    wheel, sdist = _distribution_assets(args.dist, version)
    validate_public_sdist(sdist)
    installer = args.dist / "install.py"
    render_installer(
        ROOT / "installer/install.py.in",
        installer,
        args.repository,
        version,
    )
    write_checksums([wheel, sdist, installer], args.dist / "SHA256SUMS")
    write_release_notes(args.repository, args.tag, args.dist / "RELEASE_NOTES.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
