"""Tests for --dry-run flag across all mutative commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


def _parse_dry_run(result):
    """Parse dry-run JSON output and assert basic structure."""
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
    data = json.loads(result.output)
    assert data["dry_run"] is True
    return data


# ---------------------------------------------------------------------------
# handle_dry_run unit test
# ---------------------------------------------------------------------------


class TestHandleDryRun:
    def test_outputs_json_and_exits(self):
        import io
        import sys

        import typer

        from ga_cli.utils.dry_run import handle_dry_run

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            handle_dry_run("create", "POST", "properties/123", {"key": "val"})
        except typer.Exit as e:
            assert e.exit_code == 0
        finally:
            sys.stdout = old_stdout

        data = json.loads(captured.getvalue())
        assert data["dry_run"] is True
        assert data["action"] == "create"
        assert data["method"] == "POST"
        assert data["resource"] == "properties/123"
        assert data["body"] == {"key": "val"}
        assert data["idempotent"] is False

    def test_delete_is_idempotent(self):
        import io
        import sys

        import typer

        from ga_cli.utils.dry_run import handle_dry_run

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            handle_dry_run("delete", "DELETE", "properties/123", None)
        except typer.Exit:
            pass
        finally:
            sys.stdout = old_stdout

        data = json.loads(captured.getvalue())
        assert data["idempotent"] is True
        assert "body" not in data

    def test_update_mask_included(self):
        import io
        import sys

        import typer

        from ga_cli.utils.dry_run import handle_dry_run

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            handle_dry_run(
                "update", "PATCH", "properties/123",
                {"displayName": "x"}, update_mask="displayName",
            )
        except typer.Exit:
            pass
        finally:
            sys.stdout = old_stdout

        data = json.loads(captured.getvalue())
        assert data["update_mask"] == "displayName"


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------


class TestAccountsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["accounts", "update", "-a", "123456", "--name", "New Name", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["method"] == "PATCH"
        assert data["resource"] == "accounts/123456"
        assert data["body"] == {"displayName": "New Name"}
        assert data["update_mask"] == "displayName"

    def test_api_not_called(self):
        mock_client = MagicMock()
        with patch("ga_cli.commands.accounts.get_admin_client", return_value=mock_client):
            runner.invoke(
                app,
                ["accounts", "update", "-a", "123456", "--name", "X", "--dry-run"],
            )
        mock_client.accounts.return_value.patch.return_value.execute.assert_not_called()


class TestAccountsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["accounts", "delete", "-a", "123456", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["method"] == "DELETE"
        assert data["resource"] == "accounts/123456"
        assert data["idempotent"] is True
        assert "body" not in data

    def test_skips_confirmation(self):
        """--dry-run should not prompt for confirmation."""
        result = runner.invoke(
            app,
            ["accounts", "delete", "-a", "123456", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "dry_run" in result.output


# ---------------------------------------------------------------------------
# properties
# ---------------------------------------------------------------------------


class TestPropertiesCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "properties", "create",
                "-a", "123456", "--name", "My Prop",
                "--timezone", "UTC", "--currency", "EUR",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["method"] == "POST"
        assert data["resource"] == "accounts/123456"
        assert data["body"]["displayName"] == "My Prop"
        assert data["body"]["timeZone"] == "UTC"
        assert data["body"]["currencyCode"] == "EUR"
        assert data["idempotent"] is False


class TestPropertiesUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "properties", "update",
                "-p", "999", "--name", "Updated",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["method"] == "PATCH"
        assert data["resource"] == "properties/999"
        assert data["body"]["displayName"] == "Updated"
        assert "update_mask" in data


class TestPropertiesDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["properties", "delete", "-p", "999", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999"
        assert data["idempotent"] is True


class TestPropertiesAcknowledgeUdcDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["properties", "acknowledge-udc", "-p", "999", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "acknowledge"
        assert data["method"] == "POST"
        assert data["resource"] == "properties/999"
        assert "acknowledgement" in data["body"]


# ---------------------------------------------------------------------------
# data-streams
# ---------------------------------------------------------------------------


class TestDataStreamsCreateDryRun:
    def test_dry_run_web_stream(self):
        result = runner.invoke(
            app,
            [
                "data-streams", "create",
                "-p", "999", "--display-name", "My Stream",
                "--type", "WEB_DATA_STREAM", "--url", "https://example.com",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["method"] == "POST"
        assert data["resource"] == "properties/999"
        assert data["body"]["displayName"] == "My Stream"
        assert data["body"]["webStreamData"]["defaultUri"] == "https://example.com"


class TestDataStreamsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "data-streams", "update",
                "-p", "999", "-s", "555",
                "--display-name", "Updated Stream",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/dataStreams/555"
        assert data["update_mask"] == "displayName"


class TestDataStreamsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["data-streams", "delete", "-p", "999", "-s", "555", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999/dataStreams/555"
        assert data["idempotent"] is True


# ---------------------------------------------------------------------------
# custom-dimensions
# ---------------------------------------------------------------------------


class TestCustomDimensionsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-dimensions", "create",
                "-p", "999",
                "--parameter-name", "my_param",
                "--display-name", "My Dim",
                "--scope", "EVENT",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["parameterName"] == "my_param"
        assert data["body"]["scope"] == "EVENT"


class TestCustomDimensionsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-dimensions", "update",
                "-p", "999", "-d", "dim1",
                "--display-name", "New Name",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/customDimensions/dim1"
        assert data["update_mask"] == "displayName"


class TestCustomDimensionsArchiveDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-dimensions", "archive",
                "-p", "999", "-d", "dim1",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "archive"
        assert data["method"] == "POST"
        assert data["resource"] == "properties/999/customDimensions/dim1"
        assert "body" not in data


# ---------------------------------------------------------------------------
# custom-metrics
# ---------------------------------------------------------------------------


class TestCustomMetricsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-metrics", "create",
                "-p", "999",
                "--parameter-name", "my_metric",
                "--display-name", "My Metric",
                "--scope", "EVENT",
                "--measurement-unit", "STANDARD",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["measurementUnit"] == "STANDARD"


class TestCustomMetricsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-metrics", "update",
                "-p", "999", "-m", "met1",
                "--display-name", "Updated",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/customMetrics/met1"


class TestCustomMetricsArchiveDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "custom-metrics", "archive",
                "-p", "999", "-m", "met1",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "archive"
        assert data["resource"] == "properties/999/customMetrics/met1"


# ---------------------------------------------------------------------------
# key-events
# ---------------------------------------------------------------------------


class TestKeyEventsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "key-events", "create",
                "-p", "999",
                "--event-name", "purchase",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["eventName"] == "purchase"
        assert data["body"]["countingMethod"] == "ONCE_PER_EVENT"


class TestKeyEventsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "key-events", "update",
                "-p", "999", "-k", "ke1",
                "--counting-method", "ONCE_PER_SESSION",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/keyEvents/ke1"
        assert data["body"]["countingMethod"] == "ONCE_PER_SESSION"


class TestKeyEventsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["key-events", "delete", "-p", "999", "-k", "ke1", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999/keyEvents/ke1"
        assert data["idempotent"] is True


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------


class TestAnnotationsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "annotations", "create",
                "-p", "999",
                "--title", "Deploy v2",
                "--annotation-date", "2025-01-15",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["title"] == "Deploy v2"
        assert data["body"]["annotationDate"] == "2025-01-15"


class TestAnnotationsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "annotations", "update",
                "-p", "999", "-a", "ann1",
                "--title", "Updated",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == (
            "properties/999/reportingDataAnnotations/ann1"
        )


class TestAnnotationsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            ["annotations", "delete", "-p", "999", "-a", "ann1", "--dry-run"],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == (
            "properties/999/reportingDataAnnotations/ann1"
        )


# ---------------------------------------------------------------------------
# calculated-metrics
# ---------------------------------------------------------------------------


class TestCalculatedMetricsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "calculated-metrics", "create",
                "-p", "999",
                "--calculated-metric-id", "rpm",
                "--display-name", "Revenue Per User",
                "--formula", "{{totalRevenue}} / {{totalUsers}}",
                "--metric-unit", "CURRENCY",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["formula"] == "{{totalRevenue}} / {{totalUsers}}"
        assert data["body"]["metricUnit"] == "CURRENCY"


class TestCalculatedMetricsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "calculated-metrics", "update",
                "-p", "999", "-m", "rpm",
                "--display-name", "Updated",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/calculatedMetrics/rpm"


class TestCalculatedMetricsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "calculated-metrics", "delete",
                "-p", "999", "-m", "rpm",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999/calculatedMetrics/rpm"


# ---------------------------------------------------------------------------
# firebase-links
# ---------------------------------------------------------------------------


class TestFirebaseLinksCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "firebase-links", "create",
                "-p", "999",
                "--project", "projects/my-project",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["project"] == "projects/my-project"


class TestFirebaseLinksDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "firebase-links", "delete",
                "-p", "999", "--link-id", "fb1",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999/firebaseLinks/fb1"


# ---------------------------------------------------------------------------
# google-ads-links
# ---------------------------------------------------------------------------


class TestGoogleAdsLinksCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "google-ads-links", "create",
                "-p", "999",
                "--customer-id", "CID123",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["body"]["customerId"] == "CID123"
        assert data["body"]["adsPersonalizationEnabled"] is True


class TestGoogleAdsLinksUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "google-ads-links", "update",
                "-p", "999", "--link-id", "gads1",
                "--no-ads-personalization",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == "properties/999/googleAdsLinks/gads1"
        assert data["body"]["adsPersonalizationEnabled"] is False


class TestGoogleAdsLinksDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "google-ads-links", "delete",
                "-p", "999", "--link-id", "gads1",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == "properties/999/googleAdsLinks/gads1"


# ---------------------------------------------------------------------------
# mp-secrets
# ---------------------------------------------------------------------------


class TestMpSecretsCreateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "mp-secrets", "create",
                "-p", "999", "-s", "555",
                "--display-name", "My Secret",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "create"
        assert data["resource"] == "properties/999/dataStreams/555"
        assert data["body"]["displayName"] == "My Secret"


class TestMpSecretsUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "mp-secrets", "update",
                "-p", "999", "-s", "555",
                "--secret-id", "sec1",
                "--display-name", "Updated",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["resource"] == (
            "properties/999/dataStreams/555"
            "/measurementProtocolSecrets/sec1"
        )
        assert data["update_mask"] == "displayName"


class TestMpSecretsDeleteDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "mp-secrets", "delete",
                "-p", "999", "-s", "555",
                "--secret-id", "sec1",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "delete"
        assert data["resource"] == (
            "properties/999/dataStreams/555"
            "/measurementProtocolSecrets/sec1"
        )
        assert data["idempotent"] is True


# ---------------------------------------------------------------------------
# data-retention
# ---------------------------------------------------------------------------


class TestDataRetentionUpdateDryRun:
    def test_dry_run_outputs_json(self):
        result = runner.invoke(
            app,
            [
                "data-retention", "update",
                "-p", "999",
                "--event-data-retention", "FOURTEEN_MONTHS",
                "--dry-run",
            ],
        )
        data = _parse_dry_run(result)
        assert data["action"] == "update"
        assert data["method"] == "PATCH"
        assert data["resource"] == (
            "properties/999/dataRetentionSettings"
        )
        assert data["body"]["eventDataRetention"] == "FOURTEEN_MONTHS"
        assert "update_mask" in data
