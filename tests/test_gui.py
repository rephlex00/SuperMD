"""Tests for the configuration GUI server."""

import json
import threading
import urllib.request
import urllib.error

import pytest
from ruamel.yaml import YAML

from supermd.gui import ConfigHandler, HTML_PAGE, _update_yaml_doc, _to_plain
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString
from http.server import HTTPServer

_yaml = YAML()


def _yaml_load(text):
    """Load YAML from string."""
    from io import StringIO
    return _yaml.load(StringIO(text)) or {}


def _yaml_dump(data):
    """Dump data to YAML string."""
    from io import StringIO
    s = StringIO()
    _yaml.dump(data, s)
    return s.getvalue()


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config YAML with comments."""
    path = tmp_path / "supermd.yaml"
    path.write_text(
        "# Main config\n"
        "model: gpt-4o-mini  # the LLM model\n"
        "\n"
        "# Transcription prompt\n"
        "prompt: |\n"
        "  Test prompt\n"
        "  with newlines\n"
        "\n"
        "output_path_template: '{{file_basename}}'\n"
        "output_filename_template: '{{file_basename}}.md'\n"
        "\n"
        "# Processing settings\n"
        "defaults:\n"
        "  force: false\n"
        "  progress: true\n"
        "  level: INFO\n"
        "  cooldown: 5.0\n"
        "\n"
        "# Job definitions\n"
        "jobs:\n"
        "  - name: TestJob\n"
        "    input: ~/in\n"
        "    output: ~/out\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def server(config_file):
    """Start a GUI server on a random port and yield the base URL."""
    ConfigHandler.config_path = str(config_file)
    httpd = HTTPServer(("127.0.0.1", 0), ConfigHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read())


def _post(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestHTMLPage:
    def test_serves_html(self, server):
        with urllib.request.urlopen(server + "/") as resp:
            assert resp.status == 200
            body = resp.read().decode()
            assert "SuperMD Configuration" in body


class TestGetConfig:
    def test_returns_config(self, server):
        status, data = _get(server + "/api/config")
        assert status == 200
        assert data["model"] == "gpt-4o-mini"
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["name"] == "TestJob"

    def test_returns_defaults_when_no_file(self, tmp_path, server):
        ConfigHandler.config_path = str(tmp_path / "missing.yaml")
        status, data = _get(server + "/api/config")
        assert status == 200
        assert data["model"] == "gpt-4o-mini"


class TestGetConfigPath:
    def test_returns_path(self, server, config_file):
        status, data = _get(server + "/api/config/path")
        assert status == 200
        assert data["path"] == str(config_file)


class TestPostConfig:
    def test_save_valid_config(self, server, config_file):
        payload = {
            "model": "gpt-4o",
            "prompt": "New prompt\n",
            "output_path_template": "{{file_basename}}",
            "output_filename_template": "{{file_basename}}.md",
            "defaults": {"force": True, "progress": False, "level": "DEBUG", "cooldown": 2.0},
            "jobs": [
                {"name": "Updated", "input": "/a", "output": "/b"},
            ],
        }
        status, data = _post(server + "/api/config", payload)
        assert status == 200
        assert data["ok"] is True

        written = _yaml_load(config_file.read_text())
        assert written["model"] == "gpt-4o"
        assert written["defaults"]["force"] is True
        assert written["jobs"][0]["name"] == "Updated"

    def test_save_preserves_comments(self, server, config_file):
        """Comments in the YAML should survive a save."""
        _, original = _get(server + "/api/config")
        # Change just the model
        original["model"] = "gpt-4o"
        status, _ = _post(server + "/api/config", original)
        assert status == 200

        raw_text = config_file.read_text()
        assert "# Main config" in raw_text
        assert "# the LLM model" in raw_text
        assert "# Processing settings" in raw_text
        assert "# Job definitions" in raw_text
        assert "gpt-4o" in raw_text

    def test_save_invalid_config(self, server):
        payload = {"defaults": {"cooldown": "not-a-number"}}
        status, data = _post(server + "/api/config", payload)
        assert status == 400
        assert "error" in data

    def test_save_invalid_json(self, server):
        req = urllib.request.Request(
            server + "/api/config",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_round_trip(self, server, config_file):
        """Load config, post it back unchanged, verify file is equivalent."""
        _, original = _get(server + "/api/config")
        status, data = _post(server + "/api/config", original)
        assert status == 200

        reloaded = _yaml_load(config_file.read_text())
        assert reloaded["model"] == original["model"]
        assert len(reloaded["jobs"]) == len(original["jobs"])

    def test_null_note_title_prompt_omitted(self, server, config_file):
        payload = {
            "model": "gpt-4o-mini",
            "note_title_prompt": None,
            "defaults": {"force": False, "progress": True, "level": "INFO", "cooldown": 5.0},
            "jobs": [],
        }
        status, _ = _post(server + "/api/config", payload)
        assert status == 200
        written = _yaml_load(config_file.read_text())
        assert "note_title_prompt" not in written

    def test_add_and_remove_jobs(self, server, config_file):
        payload = {
            "model": "gpt-4o-mini",
            "defaults": {"force": False, "progress": True, "level": "INFO", "cooldown": 5.0},
            "jobs": [
                {"name": "Job1", "input": "/a", "output": "/b"},
                {"name": "Job2", "input": "/c", "output": "/d"},
            ],
        }
        status, _ = _post(server + "/api/config", payload)
        assert status == 200
        written = _yaml_load(config_file.read_text())
        assert len(written["jobs"]) == 2

        # Remove all jobs
        payload["jobs"] = []
        status, _ = _post(server + "/api/config", payload)
        assert status == 200
        written = _yaml_load(config_file.read_text())
        assert written["jobs"] == []


class TestUpdateYamlDoc:
    def test_preserves_comments(self):
        doc = _yaml_load("# top comment\nmodel: old  # inline\n")
        _update_yaml_doc(doc, {"model": "new"})
        output = _yaml_dump(doc)
        assert "# top comment" in output
        assert "new" in output

    def test_multiline_uses_literal_style(self):
        doc = CommentedMap()
        _update_yaml_doc(doc, {"prompt": "line1\nline2\n"})
        assert isinstance(doc["prompt"], LiteralScalarString)


class TestToPlain:
    def test_converts_commented_map(self):
        cm = CommentedMap({"a": 1, "b": CommentedMap({"c": 2})})
        result = _to_plain(cm)
        assert result == {"a": 1, "b": {"c": 2}}
        assert type(result) is dict
        assert type(result["b"]) is dict
