from __future__ import annotations

from typer.testing import CliRunner

from bikematch.cli import app

runner = CliRunner()


def test_doctor_runs_and_reports_every_check():
    result = runner.invoke(app, ["doctor"])
    for label in ["python", "torch", "faiss", "sqlalchemy", "pillow", "/workspace/bikematch"]:
        assert label in result.stdout, result.stdout


def test_doctor_lists_unimplemented_phase2_checks():
    result = runner.invoke(app, ["doctor"])
    assert "Not yet implemented (Phase 2+)" in result.stdout
    assert "eBay API" in result.stdout


def test_doctor_exits_zero_when_every_check_passes():
    # On the CI/dev environment the full lockfile is installed, so every
    # check should genuinely pass -- this is functional, not a stub.
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout
