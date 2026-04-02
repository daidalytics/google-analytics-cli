"""Tests for --describe schema introspection."""

import json

from typer.testing import CliRunner

from ga_cli.main import app

runner = CliRunner()


def _get_describe_output():
    """Run ga --describe and return parsed JSON."""
    result = runner.invoke(app, ["--describe"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
    return json.loads(result.output)


class TestDescribeTopLevel:
    """Tests for ga --describe."""

    def test_returns_valid_json(self):
        result = runner.invoke(app, ["--describe"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_has_cli_key(self):
        data = _get_describe_output()
        assert data["cli"] == "ga-cli"

    def test_has_commands_dict(self):
        data = _get_describe_output()
        assert isinstance(data["commands"], dict)
        assert len(data["commands"]) > 0

    def test_all_command_groups_present(self):
        """All major command groups should have at least one command."""
        data = _get_describe_output()
        commands = data["commands"]

        expected_groups = [
            "ga accounts",
            "ga properties",
            "ga data-streams",
            "ga reports",
            "ga custom-dimensions",
            "ga custom-metrics",
            "ga key-events",
            "ga annotations",
            "ga config",
            "ga auth",
        ]
        for group in expected_groups:
            matching = [k for k in commands if k.startswith(group)]
            assert len(matching) > 0, f"No commands found for group '{group}'"


class TestDescribeCommandStructure:
    """Tests for individual command schema structure."""

    def test_command_has_required_keys(self):
        data = _get_describe_output()
        # Pick any command
        cmd = next(iter(data["commands"].values()))
        assert "command" in cmd
        assert "description" in cmd
        assert "parameters" in cmd
        assert "mutative" in cmd
        assert "supports_dry_run" in cmd
        assert "supports_json_input" in cmd

    def test_parameters_is_json_schema_object(self):
        data = _get_describe_output()
        cmd = next(iter(data["commands"].values()))
        params = cmd["parameters"]
        assert params["type"] == "object"
        assert "properties" in params

    def test_parameter_has_type_and_flag(self):
        data = _get_describe_output()
        # Find a command with parameters
        for cmd in data["commands"].values():
            props = cmd["parameters"]["properties"]
            if props:
                param = next(iter(props.values()))
                assert "type" in param
                assert "flag" in param
                break


class TestDescribeMutativeFlags:
    """Tests that mutative/dry-run flags are correctly derived."""

    def test_create_command_is_mutative(self):
        data = _get_describe_output()
        cmd = data["commands"].get("ga properties create")
        assert cmd is not None, "ga properties create not found"
        assert cmd["mutative"] is True
        assert cmd["supports_dry_run"] is True

    def test_delete_command_is_mutative(self):
        data = _get_describe_output()
        cmd = data["commands"].get("ga properties delete")
        assert cmd is not None, "ga properties delete not found"
        assert cmd["mutative"] is True
        assert cmd["supports_dry_run"] is True

    def test_list_command_is_not_mutative(self):
        data = _get_describe_output()
        cmd = data["commands"].get("ga properties list")
        assert cmd is not None, "ga properties list not found"
        assert cmd["mutative"] is False
        assert cmd["supports_dry_run"] is False

    def test_get_command_is_not_mutative(self):
        data = _get_describe_output()
        cmd = data["commands"].get("ga accounts get")
        assert cmd is not None, "ga accounts get not found"
        assert cmd["mutative"] is False
        assert cmd["supports_dry_run"] is False

    def test_json_input_is_false_for_all(self):
        data = _get_describe_output()
        for name, cmd in data["commands"].items():
            assert cmd["supports_json_input"] is False, (
                f"{name} has supports_json_input=True but --json-input is not implemented"
            )


class TestDescribeParameterDetails:
    """Tests for parameter extraction accuracy."""

    def test_properties_create_has_expected_params(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert "display_name" in props
        assert "account_id" in props
        assert "timezone" in props
        assert "currency" in props

    def test_required_params_detected(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        required = cmd["parameters"].get("required", [])
        assert "display_name" in required

    def test_optional_params_have_defaults(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert props["timezone"]["default"] == "America/Los_Angeles"
        assert props["currency"]["default"] == "USD"

    def test_aliases_extracted(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert props["account_id"].get("aliases") == ["-a"]

    def test_help_text_as_description(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert len(props["display_name"]["description"]) > 0

    def test_dry_run_excluded_from_params(self):
        """--dry-run is metadata, not a user-facing parameter in the schema."""
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert "dry_run" not in props

    def test_help_excluded_from_params(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties create"]
        props = cmd["parameters"]["properties"]
        assert "help" not in props

    def test_output_format_included(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties list"]
        props = cmd["parameters"]["properties"]
        assert "output_format" in props
        assert props["output_format"]["flag"] == "--output"

    def test_integer_type_detected(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga reports run"]
        props = cmd["parameters"]["properties"]
        assert props["limit"]["type"] == "integer"

    def test_boolean_type_for_flag_options(self):
        data = _get_describe_output()
        cmd = data["commands"]["ga properties delete"]
        props = cmd["parameters"]["properties"]
        assert props["yes"]["type"] == "boolean"


class TestDescribeNoAuth:
    """--describe should work without any authentication."""

    def test_describe_without_credentials(self):
        """--describe exits before any API/auth calls."""
        result = runner.invoke(app, ["--describe"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cli"] == "ga-cli"
