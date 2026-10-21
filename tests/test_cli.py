from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lifeos.cli.main import cli


def test_cli_keygen():
    runner = CliRunner()
    result = runner.invoke(cli, ["keygen"])
    assert result.exit_code == 0
    assert "Generated AES-256-GCM Key:" in result.output
    assert "LIFEOS_ENCRYPTION_KEY=" in result.output


def test_cli_tasks_list():
    runner = CliRunner()
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "tasks": [
                {"id": "t1", "title": "Buy groceries", "status": "open", "priority": "high", "due_date": "2026-10-25"},
                {"id": "t2", "title": "Pay bills", "status": "completed", "priority": "low", "due_date": "2026-10-20"},
            ]
        }
        mock_get.return_value = mock_resp

        # Test listing all
        result = runner.invoke(cli, ["tasks", "list"])
        assert result.exit_code == 0
        assert "Buy groceries" in result.output
        assert "Pay bills" in result.output

        # Test status filtering
        result_filtered = runner.invoke(cli, ["tasks", "list", "--status", "open"])
        assert result_filtered.exit_code == 0
        assert "Buy groceries" in result_filtered.output
        assert "Pay bills" not in result_filtered.output


def test_cli_schedule_list_and_add():
    runner = CliRunner()
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            {"id": "s1", "command": "check emails", "interval_seconds": 3600, "is_active": True, "total_runs": 2, "last_run": "2026-10-21"}
        ]
        mock_get.return_value = mock_resp

        result = runner.invoke(cli, ["schedule", "list"])
        assert result.exit_code == 0
        assert "check emails" in result.output

    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "sched_123"}
        mock_post.return_value = mock_resp

        result = runner.invoke(cli, ["schedule", "add", "summarize day", "--interval", "1800"])
        assert result.exit_code == 0
        assert "Schedule registered. ID: sched_123" in result.output


def test_cli_privacy():
    runner = CliRunner()
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "cloud_llm_requests_blocked": 0,
            "third_party_transmissions": 0,
            "local_ollama_executions": 5,
            "compliance_rate": "100%",
        }
        mock_get.return_value = mock_resp

        result = runner.invoke(cli, ["privacy"])
        assert result.exit_code == 0
        assert "100%" in result.output
