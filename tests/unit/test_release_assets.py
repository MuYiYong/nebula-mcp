from __future__ import annotations

import io
import re
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

from scripts import prepare_release

ROOT = Path(__file__).resolve().parents[2]


def write_test_sdist(path: Path, *members: str) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for member in members:
            payload = b"test fixture\n"
            info = tarfile.TarInfo(member)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def workflow_block(text: str, header: str) -> str:
    lines = text.splitlines()
    start = lines.index(header)
    indentation = len(header) - len(header.lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and len(line) - len(line.lstrip()) <= indentation:
            end = index
            break
    return "\n".join(lines[start:end]).rstrip()


def workflow_step_names(job: str) -> list[str]:
    return re.findall(r"^      - name: (.+)$", job, re.MULTILINE)


def workflow_run_script(step: str) -> str:
    for line in step.splitlines():
        if line.startswith("        run: "):
            value = line.removeprefix("        run: ")
            if value != "|":
                return value
            run = workflow_block(step, "        run: |").splitlines()[1:]
            return textwrap.dedent("\n".join(run))
    raise AssertionError("workflow step must contain an executable run value")


def executable_shell_lines(script: str) -> list[str]:
    return [
        line.strip()
        for line in script.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def workflow_step_run_lines(job: str, name: str) -> list[str]:
    step = workflow_block(job, f"      - name: {name}")
    return executable_shell_lines(workflow_run_script(step))


def workflow_yaml_data_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def assert_lines_in_order(lines: list[str], required: list[str]) -> None:
    for line in required:
        assert line in lines
    positions = [lines.index(line) for line in required]
    assert positions == sorted(positions)


def test_tag_must_exactly_match_project_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "nebula-mcp"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    assert prepare_release.validate_release_tag("v0.1.0", pyproject) == "0.1.0"
    with pytest.raises(ValueError, match="does not match"):
        prepare_release.validate_release_tag("v0.2.0", pyproject)


def test_rendered_installer_contains_exact_repository_and_version(tmp_path: Path) -> None:
    output = tmp_path / "install.py"

    prepare_release.render_installer(
        template=ROOT / "installer/install.py.in",
        output=output,
        repository="example-org/nebula-mcp",
        version="0.1.0",
    )

    text = output.read_text(encoding="utf-8")
    assert 'TARGET_REPOSITORY = "example-org/nebula-mcp"' in text
    assert 'TARGET_VERSION = "0.1.0"' in text
    assert "__NEBULA_MCP_" not in text


def test_rendered_installer_executes_version_smoke(tmp_path: Path) -> None:
    output = tmp_path / "install.py"
    prepare_release.render_installer(
        template=ROOT / "installer/install.py.in",
        output=output,
        repository="example-org/nebula-mcp",
        version="0.1.0",
    )

    completed = subprocess.run(
        [sys.executable, str(output), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "0.1.0\n"
    assert completed.stderr == ""


def test_checksums_are_sorted_and_release_notes_use_exact_asset_url(tmp_path: Path) -> None:
    wheel = tmp_path / "nebula_mcp-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "nebula_mcp-0.1.0.tar.gz"
    installer = tmp_path / "install.py"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    installer.write_bytes(b"installer")
    checksums = tmp_path / "SHA256SUMS"
    notes = tmp_path / "RELEASE_NOTES.md"

    prepare_release.write_checksums([wheel, sdist, installer], checksums)
    prepare_release.write_release_notes("example-org/nebula-mcp", "v0.1.0", notes)

    names = [line.split("  ", 1)[1] for line in checksums.read_text().splitlines()]
    assert names == sorted(names)
    assert (
        "The installer does not collect database connection settings. "
        "Configure them in Codex Desktop after installation.\n\n"
        "```bash\n"
        "curl -fL -o install.py "
        "https://github.com/example-org/nebula-mcp/releases/download/v0.1.0/install.py\n"
        "python3 install.py\n\n"
        "# upgrade\n"
        "python3 install.py\n\n"
        "# uninstall\n"
        "python3 install.py --uninstall\n"
        "```\n"
    ) in notes.read_text(encoding="utf-8")
    notes_text = notes.read_text(encoding="utf-8")
    for required in (
        "Windows PowerShell",
        "Invoke-WebRequest",
        "py -3 install.py",
        "py -3 install.py --uninstall",
    ):
        assert required in notes_text


def test_cli_prepares_only_exact_current_build_assets(tmp_path: Path) -> None:
    wheel = tmp_path / "nebula_mcp-0.1.4-py3-none-any.whl"
    sdist = tmp_path / "nebula_mcp-0.1.4.tar.gz"
    wheel.write_bytes(b"wheel")
    write_test_sdist(sdist, "nebula_mcp-0.1.4/src/nebula_mcp/__init__.py")

    result = prepare_release.main(
        [
            "--repository",
            "local-validation/nebula-mcp",
            "--tag",
            "v0.1.4",
            "--dist",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert [
        line.split("  ", 1)[1]
        for line in (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    ] == ["install.py", wheel.name, sdist.name]
    assert (tmp_path / "RELEASE_NOTES.md").is_file()


@pytest.mark.parametrize(
    "member",
    [
        "nebula_mcp-0.1.4/findings.md",
        "nebula_mcp-0.1.4/progress.md",
        "nebula_mcp-0.1.4/task_plan.md",
        "nebula_mcp-0.1.4/docs/superpowers/plan.md",
    ],
)
def test_cli_rejects_sdist_with_private_planning_evidence(
    tmp_path: Path, member: str
) -> None:
    (tmp_path / "nebula_mcp-0.1.4-py3-none-any.whl").write_bytes(b"wheel")
    write_test_sdist(tmp_path / "nebula_mcp-0.1.4.tar.gz", member)

    with pytest.raises(ValueError, match="private planning evidence"):
        prepare_release.main(
            [
                "--repository",
                "local-validation/nebula-mcp",
                "--tag",
                "v0.1.4",
                "--dist",
                str(tmp_path),
            ]
        )


def test_cli_rejects_old_or_extra_distribution_assets(tmp_path: Path) -> None:
    (tmp_path / "nebula_mcp-0.1.4-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "nebula_mcp-0.1.4.tar.gz").write_bytes(b"sdist")
    (tmp_path / "nebula_mcp-0.1.2-py3-none-any.whl").write_bytes(b"old wheel")

    with pytest.raises(ValueError, match="exactly one wheel and one sdist"):
        prepare_release.main(
            [
                "--repository",
                "local-validation/nebula-mcp",
                "--tag",
                "v0.1.4",
                "--dist",
                str(tmp_path),
            ]
        )


def assert_release_workflow_contract(workflow: str) -> None:
    validate = workflow_block(workflow, "  validate:")
    compatibility = workflow_block(workflow, "  installer-compatibility:")
    publish = workflow_block(workflow, "  publish:")

    assert workflow_block(workflow, "permissions:") == "permissions:\n  contents: read"
    assert workflow_block(validate, "    permissions:") == (
        "    permissions:\n      contents: read"
    )
    assert workflow_block(publish, "    permissions:") == (
        "    permissions:\n      contents: write"
    )
    assert "needs: [validate, installer-compatibility]" in workflow_yaml_data_lines(
        publish
    )
    assert "os: [ubuntu-latest, windows-latest]" in workflow_yaml_data_lines(
        compatibility
    )

    assert workflow_step_names(validate) == [
        "Checkout source",
        "Set up Python",
        "Install development dependencies",
        "Run test suite",
        "Run Ruff including installer template",
        "Run strict mypy",
        "Build distributions",
        "Prepare and validate release assets",
        "Validate clean wheel and stdio",
        "Run installer integration tests",
        "Upload verified release bundle",
    ]
    assert workflow_step_names(publish) == [
        "Download verified release bundle",
        "Verify tag and publish exact assets",
    ]
    assert workflow_step_names(compatibility) == [
        "Checkout source",
        "Set up Python",
        "Install development dependencies",
        "Run installer unit and integration compatibility",
        "Run rendered installer smoke",
    ]

    expected_uses = [
        "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0",
        "uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1",
        "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0",
        "uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1",
    ]
    uses_lines = [
        line.strip()
        for line in workflow.splitlines()
        if re.match(r"^\s+uses:\s", line)
    ]
    assert uses_lines == expected_uses

    checkout = workflow_block(validate, "      - name: Checkout source")
    assert "persist-credentials: false" in workflow_yaml_data_lines(checkout)
    setup = workflow_block(validate, "      - name: Set up Python")
    assert 'python-version: "3.13"' in workflow_yaml_data_lines(setup)

    compatibility_commands = {
        "Install development dependencies": "python -m pip install '.[dev]'",
        "Run installer unit and integration compatibility": (
            "python -m pytest tests/unit/test_installer.py "
            "tests/integration/test_installer_cli.py -q"
        ),
        "Run rendered installer smoke": (
            "python -m pytest tests/unit/test_release_assets.py -q "
            "-k rendered_installer_executes_version_smoke"
        ),
    }
    for name, command in compatibility_commands.items():
        assert command in workflow_step_run_lines(compatibility, name)

    quality_steps = {
        "Install development dependencies": "python -m pip install '.[dev]'",
        "Run test suite": "python -m pytest -q",
        "Run Ruff including installer template": (
            "python -m ruff check --extension in:python ."
        ),
        "Run strict mypy": "python -m mypy src",
        "Build distributions": "python -m build",
        "Run installer integration tests": (
            "python -m pytest tests/integration/test_installer_cli.py -q"
        ),
    }
    for name, command in quality_steps.items():
        assert command in workflow_step_run_lines(validate, name)

    prepare = workflow_step_run_lines(validate, "Prepare and validate release assets")
    assert_lines_in_order(
        prepare,
        [
            "python scripts/prepare_release.py \\",
            '--repository "$GITHUB_REPOSITORY" \\',
            '--tag "$GITHUB_REF_NAME" \\',
            "--dist dist",
            'installer_version="$(python dist/install.py --version)"',
            'test "$installer_version" = "${GITHUB_REF_NAME#v}"',
            "(cd dist && shasum -a 256 -c SHA256SUMS)",
        ],
    )

    clean_wheel = workflow_step_run_lines(validate, "Validate clean wheel and stdio")
    assert_lines_in_order(
        clean_wheel,
        [
            'python -m venv "$RUNNER_TEMP/nebula-wheel"',
            '"$RUNNER_TEMP/nebula-wheel/bin/python" -m pip install dist/*.whl',
            '"$RUNNER_TEMP/nebula-wheel/bin/python" -m pip check',
            '"$RUNNER_TEMP/nebula-wheel/bin/python" -c \'import nebula_mcp\'',
            (
                'wheel_version="$("$RUNNER_TEMP/nebula-wheel/bin/python" '
                '-m nebula_mcp --version)"'
            ),
            'test "$wheel_version" = "nebula-mcp ${GITHUB_REF_NAME#v}"',
            'NEBULA_WHEEL_PYTHON="$RUNNER_TEMP/nebula-wheel/bin/python" \\',
            "python -m pytest tests/protocol/test_stdio.py -q",
        ],
    )

    final = workflow_block(publish, "      - name: Verify tag and publish exact assets")
    final_script = workflow_run_script(final)
    syntax = subprocess.run(
        ["bash", "-n"],
        input=final_script,
        capture_output=True,
        check=False,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    final_lines = executable_shell_lines(final_script)
    ordered_boundary = [
        'test "$release_files" = "$expected_files"',
        'test "$manifest_files" = "$expected_manifest"',
        "(cd dist && shasum -a 256 -c SHA256SUMS)",
        'gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$GITHUB_REF_NAME" \\',
        'test "$target_type" = "commit"',
        'test "$target_sha" = "$GITHUB_SHA"',
        'gh release create "$GITHUB_REF_NAME" \\',
    ]
    assert_lines_in_order(final_lines, ordered_boundary)
    assert final_lines.index('test "$target_sha" = "$GITHUB_SHA"') + 1 == final_lines.index(
        'gh release create "$GITHUB_REF_NAME" \\'
    )
    assert 'wheel="dist/nebula_mcp-${version}-py3-none-any.whl"' in final_lines
    assert 'sdist="dist/nebula_mcp-${version}.tar.gz"' in final_lines
    assert '"$wheel" "$sdist" dist/install.py dist/SHA256SUMS \\' in final_lines
    assert '--repo "$GITHUB_REPOSITORY" \\' in final_lines
    assert "--verify-tag \\" in final_lines
    assert all("*" not in line for line in final_lines)

    token_lines = [
        line.strip()
        for line in workflow.splitlines()
        if re.match(r"^\s+GH_TOKEN:\s", line)
    ]
    assert token_lines == ["GH_TOKEN: ${{ github.token }}"]
    validate_run_lines = [
        line
        for name in workflow_step_names(validate)
        if "        run:" in workflow_block(validate, f"      - name: {name}")
        for line in workflow_step_run_lines(validate, name)
    ]
    assert all(not line.startswith("gh release create") for line in validate_run_lines)
    assert "local-validation/nebula-mcp" not in workflow
    assert "NEBULA_HOSTS" not in workflow
    assert "NEBULA_PASSWORD" not in workflow
    assert "PYPI" not in workflow.upper()


def test_release_workflow_is_ordered_and_least_privileged_at_publish_boundary() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert_release_workflow_contract(workflow)


@pytest.mark.parametrize(
    ("original", "commented"),
    [
        (
            '          test "$target_sha" = "$GITHUB_SHA"',
            '          # test "$target_sha" = "$GITHUB_SHA"',
        ),
        (
            "          (cd dist && shasum -a 256 -c SHA256SUMS)",
            "          # (cd dist && shasum -a 256 -c SHA256SUMS)",
        ),
        (
            "        run: python -m pytest -q",
            "        run: # python -m pytest -q",
        ),
    ],
)
def test_release_workflow_contract_rejects_commented_executable_gate(
    original: str,
    commented: str,
) -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert_release_workflow_contract(workflow)
    position = workflow.rfind(original)
    assert position >= 0
    mutated = workflow[:position] + workflow[position:].replace(original, commented, 1)

    with pytest.raises(AssertionError):
        assert_release_workflow_contract(mutated)
