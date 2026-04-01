"""Property settings commands (attribution, Google Signals, enhanced measurement)."""

from typing import Optional

import typer

from ..api.client import get_admin_alpha_client
from ..config.store import get_effective_value
from ..utils import handle_error, output, require_options, resolve_output_format, success

property_settings_app = typer.Typer(
    name="property-settings",
    help="Manage property-level settings",
    no_args_is_help=True,
)

# --- Attribution Settings ---

_ACQUISITION_LOOKBACK_CHOICES = [
    "ACQUISITION_CONVERSION_EVENT_LOOKBACK_WINDOW_7_DAYS",
    "ACQUISITION_CONVERSION_EVENT_LOOKBACK_WINDOW_30_DAYS",
]

_OTHER_LOOKBACK_CHOICES = [
    "OTHER_CONVERSION_EVENT_LOOKBACK_WINDOW_30_DAYS",
    "OTHER_CONVERSION_EVENT_LOOKBACK_WINDOW_60_DAYS",
    "OTHER_CONVERSION_EVENT_LOOKBACK_WINDOW_90_DAYS",
]

_ATTRIBUTION_MODEL_CHOICES = [
    "PAID_AND_ORGANIC_CHANNELS_DATA_DRIVEN",
    "PAID_AND_ORGANIC_CHANNELS_LAST_CLICK",
    "GOOGLE_PAID_CHANNELS_LAST_CLICK",
]

_ADS_EXPORT_SCOPE_CHOICES = [
    "NOT_SELECTED_YET",
    "PAID_AND_ORGANIC_CHANNELS",
    "GOOGLE_PAID_CHANNELS",
]


def _validate_enum(value: Optional[str], choices: list[str], flag_name: str) -> None:
    """Validate an enum value against allowed choices."""
    if value is not None and value not in choices:
        raise typer.BadParameter(
            f"Invalid value '{value}' for {flag_name}. "
            f"Must be one of: {', '.join(choices)}"
        )


@property_settings_app.command("attribution")
def attribution_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    acquisition_lookback: Optional[str] = typer.Option(
        None,
        "--acquisition-lookback",
        help=f"Acquisition conversion lookback window ({', '.join(_ACQUISITION_LOOKBACK_CHOICES)})",
    ),
    other_lookback: Optional[str] = typer.Option(
        None,
        "--other-lookback",
        help=f"Other conversion lookback window ({', '.join(_OTHER_LOOKBACK_CHOICES)})",
    ),
    attribution_model: Optional[str] = typer.Option(
        None,
        "--attribution-model",
        help=f"Reporting attribution model ({', '.join(_ATTRIBUTION_MODEL_CHOICES)})",
    ),
    ads_export_scope: Optional[str] = typer.Option(
        None,
        "--ads-export-scope",
        help=f"Ads web conversion data export scope ({', '.join(_ADS_EXPORT_SCOPE_CHOICES)})",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get or update attribution settings. With no update flags, displays current settings."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        resource_name = f"properties/{effective_property}/attributionSettings"
        admin = get_admin_alpha_client()

        field_map = {
            "acquisitionConversionEventLookbackWindow": acquisition_lookback,
            "otherConversionEventLookbackWindow": other_lookback,
            "reportingAttributionModel": attribution_model,
            "adsWebConversionDataExportScope": ads_export_scope,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if body:
            # Validate enums
            _validate_enum(
                acquisition_lookback,
                _ACQUISITION_LOOKBACK_CHOICES,
                "--acquisition-lookback",
            )
            _validate_enum(other_lookback, _OTHER_LOOKBACK_CHOICES, "--other-lookback")
            _validate_enum(attribution_model, _ATTRIBUTION_MODEL_CHOICES, "--attribution-model")
            _validate_enum(ads_export_scope, _ADS_EXPORT_SCOPE_CHOICES, "--ads-export-scope")

            update_mask = ",".join(body.keys())
            settings = (
                admin.properties()
                .updateAttributionSettings(
                    name=resource_name, updateMask=update_mask, body=body
                )
                .execute()
            )
            success("Attribution settings updated.")
        else:
            settings = (
                admin.properties()
                .getAttributionSettings(name=resource_name)
                .execute()
            )

        output(settings, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


# --- Google Signals Settings ---

_SIGNALS_STATE_CHOICES = [
    "GOOGLE_SIGNALS_ENABLED",
    "GOOGLE_SIGNALS_DISABLED",
]


@property_settings_app.command("google-signals")
def google_signals_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    state: Optional[str] = typer.Option(
        None,
        "--state",
        help=f"Google Signals state ({', '.join(_SIGNALS_STATE_CHOICES)})",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get or update Google Signals settings. With no update flags, displays current settings."""
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        resource_name = f"properties/{effective_property}/googleSignalsSettings"
        admin = get_admin_alpha_client()

        if state is not None:
            _validate_enum(state, _SIGNALS_STATE_CHOICES, "--state")
            body = {"state": state}
            settings = (
                admin.properties()
                .updateGoogleSignalsSettings(
                    name=resource_name, updateMask="state", body=body
                )
                .execute()
            )
            success("Google Signals settings updated.")
        else:
            settings = (
                admin.properties()
                .getGoogleSignalsSettings(name=resource_name)
                .execute()
            )

        output(settings, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)


# --- Enhanced Measurement Settings ---


@property_settings_app.command("enhanced-measurement")
def enhanced_measurement_cmd(
    property_id: Optional[str] = typer.Option(
        None, "--property-id", "-p", help="Property ID (numeric)"
    ),
    stream_id: str = typer.Option(
        ..., "--stream-id", "-s", help="Data stream ID"
    ),
    stream_enabled: Optional[bool] = typer.Option(
        None,
        "--stream-enabled/--no-stream-enabled",
        help="Enable/disable enhanced measurement for this stream",
    ),
    scrolls: Optional[bool] = typer.Option(
        None, "--scrolls/--no-scrolls", help="Capture scroll events"
    ),
    outbound_clicks: Optional[bool] = typer.Option(
        None, "--outbound-clicks/--no-outbound-clicks", help="Capture outbound click events"
    ),
    site_search: Optional[bool] = typer.Option(
        None, "--site-search/--no-site-search", help="Capture site search events"
    ),
    video_engagement: Optional[bool] = typer.Option(
        None, "--video-engagement/--no-video-engagement", help="Capture video engagement events"
    ),
    file_downloads: Optional[bool] = typer.Option(
        None, "--file-downloads/--no-file-downloads", help="Capture file download events"
    ),
    page_changes: Optional[bool] = typer.Option(
        None, "--page-changes/--no-page-changes", help="Capture page change (history) events"
    ),
    form_interactions: Optional[bool] = typer.Option(
        None, "--form-interactions/--no-form-interactions", help="Capture form interaction events"
    ),
    search_query_parameter: Optional[str] = typer.Option(
        None, "--search-query-parameter", help="URL query parameters for site search"
    ),
    uri_query_parameter: Optional[str] = typer.Option(
        None, "--uri-query-parameter", help="Additional URL query parameters"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output format (json, table, compact)"
    ),
):
    """Get or update enhanced measurement settings.

    With no update flags, displays current settings.
    """
    try:
        effective_property = get_effective_value(property_id, "default_property_id")
        require_options({"property_id": effective_property}, ["property_id"])
        effective_format = resolve_output_format(output_format)

        resource_name = (
            f"properties/{effective_property}/dataStreams/{stream_id}"
            "/enhancedMeasurementSettings"
        )
        admin = get_admin_alpha_client()

        field_map = {
            "streamEnabled": stream_enabled,
            "scrollsEnabled": scrolls,
            "outboundClicksEnabled": outbound_clicks,
            "siteSearchEnabled": site_search,
            "videoEngagementEnabled": video_engagement,
            "fileDownloadsEnabled": file_downloads,
            "pageChangesEnabled": page_changes,
            "formInteractionsEnabled": form_interactions,
            "searchQueryParameter": search_query_parameter,
            "uriQueryParameter": uri_query_parameter,
        }
        body = {k: v for k, v in field_map.items() if v is not None}

        if body:
            update_mask = ",".join(body.keys())
            settings = (
                admin.properties()
                .dataStreams()
                .updateEnhancedMeasurementSettings(
                    name=resource_name, updateMask=update_mask, body=body
                )
                .execute()
            )
            success("Enhanced measurement settings updated.")
        else:
            settings = (
                admin.properties()
                .dataStreams()
                .getEnhancedMeasurementSettings(name=resource_name)
                .execute()
            )

        output(settings, effective_format)
    except typer.BadParameter:
        raise
    except Exception as e:
        handle_error(e)
