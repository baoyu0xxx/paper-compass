"""Key=value argument parsing utilities, adapted from lm-eval-harness.

Ports the core patterns from lm_eval._cli.utils:
- key_val_to_dict(): parse "key=val,key2=val2" into a dict
- handle_cli_value_string(): auto-detect type (bool/int/float/str)
- MergeDictAction: argparse Action for accumulating key=value pairs

This is the main design reference for paper-compass's model selection
configuration system, following the lm-eval-harness approach.
"""

from __future__ import annotations

import argparse
import ast
import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


def handle_cli_value_string(arg: str) -> bool | int | float | str:
    """Try to parse a CLI value string into the appropriate Python type.

    Adapted from lm_eval._cli.utils.handle_cli_value_string.
    Auto-detects: bool ("true"/"false"), int, float, otherwise returns string.
    """
    if arg.lower() == "true":
        return True
    elif arg.lower() == "false":
        return False
    elif arg.isnumeric():
        return int(arg)
    try:
        return float(arg)
    except ValueError:
        try:
            return ast.literal_eval(arg)
        except (ValueError, SyntaxError):
            return arg


def key_val_to_dict(args: str) -> dict[str, Any]:
    """Parse comma-separated key=value pairs into a dictionary.

    Adapted from lm_eval._cli.utils.key_val_to_dict.
    Handles: "key1=val1,key2=val2" -> {"key1": "val1", "key2": "val2"}
    Values are auto-typed via handle_cli_value_string.
    """
    res: dict[str, Any] = {}
    if not args:
        return res

    for item in args.split(","):
        if "=" not in item:
            logger.warning("Skipping malformed arg (no '='): %r", item)
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = handle_cli_value_string(v.strip())
        if k in res:
            logger.warning("Overwriting key '%s': %r -> %r", k, res[k], v)
        res[k] = v
    return res


class MergeDictAction(argparse.Action):
    """Argparse action that parses key=value args and merges them into a dict.

    Adapted from lm_eval._cli.utils.MergeDictAction.
    Allows both comma-separated ("k=v,k2=v2") and repeated ("k=v" "k2=v2") forms.
    """

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        current: dict[str, Any] = vars(namespace).setdefault(self.dest, {}) or {}

        if not values:
            return

        if isinstance(values, str):
            values = [values]

        for v in values:
            parsed = key_val_to_dict(v)
            if overlap := current.keys() & parsed.keys():
                logger.warning(
                    "Overwriting key(s) from '%s': %s",
                    option_string or self.dest,
                    ", ".join(overlap),
                )
            current.update(parsed)

        setattr(namespace, self.dest, current)


def parse_key_val_pairs(args: list[str] | None) -> dict[str, Any]:
    """Parse a list of key=value strings into a single dict.

    Utility for non-argparse contexts (e.g. programmatic calls).
    """
    result: dict[str, Any] = {}
    if not args:
        return result
    for item in args:
        parsed = key_val_to_dict(item)
        result.update(parsed)
    return result
