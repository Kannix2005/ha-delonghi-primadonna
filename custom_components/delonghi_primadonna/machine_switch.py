from __future__ import annotations

from enum import Enum
from typing import List


class MachineSwitch(Enum):
    """Known machine switches (byte[5-6] u16 LE bitmask).

    Source: mmastrac/longshot EcamMachineSwitch enum.
    """

    WATER_SPOUT = "water_spout"              # bit 0
    MOTOR_UP = "motor_up"                    # bit 1
    MOTOR_DOWN = "motor_down"                # bit 2
    COFFEE_WASTE_CONTAINER = "coffee_waste_container"  # bit 3
    WATER_TANK_ABSENT = "water_tank_absent"  # bit 4
    KNOB = "knob"                            # bit 5
    WATER_LEVEL_LOW = "water_level_low"      # bit 6
    COFFEE_JUG = "coffee_jug"               # bit 7
    IFD_CARAFFE = "ifd_caraffe"             # bit 8
    CIOCCO_TANK = "ciocco_tank"             # bit 9
    CLEAN_KNOB = "clean_knob"               # bit 10
    DOOR_OPENED = "door_opened"             # bit 13
    PREGROUND_DOOR_OPENED = "preground_door_opened"  # bit 14
    UNKNOWN_SWITCH = "unknown_switch"
    IGNORE_SWITCH = "ignore_switch"


class MachineAlarm(Enum):
    """Known machine alarms (byte[7-8] u16 LE bitmask).

    Source: mmastrac/longshot EcamMachineAlarm enum.
    """

    EMPTY_WATER_TANK = "empty_water_tank"                  # bit 0
    COFFEE_WASTE_CONTAINER_FULL = "coffee_waste_container_full"  # bit 1
    DESCALE_ALARM = "descale_alarm"                        # bit 2
    REPLACE_WATER_FILTER = "replace_water_filter"          # bit 3
    COFFEE_GROUND_TOO_FINE = "coffee_ground_too_fine"      # bit 4
    COFFEE_BEANS_EMPTY = "coffee_beans_empty"              # bit 5
    MACHINE_TO_SERVICE = "machine_to_service"              # bit 6
    COFFEE_HEATER_PROBE_FAILURE = "coffee_heater_probe_failure"  # bit 7
    TOO_MUCH_COFFEE = "too_much_coffee"                    # bit 8
    COFFEE_INFUSER_MOTOR = "coffee_infuser_motor"          # bit 9
    STEAMER_PROBE_FAILURE = "steamer_probe_failure"        # bit 10
    EMPTY_DRIP_TRAY = "empty_drip_tray"                    # bit 11
    HYDRAULIC_CIRCUIT_PROBLEM = "hydraulic_circuit_problem"  # bit 12
    TANK_IS_IN_POSITION = "tank_is_in_position"            # bit 13
    CLEAN_KNOB = "clean_knob"                              # bit 14
    COFFEE_BEANS_EMPTY_TWO = "coffee_beans_empty_two"      # bit 15


_SWITCH_BIT_MAP: dict[int, MachineSwitch] = {
    0: MachineSwitch.WATER_SPOUT,
    1: MachineSwitch.MOTOR_UP,
    2: MachineSwitch.MOTOR_DOWN,
    3: MachineSwitch.COFFEE_WASTE_CONTAINER,
    4: MachineSwitch.WATER_TANK_ABSENT,
    5: MachineSwitch.KNOB,
    6: MachineSwitch.WATER_LEVEL_LOW,
    7: MachineSwitch.COFFEE_JUG,
    8: MachineSwitch.IFD_CARAFFE,
    9: MachineSwitch.CIOCCO_TANK,
    10: MachineSwitch.CLEAN_KNOB,
    # bits 11-12 unused
    13: MachineSwitch.DOOR_OPENED,
    14: MachineSwitch.PREGROUND_DOOR_OPENED,
}

_ALARM_BIT_MAP: dict[int, MachineAlarm] = {
    0: MachineAlarm.EMPTY_WATER_TANK,
    1: MachineAlarm.COFFEE_WASTE_CONTAINER_FULL,
    2: MachineAlarm.DESCALE_ALARM,
    3: MachineAlarm.REPLACE_WATER_FILTER,
    4: MachineAlarm.COFFEE_GROUND_TOO_FINE,
    5: MachineAlarm.COFFEE_BEANS_EMPTY,
    6: MachineAlarm.MACHINE_TO_SERVICE,
    7: MachineAlarm.COFFEE_HEATER_PROBE_FAILURE,
    8: MachineAlarm.TOO_MUCH_COFFEE,
    9: MachineAlarm.COFFEE_INFUSER_MOTOR,
    10: MachineAlarm.STEAMER_PROBE_FAILURE,
    11: MachineAlarm.EMPTY_DRIP_TRAY,
    12: MachineAlarm.HYDRAULIC_CIRCUIT_PROBLEM,
    13: MachineAlarm.TANK_IS_IN_POSITION,
    14: MachineAlarm.CLEAN_KNOB,
    15: MachineAlarm.COFFEE_BEANS_EMPTY_TWO,
}


def switch_from_bit(index: int) -> MachineSwitch:
    """Return machine switch for a bit index."""
    return _SWITCH_BIT_MAP.get(index, MachineSwitch.UNKNOWN_SWITCH)


def alarm_from_bit(index: int) -> MachineAlarm | None:
    """Return machine alarm for a bit index."""
    return _ALARM_BIT_MAP.get(index)


def parse_switches(data: bytes) -> List[MachineSwitch]:
    """Parse switch states from a MonitorV2 response.

    Switches are bytes[5-6] as u16 LE (NOT bytes[5]+[7] as before!).
    """
    if len(data) < 7:
        return []
    # FIXED: switches are u16 LE at byte[5] (low) + byte[6] (high)
    # Previously this incorrectly used data[5] | (data[7] << 8)
    mask = data[5] | (data[6] << 8)
    result: List[MachineSwitch] = []
    for bit in range(16):
        if mask & (1 << bit):
            sw = switch_from_bit(bit)
            if sw not in (
                MachineSwitch.IGNORE_SWITCH,
                MachineSwitch.WATER_SPOUT,
                MachineSwitch.UNKNOWN_SWITCH,
            ) and sw not in result:
                result.append(sw)
    return result


def parse_alarms(data: bytes) -> List[MachineAlarm]:
    """Parse alarm states from a MonitorV2 response.

    Alarms are bytes[7-8] as u16 LE.
    """
    if len(data) < 9:
        return []
    mask = data[7] | (data[8] << 8)
    result: List[MachineAlarm] = []
    for bit in range(16):
        if mask & (1 << bit):
            alarm = alarm_from_bit(bit)
            if alarm is not None and alarm not in result:
                result.append(alarm)
    return result


def get_alarm_mask(data: bytes) -> int:
    """Get raw alarm bitmask from MonitorV2 response."""
    if len(data) < 9:
        return 0
    return data[7] | (data[8] << 8)


__all__ = [
    "MachineSwitch", "MachineAlarm",
    "parse_switches", "parse_alarms", "get_alarm_mask",
    "switch_from_bit", "alarm_from_bit",
]
