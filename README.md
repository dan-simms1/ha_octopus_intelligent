# octopus_intelligent
Octopus Intelligent Home Assistant integration, maintained as a fork of the original project by [megakid](https://github.com/megakid/ha_octopus_intelligent).

## Key features

- **Multi-car awareness:** Every supported vehicle exposes its own switches, selects, sensors, and slot windows while the integration still publishes combined account-level entities for quick at-a-glance checks.
- **Slot transparency:** Smart-Charge Slot, Offpeak Window, and Planned Dispatch sensors reflect the exact state of Octopus’ dispatch planner, including per-car attributes for automations and dashboards.
- **Configurable tariff windows:** Adjust the cheap-rate start/end times or polling interval straight from Home Assistant’s Configure dialog without re-running onboarding.
- **Rich debugging data:** Entities carry raw `planned_dispatches`, `completed_dispatches`, status metadata, and friendly names so you can confirm what Octopus is planning before an overnight charge.

### Smart-Charge Slot sensors

* `binary_sensor.intelligent_smart_charge_slot` (and the `next 1/2/3 hours` variations) stay `on` while Octopus Intelligent has an active or imminent smart-charge dispatch anywhere on your account.  These are the best choice when you want to know “is Octopus actually charging right now?”.
* Every vehicle also exposes its own `binary_sensor.<equipment>_smart_charge_slot` family that only reports `on` when that specific car has dispatches scheduled.  Their attributes include the raw `planned_dispatches`/`completed_dispatches` payloads for debugging or dashboards.

### Offpeak Window sensors

* `binary_sensor.intelligent_offpeak_window` (and the `next 1/2/3 hours` variations) represent the tariff’s configured cheap-rate window regardless of what Octopus is currently planning.  Use these when you just want to know “is the energy price cheap right now?”
* Each vehicle mirrors the same sensors (`binary_sensor.<equipment>_offpeak_window*`).  They automatically turn `off` if the device is suspended inside the Octopus app so you don’t accidentally rely on a car that can’t make use of the off-peak window.

### Planned dispatch sensor

* `binary_sensor.octopus_intelligent_planned_dispatch_slot` remains `on` whenever Octopus still reports a future smart-charge dispatch for the account.  It automatically drops back to `off` once every slot has ended, even if Octopus keeps the historical entries around.  Per-car equivalents surface the same data scoped to each device and expose the raw `planned_dispatches`/`completed_dispatches` attributes for debugging.

* `sensor.octopus_intelligent_next_offpeak_start` - will display the timestamp (UTC) of the next expected offpeak period start time.
* `sensor.octopus_intelligent_offpeak_end` - will display the timestamp (UTC) of the expected end of current offpeak period (will remain so during the following peak period until a new offpeak period starts)

NOTE: It has come to my attention that, when outside core offpeak hours (2330 -> 0530), if your car does not successfully charge during the planned slots then your usage will be billed at peak pricing.  This means that if charging is unreliable then the sensor won't reflect your billing accurately.

Need to adjust your cheap-rate window? Open Home Assistant → Settings → Devices & Services → Octopus Intelligent Tariff → Configure to set the off-peak start and end times without re-running the full setup.

### Configuration options

The Configure dialog (Settings → Devices & Services → Octopus Intelligent Tariff → Configure) lets you:

- Override the off-peak start/end time so sensors stay aligned with your tariff even if Octopus tweaks the window.
- Change the coordinator polling interval (minimum 10 seconds) when you want faster state changes or need to reduce API usage.

These options can be updated at any time; the integration persists them via Home Assistant’s config entry options, so re-authentication is never required.

* `switch.octopus_intelligent_bump_charge` and `switch.octopus_intelligent_smart_charging` - controls your Octopus Intelligent bump charge and smart charge settings

* `select.octopus_intelligent_target_time` and `select.octopus_intelligent_target_soc` - controls your Octopus Intelligent target ready time and SoC %.

## Intelligent charging entities

Every supported vehicle now exposes its own set of entities (switches, selects, sensors) alongside the original account-level summary entities.  This means your dashboard can display and control each car independently while still offering a single “Octopus Intelligent Tariff” view for quick status checks.

### Target ready time sensors

- `sensor.octopus_intelligent_target_ready_time` shows the earliest active “ready by” time across all vehicles.  The sensor switches between weekday/weekend schedules automatically and exposes rich attributes:
	- `mode` – whether weekday or weekend schedules are currently active.
	- `active_target_key` – which Octopus preference field supplied the live time.
	- `device_targets` – a list of every supported device with its weekday/weekend target times and SOC limits.
	- `target_device_id` / `target_device_label` – the vehicle that currently drives the account summary.
	- `device_count` – number of supported vehicles contributing to the summary.
- Each vehicle also has its own `sensor.<equipment_name>_target_ready_time`, which inherits the weekday/weekend mode handling and reports that device’s SOC limits so automations can react to per-car changes.

### Target SOC / Ready Time selects

The per-vehicle selects (`select.<equipment_name>_target_state_of_charge` and `select.<equipment_name>_target_ready_by_time`) now initialise immediately from coordinator data after Home Assistant restarts.  Their state only updates when Octopus sends fresh preferences, keeping Recorder history clean while ensuring the UI always reflects the latest settings.

![image](https://user-images.githubusercontent.com/1478003/208247955-41b9bf37-4599-4d61-83b1-0cd97611a60e.png)

# Guide

## Installation & Usage

1. Add repository to HACS (see https://hacs.xyz/docs/faq/custom_repositories) - use "https://github.com/dan-simms1/ha_octopus_intelligent" as the repository URL.
2. Install the `octopus_intelligent` integration inside HACS (You do NOT need to restart despite HACS saying so)
3. Goto Integrations page and add "Octopus Intelligent Tariff" integration as with any other integration
4. Follow config steps (Your Octopus API key can be found here: https://octopus.energy/dashboard/developer/ and your account ID is the string starting `A-` displayed near the top of your Octopus account page)

NOTE: Your api_key and account_id is stored strictly within your Home Assistant and does not get stored elsewhere.  It is only sent directly to the official Octopus API to exchange it for a authentication token necessary to use the API.
