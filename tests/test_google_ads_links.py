"""Tests for Google Ads links commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ga_cli.config.store import UserConfig, save_config
from ga_cli.main import app

runner = CliRunner()

SAMPLE_GOOGLE_ADS_LINKS = [
    {
        "name": "properties/123/googleAdsLinks/456",
        "customerId": "123-456-7890",
        "canManageClients": False,
        "adsPersonalizationEnabled": True,
        "createTime": "2024-03-01T12:00:00Z",
    },
    {
        "name": "properties/123/googleAdsLinks/789",
        "customerId": "987-654-3210",
        "canManageClients": True,
        "adsPersonalizationEnabled": False,
        "createTime": "2024-04-15T09:30:00Z",
    },
]


def _mock_admin_client():
    """Create a mock Admin API client with googleAdsLinks methods."""
    mock_client = MagicMock()
    gal = mock_client.properties.return_value.googleAdsLinks.return_value

    gal.list.return_value.execute.return_value = {
        "googleAdsLinks": SAMPLE_GOOGLE_ADS_LINKS,
    }
    gal.create.return_value.execute.return_value = SAMPLE_GOOGLE_ADS_LINKS[0]
    gal.patch.return_value.execute.return_value = SAMPLE_GOOGLE_ADS_LINKS[0]
    gal.delete.return_value.execute.return_value = {}

    return mock_client


class TestGoogleAdsLinksList:
    def test_list_table(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["google-ads-links", "list", "--property-id", "123"]
            )

        assert result.exit_code == 0
        assert "123-456-7890" in result.output
        assert "987-654-3210" in result.output

    def test_list_json(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["google-ads-links", "list", "-p", "123", "-o", "json"]
            )

        assert result.exit_code == 0
        assert '"customerId"' in result.output

    def test_list_empty(self):
        mock_client = _mock_admin_client()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.list.return_value.execute.return_value = {"googleAdsLinks": []}

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["google-ads-links", "list", "-p", "123"]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_list_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.list.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b'{"error": {"message": "Forbidden"}}'
        )

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app, ["google-ads-links", "list", "-p", "123"]
            )

        assert result.exit_code == 2

    def test_list_missing_property_id(self):
        result = runner.invoke(app, ["google-ads-links", "list"])

        assert result.exit_code != 0
        assert "property-id" in result.output.lower()

    def test_list_uses_config_default(self):
        save_config(UserConfig(default_property_id="123"))
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(app, ["google-ads-links", "list"])

        assert result.exit_code == 0
        assert "123-456-7890" in result.output


class TestGoogleAdsLinksCreate:
    def test_create_link(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "google-ads-links", "create",
                    "-p", "123",
                    "--customer-id", "123-456-7890",
                ],
            )

        assert result.exit_code == 0
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        body = gal.create.call_args[1]["body"]
        assert body["customerId"] == "123-456-7890"
        assert body["adsPersonalizationEnabled"] is True

    def test_create_no_ads_personalization(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "google-ads-links", "create",
                    "-p", "123",
                    "--customer-id", "123-456-7890",
                    "--no-ads-personalization",
                ],
            )

        assert result.exit_code == 0
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        body = gal.create.call_args[1]["body"]
        assert body["adsPersonalizationEnabled"] is False

    def test_create_requires_customer_id(self):
        result = runner.invoke(
            app,
            ["google-ads-links", "create", "-p", "123"],
        )

        assert result.exit_code != 0

    def test_create_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "google-ads-links", "create",
                    "-p", "123",
                    "--customer-id", "123-456-7890",
                ],
            )

        assert result.exit_code == 3


class TestGoogleAdsLinksUpdate:
    def test_update_ads_personalization(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "google-ads-links", "update",
                    "-p", "123",
                    "--link-id", "456",
                    "--no-ads-personalization",
                ],
            )

        assert result.exit_code == 0
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        call_args = gal.patch.call_args
        assert call_args[1]["updateMask"] == "adsPersonalizationEnabled"
        assert call_args[1]["body"]["adsPersonalizationEnabled"] is False

    def test_update_no_fields(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["google-ads-links", "update", "-p", "123", "--link-id", "456"],
            )

        assert result.exit_code != 0

    def test_update_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.patch.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                [
                    "google-ads-links", "update",
                    "-p", "123",
                    "--link-id", "456",
                    "--ads-personalization",
                ],
            )

        assert result.exit_code == 3


class TestGoogleAdsLinksDelete:
    def test_delete_with_yes(self):
        mock_client = _mock_admin_client()

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["google-ads-links", "delete", "-p", "123", "--link-id", "456", "--yes"],
            )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.delete.assert_called_once()

    def test_delete_confirms(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.google_ads_links.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.google_ads_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = True
            result = runner.invoke(
                app,
                ["google-ads-links", "delete", "-p", "123", "--link-id", "456"],
            )

        assert result.exit_code == 0
        mock_q.confirm.assert_called_once()

    def test_delete_cancelled(self):
        mock_client = _mock_admin_client()

        with (
            patch(
                "ga_cli.commands.google_ads_links.get_admin_client",
                return_value=mock_client,
            ),
            patch("ga_cli.commands.google_ads_links.questionary") as mock_q,
        ):
            mock_q.confirm.return_value.ask.return_value = False
            result = runner.invoke(
                app,
                ["google-ads-links", "delete", "-p", "123", "--link-id", "456"],
            )

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_delete_api_error(self):
        from googleapiclient.errors import HttpError

        mock_client = _mock_admin_client()
        gal = mock_client.properties.return_value.googleAdsLinks.return_value
        gal.delete.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=400), content=b'{"error": {"message": "Bad request"}}'
        )

        with patch(
            "ga_cli.commands.google_ads_links.get_admin_client",
            return_value=mock_client,
        ):
            result = runner.invoke(
                app,
                ["google-ads-links", "delete", "-p", "123", "--link-id", "456", "--yes"],
            )

        assert result.exit_code == 3
