# Release Notes

## 2.2.0
- Device entries can now be deleted from the Home Assistant UI; deleted cars are remembered and won't be re-created.
- Device deletion is now restricted to car/charger devices; the account-level Octopus Intelligent Tariff device can't be deleted from the UI.

## 2.1.3
- Configure dialog now lets you update the Octopus API key and account ID without deleting the integration, and the coordinator automatically uses the newest credentials.
- Options flow re-validates credentials only when they change, guarding against typos while keeping existing keys untouched.

## 2.1.1
- Fixed the Target State of Charge select so it no longer crashes when Octopus returns `HH:MM:SS` timestamps. Time parsing now accepts seconds, and regression tests cover the helper.

## 2.1.2
- Account-level sensors now drop the redundant `Intelligent` prefix so their display names align with the per-car entities without breaking existing entity IDs.

## 2.1.0
- README refreshed to highlight the multi-car entity set, slot differentiation, updated configuration options, and the new canonical repository URL so documentation now mirrors the latest behaviour.

## 2.0.29
- ISO8601 timestamps with colon offsets (e.g. `+00:00`) are now parsed correctly, so Planned Dispatch Slot sensors drop past slots even when Octopus returns the raw schedule format.
- Added regression tests covering the new parser to prevent future regressions.

## 2.0.28
- Planned Dispatch Slot sensors now ignore stale dispatches, ensuring they only stay `on` when Octopus still has a future smart-charge window scheduled for that device/account.
- Added defensive timestamp parsing plus regression tests so malformed or legacy API responses can’t keep the sensors stuck in the `on` state.

## 2.0.17
- Added per-vehicle slot binaries (`slot`, `slot_next_n_hours`, and `planned_dispatch_slot`) so each supported car exposes its own view of Octopus-planned dispatches, complete with raw `planned_dispatches` / `completed_dispatches` attributes for automations.
- Normalised GraphQL dispatch `type` values (e.g. `SMART`, `BOOST`) to the canonical `smart-charge` / `bump-charge` sources so the combined charging-start sensor reports the first true dispatch instead of defaulting to 23:30.
- Introduced configurable off-peak start/end times inside the integration options flow, eliminating the need to re-run setup when Octopus changes your tariff window.
- Fixed the options flow so the Configure dialog opens reliably and added documentation pointing users to the new settings.

## 2.0.18
- Options dialog now instantiates cleanly via Home Assistant’s `OptionsFlow` base class, fixing the lingering 500 error when opening Configure and ensuring the new polling/off-peak settings are always accessible.

## 2.0.19
- Finalized the options dialog fix by aligning with Home Assistant’s internal flow handler expectations, preventing the remaining 500 error when opening Configure after 2.0.18.

## 2.0.27
- Slot sensors now share a single helper inside the coordinator, reducing drift between the smart-charge and off-peak calculations and making the logic easier to test.
- Binary sensor classes reuse a common base for naming/device-info so account-level and per-car entities stay consistent even as we add new views.
- Added regression tests covering the slot-mode helper to guard against future behaviour changes.
- README updated to describe the new Smart-Charge vs Offpeak sensor families.

## 2.0.26
- Split the old `Slot` binary sensor into explicit `Smart-Charge Slot` entities (showing when an Octopus intelligent dispatch is planned/running) and new `Offpeak Window` entities that mirror the tariff’s cheap-rate window, removing the ambiguity between the two concepts.
- Added per-car and combined variants of the `Offpeak Window` sensors so dashboards can show both “when the tariff is cheap” and “when Octopus is actually charging” for each device.

## 2.0.25
- Device names now prefer the Octopus-provided label (when it isn’t an ID), preventing duplicated car names like `select.tesla_model_3_tesla_model_3_tesla_v2_target_state_of_charge` and keeping entity display names clean.
- Timestamp sensors (`Next Offpeak Start`, `Offpeak End`, `Intelligent Charging Start`) now publish their values immediately after the coordinator loads, so they no longer sit at `unknown` after a reload when data is already available.
- Per-car Planned Dispatch Slot sensors once again expose the raw `planned_dispatches` / `completed_dispatches` attributes for dashboards and automations.
- Per-car timestamp sensors now fall back to the standard off-peak window whenever all stored dispatch slots are in the past, preventing them from getting stuck at `unknown` while the combined view continues to work.
- Account-level sensors now drop the `Octopus` prefix (for example, `Octopus Intelligent Charging Start` → `Intelligent Charging Start`) so their titles match the per-car entities.
