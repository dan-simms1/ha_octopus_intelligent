# Release Notes

## 2.0.17
- Added per-vehicle slot binaries (`slot`, `slot_next_n_hours`, and `planned_dispatch_slot`) so each supported car exposes its own view of Octopus-planned dispatches, complete with raw `planned_dispatches` / `completed_dispatches` attributes for automations.
- Normalised GraphQL dispatch `type` values (e.g. `SMART`, `BOOST`) to the canonical `smart-charge` / `bump-charge` sources so the combined charging-start sensor reports the first true dispatch instead of defaulting to 23:30.
- Introduced configurable off-peak start/end times inside the integration options flow, eliminating the need to re-run setup when Octopus changes your tariff window.
- Fixed the options flow so the Configure dialog opens reliably and added documentation pointing users to the new settings.
