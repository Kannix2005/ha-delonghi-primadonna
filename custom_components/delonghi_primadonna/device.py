"""Delongi primadonna device description"""
import asyncio
import copy

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - fallback for older Home Assistant
    from homeassistant.backports.enum import StrEnum

import logging
import uuid
from binascii import crc_hqx, hexlify
from datetime import datetime
from enum import IntFlag

from bleak import BleakClient
from bleak.exc import BleakDBusError, BleakError
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (AMERICANO_OFF, AMERICANO_ON, AVAILABLE_PROFILES,
                    BASE_COMMAND, BYTES_AUTOPOWEROFF_COMMAND,
                    BYTES_LOAD_PROFILES, BYTES_POWER, BYTES_SWITCH_COMMAND,
                    BYTES_TIME_COMMAND, BYTES_WATER_HARDNESS_COMMAND,
                    BYTES_WATER_TEMPERATURE_COMMAND, COFFE_OFF, COFFE_ON,
                    COFFEE_GROUNDS_CONTAINER_CLEAN,
                    COFFEE_GROUNDS_CONTAINER_DETACHED,
                    COFFEE_GROUNDS_CONTAINER_FULL, CONTROLL_CHARACTERISTIC,
                    DEBUG, DEVICE_READY, DOMAIN,
                    DOPPIO_OFF, DOPPIO_ON, ECAM_ALARM, ECAM_MACHINE_STATE,
                    ESPRESSO2_OFF, ESPRESSO2_ON,
                    ESPRESSO_OFF, ESPRESSO_ON, HOTWATER_OFF, HOTWATER_ON,
                    LONG_OFF, LONG_ON, NAME_CHARACTERISTIC, NOZZLE_STATE,
                    START_COFFEE, STEAM_OFF, STEAM_ON, WATER_SHORTAGE,
                    WATER_TANK_DETACHED, DEVICE_TURNOFF)
from .machine_switch import (MachineSwitch, MachineAlarm,
                             parse_switches, parse_alarms, get_alarm_mask)
from .model import get_machine_model
from .protocol import (
    build_beverage_command,
    build_stop_command,
    build_read_profile_recipe,
    parse_profile_recipe_response,
    ACTION_START,
    OP_PREPARE,
)

_LOGGER = logging.getLogger(__name__)

START_BYTE = 0xD0


class BeverageEntityFeature(IntFlag):
    """Supported features of the beverage entity"""

    MAKE_BEVERAGE = 1
    SET_TEMPERATURE = 2
    SET_INTENCE = 4


class AvailableBeverage(StrEnum):
    """Coffee machine available beverages (legacy enum for backward compat)"""

    NONE = 'none'
    STEAM = 'steam'
    LONG = 'long'
    COFFEE = 'coffee'
    DOPIO = 'dopio'
    HOTWATER = 'hot_water'
    ESPRESSO = 'espresso'
    AMERICANO = 'americano'
    ESPRESSO2 = 'espresso2'


# Maps the legacy AvailableBeverage string values to ECAM beverage IDs
# so old service calls / automations keep working.
LEGACY_BEVERAGE_MAP: dict[str, int] = {
    'none': 0,
    'steam': 17,
    'long': 3,
    'coffee': 2,
    'dopio': 5,
    'hot_water': 16,
    'espresso': 1,
    'americano': 6,
    'espresso2': 4,
}

# Default recipe parameters for the legacy beverages (same values the
# old hardcoded byte arrays contained).  These are used as fallback
# when no profile-specific recipe is available.
LEGACY_DEFAULT_PARAMS: dict[int, list[tuple[int, int]]] = {
    1:  [(1, 40), (2, 3), (0, 0)],             # Espresso (Normal)
    2:  [(1, 103), (2, 2), (0, 0)],            # Coffee (Mild)
    3:  [(1, 160), (2, 3), (0, 0)],            # Long (Normal)
    4:  [(1, 40), (2, 2), (0, 0)],             # Espresso2x (Mild)
    5:  [(1, 120), (0, 0)],                    # Doppio+
    6:  [(1, 40), (2, 3), (15, 110), (0, 0)],  # Americano (Normal)
    16: [(15, 250), (28, 1)],                  # Hot Water
    17: [(9, 900), (28, 1)],                   # Steam
}


class NotificationType(StrEnum):
    """Coffee machine notification types"""

    STATUS = 'status'
    PROCESS = 'process'


class BeverageCommand:
    """Coffee machine beverage commands"""

    def __init__(self, on, off):
        self.on = on
        self.off = off


class BeverageNotify:
    """Coffee machine beverage notifications"""

    def __init__(self, kind, description):
        self.kind = str(kind)
        self.description = str(description)


class DeviceSwitches:
    """All binary switches for the device"""

    def __init__(self):
        self.sounds = False
        self.energy_save = False
        self.cup_light = False
        self.filter = False
        self.is_on = False


BEVERAGE_COMMANDS = {
    AvailableBeverage.NONE: BeverageCommand(DEBUG, DEBUG),
    AvailableBeverage.STEAM: BeverageCommand(STEAM_ON, STEAM_OFF),
    AvailableBeverage.LONG: BeverageCommand(LONG_ON, LONG_OFF),
    AvailableBeverage.COFFEE: BeverageCommand(COFFE_ON, COFFE_OFF),
    AvailableBeverage.DOPIO: BeverageCommand(DOPPIO_ON, DOPPIO_OFF),
    AvailableBeverage.HOTWATER: BeverageCommand(HOTWATER_ON, HOTWATER_OFF),
    AvailableBeverage.ESPRESSO: BeverageCommand(ESPRESSO_ON, ESPRESSO_OFF),
    AvailableBeverage.AMERICANO: BeverageCommand(AMERICANO_ON, AMERICANO_OFF),
    AvailableBeverage.ESPRESSO2: BeverageCommand(ESPRESSO2_ON, ESPRESSO2_OFF),
}

DEVICE_NOTIFICATION = {
    str(bytearray(DEVICE_READY)): BeverageNotify(
        NotificationType.STATUS, 'DeviceOK'
    ),
    str(bytearray(DEVICE_TURNOFF)): BeverageNotify(
        NotificationType.STATUS, 'DeviceOFF'
    ),
    str(bytearray(WATER_TANK_DETACHED)): BeverageNotify(
        NotificationType.STATUS, 'NoWaterTank'
    ),
    str(bytearray(WATER_SHORTAGE)): BeverageNotify(
        NotificationType.STATUS, 'NoWater'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_DETACHED)): BeverageNotify(
        NotificationType.STATUS, 'NoGroundsContainer'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_FULL)): BeverageNotify(
        NotificationType.STATUS, 'GroundsContainerFull'
    ),
    str(bytearray(COFFEE_GROUNDS_CONTAINER_CLEAN)): BeverageNotify(
        NotificationType.STATUS, 'GroundsContainerFull'
    ),
    str(bytearray(START_COFFEE)): BeverageNotify(
        NotificationType.STATUS, 'START_COFFEE'
    ),
}


class DelongiPrimadonna:
    """Delongi Primadonna class"""

    def __init__(self, config: dict, hass: HomeAssistant) -> None:
        """Initialize device"""
        self._device_status = None
        self._client = None
        self._hass = hass
        self._device = None
        self._connecting = False
        self.mac = config.get(CONF_MAC)
        self.name = config.get(CONF_NAME)
        self.product_code = config.get(CONF_MODEL)
        self.hostname = ''
        self.model = 'Prima Donna'
        self.friendly_name = ''
        self.cooking = AvailableBeverage.NONE
        self.connected = False
        self.notify = False
        self.steam_nozzle = NOZZLE_STATE[-1]
        self.service = 0
        self.status = 'STANDBY'
        self.machine_state = 0        # raw byte[9] value
        self.progress = 0             # byte[10] 0-100
        self.percentage = 0           # byte[11] 0-100
        self.alarm_mask = 0           # raw u16 alarm bitmask
        self.active_alarms: list[MachineAlarm] = []
        self.switches = DeviceSwitches()
        self.active_switches: list[MachineSwitch] = []
        self.sync_time = False
        self._lock = asyncio.Lock()
        self._rx_buffer = bytearray()
        self._response_event = None
        self._last_response: bytes | None = None
        machine = get_machine_model(self.product_code)
        self._n_profiles = (
            machine.nProfiles
            if machine and machine.nProfiles
            else len(AVAILABLE_PROFILES)
        )
        for pid in range(1, self._n_profiles + 1):
            AVAILABLE_PROFILES.setdefault(pid, f"Profile {pid}")
        for pid in list(AVAILABLE_PROFILES):
            if pid > self._n_profiles:
                AVAILABLE_PROFILES.pop(pid)
        self.profiles = list(AVAILABLE_PROFILES.values())
        self._profiles_loaded = False
        self._poll_unsub = None  # periodic poll cancel handle
        # ── Dynamic beverage support ──────────────────────────────
        # Ordered list of beverage display names for the select entity.
        self.available_beverages: list[str] = []
        # Maps display name → ECAM beverage ID.
        self._beverage_name_to_id: dict[str, int] = {}
        # Maps ECAM beverage ID → display name.
        self._beverage_id_to_name: dict[int, str] = {}
        # Default recipe params from MachinesModels.json per bev ID.
        self._beverage_defaults: dict[int, list[tuple[int, int]]] = {}
        # Profile-specific recipe overrides: {(profile_id, bev_id): params}
        self._profile_recipes: dict[tuple[int, int], list[tuple[int, int]]] = {}
        # Currently active profile id (1-based)
        self._active_profile_id: int = 1
        self._load_machine_beverages(machine)

    def _load_machine_beverages(self, machine) -> None:
        """Populate beverage lists from the machine model."""
        names: list[str] = []
        n2id: dict[str, int] = {}
        id2n: dict[int, str] = {}
        defaults: dict[int, list[tuple[int, int]]] = {}

        if machine and machine.recipes:
            for recipe in machine.recipes:
                try:
                    bev_id = int(recipe.id)
                except (TypeError, ValueError):
                    continue
                display = (
                    recipe.name.value
                    if recipe.name is not None
                    else f"Beverage {bev_id}"
                )
                # Avoid duplicate display names for custom recipes
                if display in n2id:
                    display = f"{display} ({bev_id})"
                names.append(display)
                n2id[display] = bev_id
                id2n[bev_id] = display
                # Build default parameters from JSON fields
                params: list[tuple[int, int]] = []
                if recipe.coffee_qty and recipe.coffee_qty > 0:
                    params.append((1, recipe.coffee_qty))
                if recipe.taste is not None:
                    params.append((2, recipe.taste))
                if recipe.milk_qty and recipe.milk_qty > 0:
                    params.append((9, recipe.milk_qty))
                # Temperature default = 0 (low) unless overridden
                params.append((0, 0))
                defaults[bev_id] = params

        if not names:
            # Fallback: use the legacy hardcoded beverages
            for legacy_name, bev_id in LEGACY_BEVERAGE_MAP.items():
                if bev_id == 0:  # skip 'none'
                    continue
                display = legacy_name.replace('_', ' ').title()
                names.append(display)
                n2id[display] = bev_id
                id2n[bev_id] = display
            defaults = dict(LEGACY_DEFAULT_PARAMS)

        self.available_beverages = names
        self._beverage_name_to_id = n2id
        self._beverage_id_to_name = id2n
        self._beverage_defaults = defaults

    def resolve_beverage_id(self, option: str) -> int | None:
        """Resolve a display name or legacy string to an ECAM beverage ID."""
        # Try display name first
        bev_id = self._beverage_name_to_id.get(option)
        if bev_id is not None:
            return bev_id
        # Try legacy enum value
        return LEGACY_BEVERAGE_MAP.get(option)

    def get_recipe_params(
        self, bev_id: int
    ) -> list[tuple[int, int]]:
        """Return recipe params for the active profile, with fallbacks."""
        # 1. Profile-specific override
        key = (self._active_profile_id, bev_id)
        if key in self._profile_recipes:
            return list(self._profile_recipes[key])
        # 2. Machine model defaults
        if bev_id in self._beverage_defaults:
            return list(self._beverage_defaults[bev_id])
        # 3. Legacy hardcoded defaults
        if bev_id in LEGACY_DEFAULT_PARAMS:
            return list(LEGACY_DEFAULT_PARAMS[bev_id])
        # 4. Bare minimum
        return []

    @property
    def signal_state_updated(self) -> str:
        """Dispatcher signal name for state updates."""
        return f"{DOMAIN}_state_updated_{self.mac}"

    async def disconnect(self):
        """Disconnect from the device."""
        _LOGGER.info("Disconnect from %s", self.mac)
        async with self._lock:
            client = self._client
            if client is not None and client.is_connected:
                try:
                    await asyncio.wait_for(client.disconnect(), timeout=5)
                except (
                    asyncio.TimeoutError,
                    Exception,
                ) as error:  # noqa: BLE001
                    _LOGGER.warning(
                        "Forced disconnect [%s]: %s",
                        type(error).__name__,
                        error
                    )
                finally:
                    self._client = None
                    self.connected = False
            else:
                self._client = None
                self.connected = False

    async def _connect(self, retries=3):
        """Connect to the device."""
        self._connecting = True
        last_error = None
        for attempt in range(retries):
            try:
                if self._client is None or not self._client.is_connected:
                    self._device = bluetooth.async_ble_device_from_address(
                        self._hass, self.mac, connectable=True
                    )
                    if not self._device:
                        raise BleakError(
                            (
                                f"A device with address {self.mac}"
                                " could not be found."
                            )
                        )
                    self._client = BleakClient(self._device)
                    _LOGGER.info(
                        "Connect to %s (attempt %d)",
                        self.mac,
                        attempt + 1,
                    )
                    await asyncio.wait_for(
                        self._client.connect(),
                        timeout=10,
                    )
                    # Service discovery is performed during the connection
                    # process. Accessing ``get_services`` directly raises a
                    # ``FutureWarning`` in recent versions of Bleak.
                    # ``self._client.services`` will contain the discovered
                    # services once the connection succeeds.
                    await asyncio.wait_for(
                        self._client.start_notify(
                            uuid.UUID(CONTROLL_CHARACTERISTIC),
                            self._process_raw_data,
                        ),
                        timeout=10,
                    )
                self._connecting = False
                return
            except Exception as error:
                _LOGGER.warning(
                    "BLE connect error: %s (type: %s, attempt %d)",
                    error,
                    type(error).__name__,
                    attempt + 1,
                )
                if self._client is not None:
                    try:
                        await asyncio.wait_for(
                            self._client.disconnect(), timeout=5
                        )
                    except Exception:  # noqa: BLE001
                        pass
                self._client = None
                last_error = error
                await asyncio.sleep(2)
        self._connecting = False
        raise last_error

    def _make_switch_command(self):
        """Make hex command"""
        base_command = list(BASE_COMMAND)
        base_command[3] = '1' if self.switches.energy_save else '0'
        base_command[4] = '1' if self.switches.cup_light else '0'
        base_command[5] = '1' if self.switches.sounds else '0'
        hex_command = BYTES_SWITCH_COMMAND.copy()
        hex_command[9] = int(''.join(base_command), 2)
        return hex_command

    async def _event_trigger(self, value):
        """
        Trigger event with semantic classification.
        Uses byte analysis instead of exact byte matching for
        model-independent event detection.
        :param value: event value
        """
        event_data = {'data': str(hexlify(value, ' '))}

        notification_message = (
            str(hexlify(value, ' '))
            .replace(' ', ', 0x')
            .replace("b'", '[0x')
            .replace("'", ']')
        )

        # Try semantic classification first (model-independent)
        notification = None
        if len(value) >= 12 and value[2] == 0x75:
            notification = self._classify_notification(value)

        # Fallback to legacy exact byte matching
        if notification is None:
            legacy_key = str(bytearray(value))
            if legacy_key in DEVICE_NOTIFICATION:
                notification = DEVICE_NOTIFICATION.get(legacy_key)

        if notification is not None:
            notification_message = notification.description
            event_data['type'] = notification.kind
            event_data['description'] = notification.description

        self._hass.bus.async_fire(f'{DOMAIN}_event', event_data)

        if self.notify:
            answer_id = f"{value[2]:02x}"
            await self._hass.services.async_call(
                'persistent_notification',
                'create',
                {
                    'message': notification_message,
                    'title': f'{self.name} {answer_id}',
                    'notification_id': f'{self.mac}_err_{uuid.uuid4()}',
                },
            )
        _LOGGER.info('Event triggered: %s', event_data)

    def _classify_notification(self, value):
        """Classify 0x75 notification by protocol-correct byte analysis.

        MonitorV2 (0x75) byte layout (APK MonitorDataV2 + longshot):
          byte[4]     = EcamAccessory  (nozzle/accessory type)
          byte[5-6]   = u16 LE switches bitmask
          byte[7-8]   = u16 LE alarms LOW (bits 0-15)
          byte[9]     = EcamMachineState
          byte[10]    = progress (0-100)
          byte[11]    = percentage (0-100)
          byte[12-13] = u16 LE alarms HIGH (bits 16-31)
        """
        state = value[9]
        progress = value[10] if len(value) > 10 else 0
        alarm_mask = get_alarm_mask(value)

        # Priority order from longshot EcamStatus::extract()
        if state == 1:  # TurningOn
            return BeverageNotify(NotificationType.PROCESS, 'TurningOn')
        if state == 2:  # ShuttingDown
            return BeverageNotify(NotificationType.STATUS, 'DeviceOFF')
        if state in (8, 12):  # Rinsing, MilkCleaning
            return BeverageNotify(NotificationType.PROCESS, 'Rinsing')
        if state in (10, 11) or (state == 7 and progress > 0):
            return BeverageNotify(NotificationType.PROCESS, 'START_COFFEE')
        if state == 4:  # Descaling
            return BeverageNotify(NotificationType.PROCESS, 'Descaling')

        # Check alarms (skip CleanKnob = bit 14)
        non_warning = alarm_mask & ~(1 << 14)
        if non_warning:
            if non_warning & (1 << 0):
                return BeverageNotify(NotificationType.STATUS, 'NoWater')
            if non_warning & (1 << 1):
                return BeverageNotify(
                    NotificationType.STATUS, 'GroundsContainerFull')
            if non_warning & (1 << 5):
                return BeverageNotify(
                    NotificationType.STATUS, 'CoffeeBeansEmpty')
            return BeverageNotify(NotificationType.STATUS, 'Alarm')

        if state == 0:  # StandBy
            return BeverageNotify(NotificationType.STATUS, 'DeviceOFF')

        return BeverageNotify(NotificationType.STATUS, 'DeviceOK')

    @staticmethod
    def _determine_status(state: int, progress: int, alarm_mask: int) -> str:
        """Determine user-facing status from machine state + context.

        Follows longshot EcamStatus::extract() priority order exactly:
          1. TurningOn
          2. ShuttingDown
          3. Rinsing / MilkCleaning  → RINSING
          4. MilkPrep / HotWater / (Ready+progress)  → DISPENSING
          5. Descaling
          6. Alarm (non-CleanKnob)
          7. StandBy
          8. else → READY
        """
        if state == 1:  # TurningOn
            return 'TURNING_ON'
        if state == 2:  # ShuttingDown
            return 'SHUTTING_DOWN'
        if state in (8, 12):  # Rinsing, MilkCleaning
            return 'RINSING'
        if state in (10, 11) or (state == 7 and progress > 0):
            # MilkPreparation, HotWaterDelivery, or ReadyOrDispensing+active
            return 'DISPENSING'
        if state == 4:  # Descaling
            return 'DESCALING'
        # Check alarms — skip CleanKnob (bit 14) which is a warning
        non_warning = alarm_mask & ~(1 << 14)
        if non_warning:
            return 'ALARM'
        if state == 0:  # StandBy
            return 'STANDBY'
        # SteamPreparation(5), Recovery(6), ChocolatePreparation(16), etc.
        return 'READY'

    async def _process_raw_data(self, sender, value):
        """Assemble incoming BLE packets and pass complete messages."""
        self._rx_buffer.extend(value)

        while True:
            if len(self._rx_buffer) < 2:
                return
            try:
                start_index = self._rx_buffer.index(START_BYTE)
            except ValueError:
                self._rx_buffer.clear()
                return

            if start_index > 0:
                del self._rx_buffer[:start_index]

            if len(self._rx_buffer) < 2:
                return

            msg_len = self._rx_buffer[1] + 1

            if len(self._rx_buffer) < msg_len:
                return

            packet = bytes(self._rx_buffer[:msg_len])
            del self._rx_buffer[:msg_len]
            await self._handle_data(sender, packet)

    async def _handle_data(self, sender, value):
        """Handle notifications from the device."""
        if (
            self._response_event is not None
            and not self._response_event.is_set()
        ):
            self._response_event.set()
        answer_id = value[2] if len(value) > 2 else None

        if answer_id == 0x75:
            # ── MonitorV2 protocol-correct parsing ─────────────────
            # byte[4]     = EcamAccessory (nozzle type)
            # byte[5-6]   = u16 LE switches bitmask
            # byte[7-8]   = u16 LE alarms LOW (bits 0-15)
            # byte[9]     = EcamMachineState
            # byte[10]    = progress (0-100)
            # byte[11]    = percentage (0-100)
            # byte[12-13] = u16 LE alarms HIGH (bits 16-31)
            self.steam_nozzle = NOZZLE_STATE.get(value[4], str(value[4]))
            self.active_switches = parse_switches(value)
            self.active_alarms = parse_alarms(value)
            self.alarm_mask = get_alarm_mask(value)
            self.service = value[7]  # alarm_low — backward compat

            state = value[9]
            self.machine_state = state
            self.switches.is_on = state != 0  # 0=StandBy=off
            self.progress = value[10] if len(value) > 10 else 0
            self.percentage = value[11] if len(value) > 11 else 0

            # Status determination — follows longshot EcamStatus::extract()
            self.status = self._determine_status(
                state, self.progress, self.alarm_mask
            )
        elif answer_id == 0xA6:
            # Profile-specific recipe response
            parsed_recipe = parse_profile_recipe_response(value)
            if parsed_recipe is not None:
                pid, bev_id, params = parsed_recipe
                self._profile_recipes[(pid, bev_id)] = params
                _LOGGER.debug(
                    "Profile %d beverage %d recipe: %s",
                    pid, bev_id, params,
                )
        elif answer_id == 0xA4:
            parsed = []
            try:
                parsed = self._parse_profile_response(
                    list(value)
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Failed to parse profile response: %s", err)
            for pid, name in parsed.items():
                AVAILABLE_PROFILES[pid] = name
            _LOGGER.debug(
                "Available profiles: %s",
                AVAILABLE_PROFILES
            )
            self.profiles = list(AVAILABLE_PROFILES.values())
        elif answer_id == 0xA9:
            profile_id = value[4] if len(value) > 4 else None
            status = value[5] if len(value) > 5 else None
            _LOGGER.debug(
                "Profile change response id=%s status=%s raw=%s",
                profile_id,
                status,
                hexlify(value, " "),
            )

        hex_value = hexlify(value, ' ')

        state_changed = self._device_status != hex_value
        if state_changed:
            _LOGGER.info(
                'Received data: %s from %s',
                hex_value,
                sender
            )
            await self._event_trigger(value)

        self._device_status = hex_value

        # Push state to all listening entities immediately
        # Only signal on actual state changes to avoid unnecessary
        # async_write_ha_state calls (~15 packets/min with polling)
        if state_changed or answer_id == 0x75:
            async_dispatcher_send(self._hass, self.signal_state_updated)

    def _parse_profile_response(
        self,
        data: list[int],
    ) -> dict[int, str]:
        """Parse profile names sent by the machine."""

        b = bytes(data)
        if len(b) < 4 or b[0] != 0xD0:
            raise ValueError("Wrong start byte")

        profiles: dict[int, str] = {}
        NAME_SIZE = 20
        NAME_OFFSET = 1
        NAME_HEADER = 4
        profile_index = 1
        idx = NAME_HEADER
        while idx + NAME_SIZE < len(b):
            profiles.setdefault(
                profile_index,
                b[idx:idx + NAME_SIZE]
                .decode("utf-16-be")
                .rstrip("\x00")
                .strip(),
            )
            profile_index += 1
            idx += NAME_SIZE + NAME_OFFSET
        return profiles

    async def power_on(self) -> None:
        """Turn the device on."""
        await self.send_command(BYTES_POWER)

    async def cup_light_on(self) -> None:
        """Turn the cup light on."""
        self.switches.cup_light = True
        await self.send_command(self._make_switch_command())

    async def cup_light_off(self) -> None:
        """Turn the cup light off."""
        self.switches.cup_light = False
        await self.send_command(self._make_switch_command())

    async def energy_save_on(self):
        """Enable energy save mode"""
        self.switches.energy_save = True
        await self.send_command(self._make_switch_command())

    async def energy_save_off(self):
        """Enable energy save mode"""
        self.switches.energy_save = False
        await self.send_command(self._make_switch_command())

    async def sound_alarm_on(self):
        """Enable sound alarm"""
        self.switches.sounds = True
        await self.send_command(self._make_switch_command())

    async def sound_alarm_off(self):
        """Disable sound alarm"""
        self.switches.sounds = False
        await self.send_command(self._make_switch_command())

    async def beverage_start(self, beverage) -> None:
        """Start a beverage by display name or legacy string."""
        bev_id = self.resolve_beverage_id(beverage)
        if bev_id is None or bev_id == 0:
            _LOGGER.debug("Ignoring beverage_start for '%s'", beverage)
            return
        params = self.get_recipe_params(bev_id)
        cmd = build_beverage_command(
            beverage_id=bev_id,
            action=ACTION_START,
            parameters=params,
            profile_id=self._active_profile_id,
            operation=OP_PREPARE,
        )
        _LOGGER.info(
            "Preparing beverage '%s' (id=%d, profile=%d) params=%s",
            beverage, bev_id, self._active_profile_id, params,
        )
        self.cooking = beverage
        await self.send_command(cmd)

    async def beverage_cancel(self) -> None:
        """Cancel the currently dispensing beverage."""
        if self.cooking and self.cooking != AvailableBeverage.NONE:
            bev_id = self.resolve_beverage_id(self.cooking)
            if bev_id and bev_id != 0:
                cmd = build_stop_command(
                    beverage_id=bev_id,
                    profile_id=self._active_profile_id,
                )
                await self.send_command(cmd)

    async def debug(self):
        """Send command which causes status reply"""
        await self.send_command(DEBUG)

    async def get_device_name(self):
        """
        Get device name
        :return: device name
        """
        async with self._lock:
            try:
                await self._connect()
                self.hostname = bytes(
                    await self._client.read_gatt_char(
                        uuid.UUID(NAME_CHARACTERISTIC)
                    )
                ).decode('utf-8')
                await self._client.write_gatt_char(
                    uuid.UUID(CONTROLL_CHARACTERISTIC), bytearray(DEBUG)
                )
                self.connected = True
            except BleakDBusError as error:
                self.connected = False
                _LOGGER.warning('BleakDBusError: %s', error)
            except BleakError as error:
                self.connected = False
                _LOGGER.warning('BleakError: %s', error)
            except asyncio.exceptions.TimeoutError as error:
                self.connected = False
                _LOGGER.info('TimeoutError: %s at device connection', error)
            except asyncio.exceptions.CancelledError as error:
                self.connected = False
                _LOGGER.warning('CancelledError: %s', error)

        if self.connected and not self._profiles_loaded:
            command = BYTES_LOAD_PROFILES.copy()
            command[5] = self._n_profiles
            await self.send_command(command)
            self._profiles_loaded = True
            # Load profile-specific recipes for the active profile
            await self.load_profile_recipes(self._active_profile_id)

    async def set_time(self, dt: datetime) -> None:
        """Set device clock from provided datetime."""
        packet = BYTES_TIME_COMMAND.copy()
        packet[4] = dt.hour & 0xFF
        packet[5] = dt.minute & 0xFF
        await self.send_command(packet)

    async def select_profile(self, profile_id) -> None:
        """select a profile."""
        _LOGGER.debug("Send select profile command id=%s", profile_id)
        self._active_profile_id = profile_id
        message = [0x0D, 0x06, 0xA9, 0xF0, profile_id, 0xD7, 0xC0]
        await self.send_command(message)
        # Load profile-specific recipes for all beverages
        await self.load_profile_recipes(profile_id)

    async def load_profile_recipes(self, profile_id: int) -> None:
        """Request profile-specific recipes for all known beverages."""
        for bev_id in self._beverage_id_to_name:
            cmd = build_read_profile_recipe(profile_id, bev_id)
            try:
                await self.send_command(cmd)
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to load recipe for profile=%d bev=%d",
                    profile_id, bev_id,
                )
        _LOGGER.info(
            "Loaded %d profile recipes for profile %d",
            len([
                k for k in self._profile_recipes
                if k[0] == profile_id
            ]),
            profile_id,
        )

    async def set_auto_power_off(self, power_off_interval) -> None:
        """Set auto power off time."""
        message = copy.deepcopy(BYTES_AUTOPOWEROFF_COMMAND)
        message[9] = power_off_interval
        await self.send_command(message)

    async def set_water_hardness(self, hardness_level) -> None:
        """Set water hardness"""
        message = copy.deepcopy(BYTES_WATER_HARDNESS_COMMAND)
        message[9] = hardness_level
        await self.send_command(message)

    async def set_water_temperature(self, temperature_level) -> None:
        """Set water temperature"""
        message = copy.deepcopy(BYTES_WATER_TEMPERATURE_COMMAND)
        message[9] = temperature_level
        await self.send_command(message)

    async def common_command(self, command: str) -> None:
        """Send custom BLE command"""
        message = [int(x, 16) for x in command.split(' ')]
        await self.send_command(message)

    async def poll_status(self):
        """Lightweight status poll — shorter timeout, no retry.

        Used by the periodic polling loop. Unlike send_command(), this
        won't block for 30+ seconds on connection issues, allowing the
        poll loop to attempt reconnects sooner.
        """
        if self._lock.locked():
            return  # Another command is in progress, skip poll
        async with self._lock:
            try:
                if not self._client or not self._client.is_connected:
                    self.connected = False
                    return
                message = copy.deepcopy(DEBUG)
                crc = crc_hqx(bytearray(message[:-2]), 0x1D0F)
                crc_bytes = crc.to_bytes(2, byteorder='big')
                message[-2] = crc_bytes[0]
                message[-1] = crc_bytes[1]
                self._response_event = asyncio.Event()
                await self._client.write_gatt_char(
                    CONTROLL_CHARACTERISTIC, bytearray(message)
                )
                try:
                    await asyncio.wait_for(
                        self._response_event.wait(), timeout=3
                    )
                except asyncio.TimeoutError:
                    _LOGGER.debug('Poll timeout — connection may be stale')
                    self.connected = False
                finally:
                    self._response_event = None
            except (BleakError, BleakDBusError, Exception) as error:
                self.connected = False
                self._client = None
                _LOGGER.debug('Poll failed: %s', error)

    async def send_command(self, message, retries=3):
        async with self._lock:
            message_to_send = copy.deepcopy(message)
            for attempt in range(retries):
                try:
                    await self._connect()
                    crc = crc_hqx(bytearray(message_to_send[:-2]), 0x1D0F)
                    crc_bytes = crc.to_bytes(2, byteorder='big')
                    message_to_send[-2] = crc_bytes[0]
                    message_to_send[-1] = crc_bytes[1]
                    _LOGGER.info(
                        'Send command: %s',
                        hexlify(bytearray(message_to_send), " ")
                    )
                    self._response_event = asyncio.Event()
                    await self._client.write_gatt_char(
                        CONTROLL_CHARACTERISTIC, bytearray(message_to_send)
                    )
                    try:
                        await asyncio.wait_for(
                            self._response_event.wait(),
                            timeout=10,
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.warning(
                            'Timeout waiting for response to command: %s',
                            hexlify(bytearray(message_to_send), " ")
                        )
                    finally:
                        self._response_event = None
                    return
                except BleakError as error:
                    self.connected = False
                    self._client = None
                    _LOGGER.warning(
                        'BleakError: %s (attempt %d)',
                        error,
                        attempt + 1
                    )
                    await asyncio.sleep(2)
            _LOGGER.error('Failed to send command after %d attempts', retries)
