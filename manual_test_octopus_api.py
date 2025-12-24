"""Manual Octopus GraphQL smoke-test harness.

Usage:
    OCTOPUS_API_KEY=sk_live_xxx OCTOPUS_ACCOUNT=ABC123 python manual_test_octopus_api.py

The script prints out the device list, charging preferences, and a summary of planned
and completed dispatch windows for each device so you can verify the integration logic
matches the live API responses.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import pathlib
import sys
from typing import Any


def _env(name: str, prompt: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    print(f"Enter {prompt}: ", end="", flush=True)
    value = sys.stdin.readline().strip()
    if not value:
        raise SystemExit(f"{prompt} is required")
    return value


def _fmt_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _load_graphql_client_class():
    root = pathlib.Path(__file__).parent
    client_path = root / "custom_components" / "octopus_intelligent" / "graphql_client.py"
    spec = importlib.util.spec_from_file_location("octo_graphql_client", client_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load graphql_client module from {client_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module.OctopusEnergyGraphQLClient


async def main() -> None:
    api_key = _env("OCTOPUS_API_KEY", "Octopus API key")
    account_id = _env("OCTOPUS_ACCOUNT", "Octopus account number")

    OctopusEnergyGraphQLClient = _load_graphql_client_class()
    client = OctopusEnergyGraphQLClient(api_key)

    print("\nFetching devices...")
    devices = await client.async_get_devices(account_id)
    if not devices:
        print("No devices returned for account", account_id)
        return

    print(f"Found {len(devices)} device(s)\n")

    for idx, device in enumerate(devices, start=1):
        device_id = device.get("id", "<unknown>")
        label = device.get("label") or device_id
        print(f"=== Device {idx}: {label} ({device_id}) ===")
        print(_fmt_json(device))

        print("\n-- Charging Preferences --")
        prefs = await client.async_get_device_preferences(account_id, device_id)
        if prefs:
            print(_fmt_json(prefs))
        else:
            print("<none>")

        print("\n-- Dispatch Summary --")
        dispatch_data = await client.async_get_device_dispatches(account_id, device_id)
        if not dispatch_data:
            print("<none>")
            print()
            continue

        planned = dispatch_data.get("flexPlannedDispatches", [])
        completed = dispatch_data.get("completedDispatches", [])
        print(f"Planned dispatches: {len(planned)}")
        if planned:
            print(_fmt_json(planned))
        print(f"Completed dispatches: {len(completed)}")
        if completed:
            print(_fmt_json(completed))
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Aborted by user")