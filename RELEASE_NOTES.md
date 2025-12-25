# Release Notes

## 2.0.17
- Added per-vehicle slot binaries (`slot`, `slot_next_n_hours`, and `planned_dispatch_slot`) so each supported car exposes its own view of Octopus-planned dispatches, complete with raw `planned_dispatches` / `completed_dispatches` attributes for automations.
- Normalised GraphQL dispatch `type` values (e.g. `SMART`, `BOOST`) to the canonical `smart-charge` / `bump-charge` sources so the combined charging-start sensor reports the first true dispatch instead of defaulting to 23:30.
- Introduced configurable off-peak start/end times inside the integration options flow, eliminating the need to re-run setup when Octopus changes your tariff window.
- Fixed the options flow so the Configure dialog opens reliably and added documentation pointing users to the new settings.

## 2.0.18
- Options dialog now instantiates cleanly via Home Assistant’s `OptionsFlow` base class, fixing the lingering 500 error when opening Configure and ensuring the new polling/off-peak settings are always accessible.

## 2.0.19
- Finalized the options dialog fix by aligning with Home Assistant’s internal flow handler expectations, preventing the remaining 500 error when opening Configure after 2.0.18.

## 2.0.24
- Device names now prefer the Octopus-provided label (when it isn’t an ID), preventing duplicated car names like `select.tesla_model_3_tesla_model_3_tesla_v2_target_state_of_charge` and keeping entity display names clean.
- Timestamp sensors (`Next Offpeak Start`, `Offpeak End`, `Intelligent Charging Start`) now publish their values immediately after the coordinator loads, so they no longer sit at `unknown` after a reload when data is already available.
- Per-car Planned Dispatch Slot sensors once again expose the raw `planned_dispatches` / `completed_dispatches` attributes for dashboards and automations.
