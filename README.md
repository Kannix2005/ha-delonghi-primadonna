# DeLonghi Primadonna BLE Integration for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Kannix2005/ha-delonghi-primadonna)](https://github.com/Kannix2005/ha-delonghi-primadonna/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Custom Home Assistant integration for DeLonghi Primadonna coffee machines via Bluetooth Low Energy (BLE).

> **Fork notice:** This integration is based on [Arbuzov/home_assistant_delonghi_primadonna](https://github.com/Arbuzov/home_assistant_delonghi_primadonna) with a **complete protocol rewrite** based on the [mmastrac/longshot](https://github.com/mmastrac/longshot) reverse-engineering project.

## What's Different

The original integration had **fundamentally incorrect byte parsing** of the ECAM BLE protocol (`MonitorV2` / `0x75` response). This fork fixes:

| Issue | Original | Fixed |
|-------|----------|-------|
| Switch bitmask | `data[5] \| (data[7] << 8)` | `data[5] \| (data[6] << 8)` — u16 LE at byte[5-6] |
| Alarm bitmask | Not parsed | `data[7] \| (data[8] << 8)` — u16 LE at byte[7-8] |
| Machine state | `data[5]` as status enum | `data[9]` = `EcamMachineState` enum |
| Progress | `data[10]` as stage enum | `data[10]` = progress percentage (0-100) |
| Status determination | Single byte lookup | Priority-based logic matching longshot's `EcamStatus::extract()` |

### New Entities

- **Alarm Sensor** — Shows active machine alarms (empty water tank, coffee waste full, descale needed, etc.)
- **Progress Sensor** — Beverage dispensing progress as percentage (0-100%)
- **Enhanced Status Sensor** — Extra attributes: `machine_state`, `machine_state_raw`, `progress`, `percentage`, `alarms`

### New Status Values

| Status | When |
|--------|------|
| `STANDBY` | Machine is off / standby |
| `TURNING_ON` | Machine is warming up |
| `SHUTTING_DOWN` | Machine is shutting down |
| `READY` | Ready for beverage selection |
| `DISPENSING` | Making coffee / hot water / milk |
| `RINSING` | Rinsing or milk cleaning cycle |
| `DESCALING` | Descaling in progress |
| `ALARM` | Active alarm (non-warning) |

### Lightweight Polling

- `poll_status()` — 3-second timeout, no retries, skips if BLE lock is held
- 5-second polling interval with 30-second reconnect throttle
- Push-based entity updates via Home Assistant dispatcher (no `should_poll`)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the 3 dots in the top right → **Custom repositories**
3. Add `https://github.com/Kannix2005/ha-delonghi-primadonna` as **Integration**
4. Search for "DeLonghi" and install
5. Restart Home Assistant
6. Add the integration via **Settings → Devices & Services → Add Integration → DeLonghi BLE**

### Manual

1. Copy `custom_components/delonghi_primadonna` to your HA `custom_components/` directory
2. Restart Home Assistant
3. Add the integration via **Settings → Devices & Services → Add Integration → DeLonghi BLE**

## Requirements

- Home Assistant 2024.8.0 or newer
- Bluetooth adapter or ESPHome BLE Proxy
- DeLonghi Primadonna coffee machine with BLE support

## Protocol Reference

This integration implements the ECAM BLE protocol as documented by [mmastrac/longshot](https://github.com/mmastrac/longshot):

```
MonitorV2 (0x75) response payload:
  byte[4]     = EcamAccessory   (nozzle type: 0=none, 1=water, 2=milk, 3=choco, 4=milk_clean)
  byte[5-6]   = EcamMachineSwitch  (u16 LE bitmask — water spout, motor, tank, knob, etc.)
  byte[7-8]   = EcamMachineAlarm   (u16 LE bitmask — water empty, waste full, descale, etc.)
  byte[9]     = EcamMachineState   (0=StandBy, 1=TurningOn, 7=ReadyOrDispensing, 8=Rinsing, ...)
  byte[10]    = progress           (0-100)
  byte[11]    = percentage         (0-100)
```

CRC: CRC-16/AUG-CCITT with init value `0x1D0F`.

## Supported Machines

See [MachinesModels.json](custom_components/delonghi_primadonna/MachinesModels.json) for the full list. Generally any DeLonghi ECAM machine with Bluetooth should work.

## Credits

- [Arbuzov](https://github.com/Arbuzov) — Original integration
- [mmastrac/longshot](https://github.com/mmastrac/longshot) — Authoritative ECAM BLE protocol reverse engineering
- [grack.com](https://mmastrac.substack.com/) — Protocol research blog posts

## License

MIT — see [LICENSE](LICENSE)
