"""Tests for account-summaries commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()

SAMPLE_SUMMARIES = [
    {
        "name": "accountSummaries/aaa",
        "account": "accounts/111",
        "displayName": "Acme Corp",
        "propertySummaries": [
            {
                "property": "properties/1001",
                "displayName": "Acme Website",
                "propertyType": "PROPERTY_TYPE_ORDINARY",
            },
            {
                "property": "properties/1002",
                "displayName": "Acme App",
                "propertyType": "PROPERTY_TYPE_ORDINARY",
            },
        ],
    },
    {
        "name": "accountSummaries/bbb",
        "account": "accounts/222",
        "displayName": "Beta Inc",
        "propertySummaries": [
            {
                "property": "properties/2001",
                "displayName": "Beta Site",
                "propertyType": "PROPERTY_TYPE_ORDINARY",
            },
        ],
    },
]


def _mock_admin_client(summaries=None):
    mock_client = MagicMock()
    mock_client.accountSummaries.return_value.list.return_value.execute.return_value = {
        "accountSummaries": summaries if summaries is not None else [],
    }
    return mock_client


class TestAccountSummariesList:
    def test_list_table(self):
        mock_client = _mock_admin_client(summaries=SAMPLE_SUMMARIES)

        with patch(
            "ga_cli.commands.account_summaries.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["account-summaries", "list"])

        assert result.exit_code == 0
        assert "Acme Corp" in result.output
        assert "Acme Website" in result.output
        assert "Acme App" in result.output
        assert "Beta Inc" in result.output
        assert "Beta Site" in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client(summaries=[])

        with patch(
            "ga_cli.commands.account_summaries.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["account-summaries", "list"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client(summaries=SAMPLE_SUMMARIES)

        with patch(
            "ga_cli.commands.account_summaries.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["account-summaries", "list", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"displayName"' in result.output
        assert "Acme Corp" in result.output

    def test_list_pagination(self):
        mock_client = MagicMock()
        # First call returns page with nextPageToken, second call returns final page
        mock_client.accountSummaries.return_value.list.return_value.execute.side_effect = [
            {
                "accountSummaries": [SAMPLE_SUMMARIES[0]],
                "nextPageToken": "token123",
            },
            {
                "accountSummaries": [SAMPLE_SUMMARIES[1]],
            },
        ]

        with patch(
            "ga_cli.commands.account_summaries.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["account-summaries", "list"])

        assert result.exit_code == 0
        assert "Acme Corp" in result.output
        assert "Beta Inc" in result.output

    def test_list_api_error(self):
        mock_client = MagicMock()
        mock_client.accountSummaries.return_value.list.return_value.execute.side_effect = (
            Exception("Permission denied")
        )

        with patch(
            "ga_cli.commands.account_summaries.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["account-summaries", "list"])

        assert result.exit_code != 0
