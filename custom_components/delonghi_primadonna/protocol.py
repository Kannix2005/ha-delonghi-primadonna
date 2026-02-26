"""ECAM V2 BLE protocol — dynamic command builder.

Reverse-engineered from the DeLonghi Coffee Link APK v4.9.6.
Replaces the hardcoded ON/OFF byte arrays with a generic builder
that can produce commands for *any* beverage with arbitrary recipe
parameters, profile selection and operation type.
"""

from __future__ import annotations

from binascii import crc_hqx

# Parameter IDs that use 2-byte (big-endian) values (mL quantities).
TWO_BYTE_PARAMS: set[int] = {1, 9, 15}  # COFFEE, MILK, HOT_WATER

# Only parameters passing this filter are included in the BLE packet.
# Derived from EcamProtocolProcessorV2.m32103E0().
ALLOWED_PARAM_IDS: set[int] = set(range(0, 23)) | {27, 28, 31, 33, 38, 39}

# DUExPER (id=8) is always stripped by the APK before sending.
EXCLUDED_PARAM_IDS: set[int] = {8}


# ── Action types (EnumC8923s) ────────────────────────────────────
ACTION_START = 1
ACTION_STOP_V2 = 2

# ── Operation types (EnumC8906b) ─────────────────────────────────
OP_DELETE = 0
OP_SAVE = 1
OP_PREPARE = 2
OP_PREPARE_AND_SAVE = 3
OP_SAVE_INVERSION = 5
OP_PREPARE_INVERSION = 6
OP_PREPARE_SAVE_INVERSION = 7


def build_beverage_command(
    beverage_id: int,
    action: int = ACTION_START,
    parameters: list[tuple[int, int]] | None = None,
    profile_id: int = 1,
    operation: int = OP_PREPARE,
    bool_flag: bool = False,
    two_byte_params: set[int] | None = None,
) -> list[int]:
    """Build a V2 (0x83) beverage command packet.

    Args:
        beverage_id: ECAM beverage id (1=Espresso, 2=Coffee …).
        action: 1=START, 2=STOP_V2.
        parameters: [(param_id, value), …] — order is preserved.
        profile_id: Active user profile (1-based).
        operation: 2=PREPARE, 1=SAVE, 3=PREPARE_AND_SAVE.
        bool_flag: If True, ORs action byte with 0x80 (rinse flag).
        two_byte_params: Override for 2-byte param IDs.

    Returns:
        Command packet as ``list[int]`` including CRC placeholder bytes
        (will be filled by ``send_command``).
    """
    if two_byte_params is None:
        two_byte_params = TWO_BYTE_PARAMS

    # ── Filter parameters ────────────────────────────────────────
    filtered: list[tuple[int, int]] = []
    if parameters:
        for pid, val in parameters:
            if pid in EXCLUDED_PARAM_IDS:
                continue
            if pid not in ALLOWED_PARAM_IDS:
                continue
            # Bean system (id 200) excludes TASTE unless bool_flag
            if not bool_flag and beverage_id == 200 and pid == 2:
                continue
            filtered.append((pid, val))

    # ── Calculate sizes ──────────────────────────────────────────
    param_len = sum(
        3 if pid in two_byte_params else 2 for pid, _ in filtered
    )
    total = param_len + 9  # header(1)+len(1)+cmd(1)+sub(1)+bev(1)+act(1)
    #                        + params + prof_op(1) + crc(2)

    pkt = bytearray(total)
    pkt[0] = 0x0D
    pkt[1] = param_len + 8  # everything after byte[0]
    pkt[2] = 0x83
    pkt[3] = 0xF0
    pkt[4] = beverage_id & 0xFF
    pkt[5] = (action | 0x80) if bool_flag else action

    # ── Encode TLV parameters ───────────────────────────────────
    idx = 6
    for pid, val in filtered:
        pkt[idx] = pid & 0xFF
        if pid in two_byte_params:
            pkt[idx + 1] = (val >> 8) & 0xFF
            pkt[idx + 2] = val & 0xFF
            idx += 3
        else:
            pkt[idx + 1] = val & 0xFF
            idx += 2

    # ── Profile + operation byte ─────────────────────────────────
    pkt[idx] = ((profile_id & 0x3F) << 2) | (operation & 0x03)

    # CRC placeholders — ``send_command()`` calculates real CRC.
    # We still fill them here so callers that need a finished packet
    # (e.g. tests) get correct bytes.
    crc = crc_hqx(bytes(pkt[:-2]), 0x1D0F)
    pkt[-2] = (crc >> 8) & 0xFF
    pkt[-1] = crc & 0xFF

    return list(pkt)


def build_stop_command(
    beverage_id: int,
    profile_id: int = 1,
    operation: int = OP_PREPARE,
) -> list[int]:
    """Build a STOP command (no parameters, action=STOP_V2)."""
    return build_beverage_command(
        beverage_id=beverage_id,
        action=ACTION_STOP_V2,
        parameters=[],
        profile_id=profile_id,
        operation=operation,
    )


def build_read_profile_recipe(
    profile_id: int,
    beverage_id: int,
) -> list[int]:
    """Build a 0xA6 request to read a profile's recipe for a beverage.

    The machine answers with the stored TLV parameters for that
    profile + beverage combination.
    """
    # [0x0D, 0x07, 0xA6, 0xF0, profileId, beverageId, CRC_HI, CRC_LO]
    pkt = bytearray(8)
    pkt[0] = 0x0D
    pkt[1] = 0x07
    pkt[2] = 0xA6
    pkt[3] = 0xF0
    pkt[4] = profile_id & 0xFF
    pkt[5] = beverage_id & 0xFF
    crc = crc_hqx(bytes(pkt[:-2]), 0x1D0F)
    pkt[-2] = (crc >> 8) & 0xFF
    pkt[-1] = crc & 0xFF
    return list(pkt)


def parse_profile_recipe_response(
    data: bytes | bytearray,
) -> tuple[int, int, list[tuple[int, int]]] | None:
    """Parse a 0xA6 profile recipe response.

    Returns:
        ``(profile_id, beverage_id, [(param_id, value), …])``
        or ``None`` if the packet is not a valid 0xA6 response.
    """
    if len(data) < 8 or data[0] != 0xD0 or data[2] != 0xA6:
        return None

    profile_id = data[4]
    beverage_id = data[5]
    params: list[tuple[int, int]] = []

    idx = 6
    end = len(data) - 2  # last 2 bytes are CRC
    while idx < end:
        pid = data[idx]
        if pid in TWO_BYTE_PARAMS:
            if idx + 2 >= end:
                break
            val = (data[idx + 1] << 8) | data[idx + 2]
            idx += 3
        else:
            if idx + 1 >= end:
                break
            val = data[idx + 1]
            idx += 2
        params.append((pid, val))

    return (profile_id, beverage_id, params)
