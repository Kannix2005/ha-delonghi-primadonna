"""Constants for the De'Longhi Primadonna integration."""
from homeassistant.const import EntityCategory

DOMAIN = 'delonghi_primadonna'

SERVICE = '00035b03-58e6-07dd-021a-08123a000300'

CONTROLL_CHARACTERISTIC = '00035b03-58e6-07dd-021a-08123a000301'

NAME_CHARACTERISTIC = '00002A00-0000-1000-8000-00805F9B34FB'

DESCRIPTOR = '00002902-0000-1000-8000-00805f9b34fb'

DEFAULT_IMAGE_URL = (
    'https://delonghibe.s3.eu-west-1.amazonaws.com/cms/prod/img/'
    '_opt_delonghi_uploads_PD_CLASS_TOP_INT_ECAM550.85.MS.png'
)

BEVERAGE_SERVICE_NAME = 'make_beverage'

# Mapping of profile id to profile name
AVAILABLE_PROFILES = {
    1: 'Profile 1',
    2: 'Profile 2',
    3: 'Profile 3',
    4: 'Guest',
}

POWER_OFF_OPTIONS = {
    '15min': 0,
    '30min': 1,
    '1h': 2,
    '2h': 3,
    '3h': 4
}

ENTITY_CATEGORY = {
    'None': None,
    'Configuration': EntityCategory.CONFIG,
    'Diagnostic': EntityCategory.DIAGNOSTIC,
}

NOZZLE_STATE = {
    -1: "unknown",
    0: "detached",              # EcamAccessory::None
    1: "steam",                 # EcamAccessory::Water (standard spout)
    2: "milk_frother",          # EcamAccessory::Milk
    3: "chocolate",             # EcamAccessory::Chocolate
    4: "milk_frother_cleaning", # EcamAccessory::MilkClean
}

# Skipable maintanence states
SERVICE_STATE = {0: 'OK', 4: 'DESCALING'}

# ── MonitorV2 (0x75) protocol definitions ─────────────────────────
# Source: DeLonghi Coffee Link APK v4.9.6 (MonitorDataV2.java)
#         + mmastrac/longshot (Rust ECAM CLI) for cross-reference
#
# Byte layout of MonitorV2 response payload (after D0 LEN 75 0F):
#   byte[4]     = EcamAccessory        (u8 enum)
#   byte[5-6]   = EcamMachineSwitch    (u16 LE bitmask)
#   byte[7-8]   = EcamMachineAlarm LOW (u16 LE, alarm bits 0-15)
#   byte[9]     = EcamMachineState     (u8 enum)
#   byte[10]    = progress             (u8, 0-100)
#   byte[11]    = percentage           (u8, 0-100)
#   byte[12-13] = EcamMachineAlarm HIGH (u16 LE, alarm bits 16-31)
#   byte[14-16] = unknown
#
# IMPORTANT: Alarms are 32-bit! The APK reads them as:
#   alarm_mask = byte[7] | (byte[8]<<8) | (byte[12]<<16) | (byte[13]<<24)
# Longshot only used 16-bit (bytes 7-8). The APK proves bytes 12-13 are
# the upper 16 bits of the alarm bitmask.

# Machine state from byte[9]
ECAM_MACHINE_STATE = {
    0: 'StandBy',
    1: 'TurningOn',
    2: 'ShuttingDown',
    4: 'Descaling',
    5: 'SteamPreparation',
    6: 'Recovery',
    7: 'ReadyOrDispensing',
    8: 'Rinsing',
    10: 'MilkPreparation',
    11: 'HotWaterDelivery',
    12: 'MilkCleaning',
    16: 'ChocolatePreparation',
}

# Alarm bitmask from bytes[7-8]+[12-13] (u32 LE, split across gap)
# Source: DeLonghi Coffee Link APK v4.9.6, EnumC8916l.java
ECAM_ALARM = {
    0: 'EmptyWaterTank',
    1: 'CoffeeWasteContainerFull',
    2: 'DescaleAlarm',
    3: 'ReplaceWaterFilter',
    4: 'CoffeeGroundTooFine',
    5: 'CoffeeBeansEmpty',
    6: 'MachineToService',
    7: 'CoffeeHeaterProbeFailure',
    8: 'TooMuchCoffee',
    9: 'CoffeeInfuserMotorNotWorking',
    10: 'SteamerProbeFailure',
    11: 'EmptyDripTray',
    12: 'HydraulicCircuitProblem',
    13: 'TankIsInPosition',
    14: 'CleanKnob',
    15: 'CoffeeBeansEmptyTwo',
    16: 'TankTooFull',
    17: 'BeanHopperAbsent',
    18: 'GridPresence',
    19: 'InfuserSense',
    20: 'NotEnoughCoffee',
    21: 'ExpansionCommProb',
    22: 'ExpansionSubmodulesProb',
    23: 'GrindingUnit1Problem',
    24: 'GrindingUnit2Problem',
    25: 'CondenseFanProblem',
    26: 'ClockBtCommProblem',
    27: 'SpiCommProblem',
}

# ── Beverage IDs (EnumC8905a) ──────────────────────────────────────
# Source: DeLonghi Coffee Link APK v4.9.6, 82 beverage definitions
ECAM_BEVERAGE_ID = {
    # Standard beverages
    1: 'Espresso', 2: 'Coffee', 3: 'Long', 4: 'Espresso2x',
    5: 'DoppioPlus', 6: 'Americano', 7: 'Cappuccino',
    8: 'LatteMacchiato', 9: 'CaffeLatte', 10: 'FlatWhite',
    11: 'EspressoMacchiato', 12: 'HotMilk', 13: 'CappuccinoDoppioPlus',
    14: 'ColdMilk', 15: 'CappuccinoReverse', 16: 'HotWater',
    17: 'Steam', 18: 'Ciocco',
    # Extended
    19: 'Ristretto', 20: 'LongEspresso', 21: 'CoffeeCream',
    22: 'Tea', 23: 'CoffeePot', 24: 'Cortado', 25: 'LongBlack',
    26: 'TravelMug', 27: 'BrewOverIce',
    # Iced beverages
    50: 'IceAmericano', 51: 'IceCappuccino', 52: 'IceLatteMacchiato',
    53: 'IceCappuccinoMix', 54: 'IceFlatWhite', 55: 'IceColdMilk',
    56: 'IceCaffeLatte', 57: 'OverIceEspresso',
    # Mug beverages
    80: 'MugAmericano', 81: 'MugCappuccino', 82: 'MugLatteMacchiato',
    83: 'MugCaffeLatte', 84: 'MugCappuccinoMix', 85: 'MugFlatWhite',
    86: 'MugHotMilk',
    # Mug+Ice beverages
    100: 'MugIceOverIce', 101: 'MugIceAmericano', 102: 'MugIceCappuccino',
    103: 'MugIceLatteMacchiato', 104: 'MugIceCaffeLatte',
    105: 'MugIceCappuccinoMix', 106: 'MugIceFlatWhite',
    107: 'MugIceColdMilk',
    # Cold brew
    120: 'ColdBrewCoffee', 121: 'ColdBrewEssence', 122: 'ColdBrewPot',
    123: 'ColdBrewLatte', 124: 'ColdBrewCappuccino',
    140: 'ColdBrewMug', 141: 'ColdBrewLatteMug',
    142: 'ColdBrewCappuccinoMug',
    # Bean systems
    200: 'Bean01', 201: 'Bean02', 202: 'Bean03',
    203: 'Bean04', 204: 'Bean05', 205: 'Bean06',
    # Custom recipes V2
    230: 'CustomV2_01', 231: 'CustomV2_02', 232: 'CustomV2_03',
    233: 'CustomV2_04', 234: 'CustomV2_05', 235: 'CustomV2_06',
    236: 'CustomV2_07', 237: 'CustomV2_08', 238: 'CustomV2_09',
    239: 'CustomV2_10',
}

# ── Recipe Parameters (EnumC8913i) ────────────────────────────────
# Source: DeLonghi Coffee Link APK v4.9.6, 35 parameters
ECAM_RECIPE_PARAM = {
    0: 'Temp', 1: 'Coffee', 2: 'Taste', 3: 'Granulometry',
    4: 'Blend', 5: 'InfusionSpeed', 6: 'Preinfusion', 7: 'Crema',
    8: 'DuePer', 9: 'Milk', 10: 'MilkTemp', 11: 'MilkFroth',
    12: 'Inversion', 13: 'TeaTemp', 14: 'TeaProfile', 15: 'HotWater',
    16: 'MixVelocity', 17: 'MixDuration', 18: 'DensityMultiBeverage',
    19: 'TempMultiBeverage', 20: 'DecalcType', 21: 'TempRinse',
    22: 'WaterRinse', 23: 'CleanType', 24: 'Programable',
    25: 'Visible', 26: 'VisibleInProgramming', 27: 'IndexLength',
    28: 'Accessory', 31: 'Iced', 32: 'MugSize', 33: 'MugAdjust',
    37: 'NumIceCubes', 38: 'Intensity', 39: 'Rinse',
}

# ── Taste / Strength Values (EnumC8907c) ──────────────────────────
ECAM_TASTE = {
    0: ('Preground', 0x00),
    1: ('ExtraMild', 0x10),
    2: ('Mild', 0x20),
    3: ('Normal', 0x30),
    4: ('Strong', 0x40),
    5: ('ExtraStrong', 0x50),
}

# ── Dispense Action (EnumC8923s) ──────────────────────────────────
ECAM_ACTION = {
    0: 'DontCare',
    1: 'Start',
    2: 'StartProgram',  # also StopV2
    3: 'CheckStart',
    4: 'Stop',
    5: 'StopProgram',
    6: 'SkipRinse',
    7: 'AdvancedMode',
}

# ── Beverage Action (EnumC8906b) ──────────────────────────────────
ECAM_BEVERAGE_ACTION = {
    0: 'DeleteBeverage',
    1: 'SaveBeverage',
    2: 'PrepareBeverage',
    3: 'PrepareAndSave',
    5: 'SaveInversion',
    6: 'PrepareInversion',
    7: 'PrepareSaveInversion',
}

# High-level sensor status values (matching longshot EcamStatus)
# Order follows longshot's EcamStatus::extract() priority:
#   TurningOn > ShuttingDown > Rinsing/Cleaning > Dispensing >
#   Descaling > Alarm > StandBy > Ready
MACHINE_STATUSES = [
    'STANDBY',
    'TURNING_ON',
    'SHUTTING_DOWN',
    'READY',
    'DISPENSING',
    'RINSING',
    'DESCALING',
    'ALARM',
]

"""
Command bytes
"""
BYTES_POWER = [0x0d, 0x07, 0x84, 0x0f, 0x02, 0x01, 0x55, 0x12]

# Default bitmask for commands
BASE_COMMAND = '10000001'

BYTES_TIME_COMMAND = [
    0x0d, 0x07, 0xE2, 0xF0, 0x00, 0x00, 0x00, 0x00
]

# This command change device switches
BYTES_SWITCH_COMMAND = [
    0x0d, 0x0b, 0x90, 0x0f, 0x00, 0x3f,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
]

BYTES_AUTOPOWEROFF_COMMAND = [
    0x0d, 0x0b, 0x90, 0x0f, 0x00, 0x3e,
    0x00, 0x00, 0x00, 0x00, 0x81, 0xe3
]

BYTES_WATER_HARDNESS_COMMAND = [
    0x0d, 0x0b, 0x90, 0x0f, 0x00, 0x32,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
]

BYTES_WATER_TEMPERATURE_COMMAND = [
    0x0d, 0x0b, 0x90, 0x0f, 0x00, 0x3d,
    0x00, 0x00, 0x00, 0x00, 0x6f, 0x31
]

# Commands that load user profiles from the device. They must be
# executed once after the first successful connection. The CRC
# bytes are zeros as they are calculated at runtime.
BYTES_LOAD_PROFILES = [0x0d, 0x07, 0xa4, 0xf0, 0x01, 0x06, 0x00, 0x00]
BYTES_LOAD_PROFILES_1 = [0x0d, 0x07, 0xa4, 0xf0, 0x01, 0x03, 0x00, 0x00]
BYTES_LOAD_PROFILES_2 = [0x0d, 0x07, 0xa4, 0xf0, 0x04, 0x06, 0x00, 0x00]

COFFE_ON = [0x0d, 0x0f, 0x83, 0xf0, 0x02, 0x01, 0x01,
            0x00, 0x67, 0x02, 0x02, 0x00, 0x00, 0x06, 0x77, 0xff]
COFFE_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x02, 0x02, 0x06, 0xc4, 0xb1]

DOPPIO_ON = [0x0d, 0x0d, 0x83, 0xf0, 0x05, 0x01, 0x01,
             0x00, 0x78, 0x00, 0x00, 0x06, 0xc4, 0x7e]
DOPPIO_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x05, 0x02, 0x06, 0x41, 0x21]

STEAM_ON = [0x0d, 0x0d, 0x83, 0xf0, 0x11, 0x01,
            0x09, 0x03, 0x84, 0x1c, 0x01, 0x06, 0xc0, 0x7b]
STEAM_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x11, 0x02, 0x06, 0xde, 0x82]

HOTWATER_ON = [0x0d, 0x0d, 0x83, 0xf0, 0x10, 0x01,
               0x0f, 0x00, 0xfa, 0x1c, 0x01, 0x06, 0x04, 0xb4]
HOTWATER_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x10, 0x02, 0x06, 0xe9, 0xb2]

ESPRESSO2_ON = [0x0d, 0x0f, 0x83, 0xf0, 0x04, 0x01, 0x01,
                0x00, 0x28, 0x02, 0x02, 0x00, 0x00, 0x06, 0xab, 0x53]
ESPRESSO2_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x04, 0x02, 0x06, 0x76, 0x11]

AMERICANO_ON = [0x0d, 0x12, 0x83, 0xf0, 0x06, 0x01, 0x01, 0x00,
                0x28, 0x02, 0x03, 0x0f, 0x00, 0x6e, 0x00, 0x00,
                0x06, 0x47, 0x8b]
AMERICANO_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x06, 0x02, 0x06, 0x18, 0x71]

LONG_ON = [0x0d, 0x0f, 0x83, 0xf0, 0x03, 0x01, 0x01,
           0x00, 0xa0, 0x02, 0x03, 0x00, 0x00, 0x06, 0x18, 0x7f]
LONG_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x03, 0x02, 0x06, 0xf3, 0x81]

# Espresso x1 (Aroma=3 Temperature=2 Qty=40)
ESPRESSO_ON = [0x0d, 0x11, 0x83, 0xf0, 0x01, 0x01, 0x01, 0x00,
               0x28, 0x02, 0x03, 0x08, 0x00, 0x00, 0x00, 0x06, 0x8f, 0xfc]
ESPRESSO_OFF = [0x0d, 0x08, 0x83, 0xf0, 0x01, 0x02, 0x06, 0x9d, 0xe1]

# This commands return the current device state
DEBUG = [0x0d, 0x05, 0x75, 0x0f, 0xda, 0x25]

"""
Status bytes
"""
WATER_TANK_DETACHED = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x15, 0x00, 0x00,
                       0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                       0xaa, 0x31]

WATER_SHORTAGE = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x45, 0x00, 0x01, 0x00,
                  0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2f, 0x64]

WATER_SHORTAGE2 = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x41, 0x00, 0x05, 0x00,
                   0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0f, 0x4e]

GRAINS_SHORTAGE = []

CRAINS_COVER_OPENED = []

COFFEE_GROUNDS_CONTAINER_FULL = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x05, 0x00,
                                 0x02, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00,
                                 0x00, 0x00, 0x00, 0x43, 0xd0]

# On some devices the grounds container clean notification includes an
# additional bit in the general notification field. Handle it as the same
# "GroundsContainerFull" status.
COFFEE_GROUNDS_CONTAINER_CLEAN = [
    0xd0, 0x12, 0x75, 0x0f, 0x01, 0x05, 0x00, 0x0a, 0x00, 0x07, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x09, 0xa0
]

COFFEE_GROUNDS_CONTAINER_DETACHED = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x0d, 0x00,
                                     0x00, 0x00, 0x07, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x86, 0xc9]

DEVICE_READY = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x05, 0x00, 0x00,
                0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x9d, 0x61]

DEVICE_TURNOFF = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x01, 0x00, 0x00,
                  0x00, 0x00, 0x03, 0x64, 0x00, 0x00, 0x00, 0x00,
                  0x00, 0xd6, 0x96]

START_COFFEE = [0xd0, 0x12, 0x75, 0x0f, 0x01, 0x05, 0x00, 0x00,
                0x00, 0x07, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x5c, 0xa7]
