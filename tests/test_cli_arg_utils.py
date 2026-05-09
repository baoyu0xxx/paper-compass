"""Tests for paper-compass CLI argument parsing utilities.

Tests the lm-eval-harness-adapted key=value parsing logic.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest

from paper_compass.cli.arg_utils import (
    MergeDictAction,
    handle_cli_value_string,
    key_val_to_dict,
    parse_key_val_pairs,
)


class TestHandleCliValueString:
    def test_bool_true(self):
        assert handle_cli_value_string("true") is True
        assert handle_cli_value_string("True") is True

    def test_bool_false(self):
        assert handle_cli_value_string("false") is False
        assert handle_cli_value_string("False") is False

    def test_int(self):
        assert handle_cli_value_string("42") == 42
        assert handle_cli_value_string("0") == 0
        assert handle_cli_value_string("-5") == -5

    def test_float(self):
        assert handle_cli_value_string("3.14") == 3.14
        assert handle_cli_value_string("-0.5") == -0.5

    def test_string(self):
        assert handle_cli_value_string("hello") == "hello"
        assert handle_cli_value_string("https://api.example.com") == "https://api.example.com"
        assert handle_cli_value_string("gpt-4o") == "gpt-4o"


class TestKeyValToDict:
    def test_empty(self):
        assert key_val_to_dict("") == {}

    def test_single_pair(self):
        result = key_val_to_dict("base_url=https://api.openai.com/v1")
        assert result == {"base_url": "https://api.openai.com/v1"}

    def test_multiple_pairs(self):
        result = key_val_to_dict(
            "base_url=https://api.openai.com/v1,model=gpt-4o,api_key=$OPENAI_API_KEY"
        )
        assert result == {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "api_key": "$OPENAI_API_KEY",
        }

    def test_auto_type_conversion(self):
        result = key_val_to_dict("batch_size=32,use_cache=true,temperature=0.1")
        assert result == {"batch_size": 32, "use_cache": True, "temperature": 0.1}

    def test_malformed_skipped(self):
        result = key_val_to_dict("base_url=https://example.com,badarg,model=gpt4")
        # 'badarg' has no '=' so it's skipped
        assert result == {
            "base_url": "https://example.com",
            "model": "gpt4",
        }


class TestMergeDictAction:
    def test_single_call(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--model-args", nargs="+", action=MergeDictAction)
        args = parser.parse_args(["--model-args", "base_url=http://example.com,model=gpt4"])
        assert args.model_args == {"base_url": "http://example.com", "model": "gpt4"}

    def test_multiple_calls(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--model-args", nargs="+", action=MergeDictAction)
        args = parser.parse_args([
            "--model-args", "base_url=http://example.com",
            "--model-args", "model=gpt4,api_key=sk-123",
        ])
        assert args.model_args == {
            "base_url": "http://example.com",
            "model": "gpt4",
            "api_key": "sk-123",
        }

    def test_space_separated_pairs(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--model-args", nargs="+", action=MergeDictAction)
        args = parser.parse_args([
            "--model-args", "base_url=http://example.com", "model=gpt4",
        ])
        assert args.model_args == {
            "base_url": "http://example.com",
            "model": "gpt4",
        }

    def test_omitted(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--model-args", nargs="+", action=MergeDictAction)
        args = parser.parse_args([])
        # nargs='+' returns None when the flag is not passed
        assert args.model_args is None or args.model_args == {}


class TestParseKeyValPairs:
    def test_empty(self):
        assert parse_key_val_pairs(None) == {}
        assert parse_key_val_pairs([]) == {}

    def test_single(self):
        result = parse_key_val_pairs(["base_url=http://example.com"])
        assert result == {"base_url": "http://example.com"}

    def test_multiple(self):
        result = parse_key_val_pairs([
            "base_url=http://example.com,model=gpt4",
            "api_key=sk-123",
        ])
        assert result == {
            "base_url": "http://example.com",
            "model": "gpt4",
            "api_key": "sk-123",
        }
