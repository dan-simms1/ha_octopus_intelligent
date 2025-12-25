# octopus_intelligent
Octopus Intelligent Home Assistant integration

* `binary_sensor.octopus_intelligent_slot` - will be `on` when your electricity is cheap. This includes when your car is charging outside of the normal Octopus Intelligent offpeak times but NOT when bump charging (unless within off peak hours)

* `binary_sensor.octopus_intelligent_planned_dispatch_slot` - will be `on` when Octopus plans to charge your car. This includes when your car is charging outside of the normal Octopus Intelligent offpeak times but NOT when bump charging.  Your electricity might be offpeak when this sensor reports "off" (e.g. during the overnight 6 hours)

* `binary_sensor.octopus_intelligent_slot_next_1_hour` - will be `on` when your electricity is cheap for the next 1 hour.
* `binary_sensor.octopus_intelligent_slot_next_2_hours` - will be `on` when your electricity is cheap for the next 2 hours.
* `binary_sensor.octopus_intelligent_slot_next_3_hours` - will be `on` when your electricity is cheap for the next 3 hours.

Every supported vehicle exposes the same family of slot sensors, e.g. `binary_sensor.tesla_model_3_slot`, `binary_sensor.tesla_model_3_slot_next_1_hour` and `binary_sensor.tesla_model_3_planned_dispatch_slot`.  These per-car entities only report `on` when Octopus has actually scheduled dispatches for that specific vehicle, and their attributes include the raw `planned_dispatches`/`completed_dispatches` payloads so automations can inspect the exact schedule that Octopus published.

* `sensor.octopus_intelligent_next_offpeak_start` - will display the timestamp (UTC) of the next expected offpeak period start time.
* `sensor.octopus_intelligent_offpeak_end` - will display the timestamp (UTC) of the expected end of current offpeak period (will remain so during the following peak period until a new offpeak period starts)

NOTE: It has come to my attention that, when outside core offpeak hours (2330 -> 0530), if your car does not successfully charge during the planned slots then your usage will be billed at peak pricing.  This means that if charging is unreliable then the sensor won't reflect your billing accurately.

Need to adjust your cheap-rate window? Open Home Assistant → Settings → Devices & Services → Octopus Intelligent Tariff → Configure to set the off-peak start and end times without re-running the full setup.

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

1. Add repository to HACS (see https://hacs.xyz/docs/faq/custom_repositories) - use "https://github.com/megakid/ha_octopus_intelligent" as the repository URL.
2. Install the `octopus_intelligent` integration inside HACS (You do NOT need to restart despite HACS saying so)
3. Goto Integrations page and add "Octopus Intelligent Tariff" integration as with any other integration
4. Follow config steps (Your Octopus API key can be found here: https://octopus.energy/dashboard/developer/ and your account ID is the string starting `A-` displayed near the top of your Octopus account page)

NOTE: Your api_key and account_id is stored strictly within your Home Assistant and does not get stored elsewhere.  It is only sent directly to the official Octopus API to exchange it for a authentication token necessary to use the API.
