"""The typer and argparse frontends must agree on every shared option default.

The CLI has two frontends: a typer app (used when typer is installed, which it
always is because typer is a required dependency) and an argparse fallback. They
declare their defaults independently, so a fix applied to one silently leaves the
other wrong. That happened with review-literature: the argparse defaults were
moved off the offline-pilot trees while the typer defaults still pointed at
data/extracted and reports/, so the live path kept overwriting committed
synthetic artifacts.
"""

from __future__ import annotations

import argparse
import inspect
import unittest

from metabotyping_agentic import cli


def _argparse_defaults() -> dict[str, dict[str, object]]:
    parser = cli.build_parser()
    out: dict[str, dict[str, object]] = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, subparser in action.choices.items():
            out[name] = {
                sub.dest: sub.default
                for sub in subparser._actions
                if sub.dest != "help"
            }
    return out


def _typer_defaults() -> dict[str, dict[str, object]]:
    if not cli.HAS_TYPER or cli.app is None:
        return {}
    out: dict[str, dict[str, object]] = {}
    for command in cli.app.registered_commands:
        name = command.name or command.callback.__name__
        defaults: dict[str, object] = {}
        for param in inspect.signature(command.callback).parameters.values():
            default = param.default
            value = getattr(default, "default", default)
            if value is inspect.Parameter.empty:
                continue
            defaults[param.name] = value
        out[name] = defaults
    return out


class CliFrontendParityTests(unittest.TestCase):
    def test_shared_option_defaults_match(self):
        typer_defaults = _typer_defaults()
        if not typer_defaults:
            self.skipTest("typer is not installed; only the argparse frontend exists")
        argparse_defaults = _argparse_defaults()

        mismatches: list[str] = []
        for command, typer_options in sorted(typer_defaults.items()):
            argparse_options = argparse_defaults.get(command)
            if argparse_options is None:
                continue
            for option, typer_value in sorted(typer_options.items()):
                if option not in argparse_options:
                    continue
                argparse_value = argparse_options[option]
                # Ellipsis marks a typer required option; argparse spells that
                # as required=True with a None default.
                if typer_value is ...:
                    continue
                if argparse_value != typer_value:
                    mismatches.append(
                        f"{command}.{option}: typer={typer_value!r} argparse={argparse_value!r}"
                    )

        self.assertEqual(mismatches, [], "frontend default drift:\n" + "\n".join(mismatches))

    def test_no_live_command_defaults_into_the_offline_pilot_trees(self):
        """Live lanes must never default to writing over offline-pilot output."""

        protected = ("reports", "data/extracted", "data/review", "data/examples")
        offenders: list[str] = []
        for source in (_typer_defaults(), _argparse_defaults()):
            for command, options in source.items():
                if not command.startswith(("live-", "review-literature")):
                    continue
                for option, value in options.items():
                    if option not in {"out", "reports_out"}:
                        continue
                    if isinstance(value, str) and value in protected:
                        offenders.append(f"{command}.{option}={value}")
        self.assertEqual(sorted(set(offenders)), [])


if __name__ == "__main__":
    unittest.main()
