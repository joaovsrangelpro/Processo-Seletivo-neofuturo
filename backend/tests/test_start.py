from pathlib import Path
import subprocess

import pytest


START_SCRIPT = Path(__file__).resolve().parents[1] / "start.sh"


@pytest.fixture
def stub_commands(tmp_path: Path) -> tuple[Path, Path]:
    calls = tmp_path / "calls"
    for name, body in {
        "alembic": 'printf "alembic %s\\n" "$*" >> "$CALLS"\nexit "${MIGRATION_EXIT:-0}"\n',
        "uvicorn": 'printf "uvicorn %s\\n" "$*" >> "$CALLS"\n',
    }.items():
        command = tmp_path / name
        command.write_text("#!/bin/sh\n" + body, encoding="ascii")
        command.chmod(0o755)
    return tmp_path, calls


@pytest.mark.parametrize("port", [None, "19081"])
def test_start_applies_migrations_before_uvicorn(
    stub_commands: tuple[Path, Path],
    port: str | None,
) -> None:
    commands, calls = stub_commands
    environment = {"PATH": str(commands), "CALLS": str(calls)}
    if port is not None:
        environment["PORT"] = port

    result = subprocess.run(
        ["/bin/sh", str(START_SCRIPT)], env=environment, capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert calls.read_text(encoding="ascii").splitlines() == [
        "alembic upgrade head",
        f"uvicorn app.main:app --host 0.0.0.0 --port {port or '8000'}",
    ]


def test_start_does_not_launch_uvicorn_when_migrations_fail(
    stub_commands: tuple[Path, Path],
) -> None:
    commands, calls = stub_commands

    result = subprocess.run(
        ["/bin/sh", str(START_SCRIPT)],
        env={"PATH": str(commands), "CALLS": str(calls), "MIGRATION_EXIT": "1"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert calls.read_text(encoding="ascii").splitlines() == ["alembic upgrade head"]
