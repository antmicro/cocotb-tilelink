# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

import enum
from collections import namedtuple
from typing import NamedTuple

class TileLinkULResp(enum.IntEnum):
    Processed = 0b0
    Denied = 0b1

class TileLinkULTimeout(Exception):
    pass

class TileLinkULWidthError(Exception):
    pass

class TileLinkULSizeError(Exception):
    pass

class TileLinkULAligmentError(Exception):
    pass

class TileLinkULMaskContinuousError(Exception):
    pass

class TileLinkULMaskSizeError(Exception):
    pass

class TileLinkULMaskError(Exception):
    pass

class TileLinkULProtocolError(Exception):
    def __init__(self, message: str, dresp: TileLinkULResp):
        super().__init__(message)
        self.dresp = dresp

class TileLinkULAOP(enum.IntEnum):
    PutFullData    = 0b0
    PutPartialData = 0b1
    Get            = 0b100

class TileLinkULDOP(enum.IntEnum):
    AccessAck     = 0b0
    AccessAckData = 0b1


class TileLinkAPacket(NamedTuple):
    a_opcode: TileLinkULAOP = TileLinkULAOP.Get
    a_param: int = 0
    a_size: int = 0
    a_source: int = 0
    a_address: int = 0
    a_mask: int = 0
    a_data: int = 0


class TileLinkDPacket(NamedTuple):
    d_opcode: TileLinkULDOP = TileLinkULDOP.AccessAckData
    d_param: int = 0
    d_size: int = 0
    d_source: int = 0
    d_sink: int = 0
    d_error: TileLinkULResp = TileLinkULResp.Processed
    d_data: int = 0


def check_address(address: int, dbus_byte_width: int, size: int) -> None:
    if 2**size > dbus_byte_width:
        raise TileLinkULWidthError(f"Packet size ({2**size} B) is larger than" \
                                   f" the bus width ({dbus_byte_width} B)")
    elif size < 0:
        raise TileLinkULSizeError(f"Packet size must be a positive power of 2, given {size}")
    elif address & ~(2**size - 1) != address:
        raise TileLinkULAligmentError(f"Address 0x{address:8x} must be aligned to packet size: {2**size}")

def check_mask(address: int, dbus_byte_width: int, byte_mask: int, size: int, write: bool) -> None:
    offset = address % dbus_byte_width
    if byte_mask != ((byte_mask >> offset) << offset):
        raise TileLinkULMaskError("High bit in incorrect position")
    if write:
        return
    byte_mask >>= offset
    count = 0
    while byte_mask:
        if byte_mask & 1:
            count +=1
        else:
            raise TileLinkULMaskContinuousError(
                f"Mask must be continuous, address 0x{address:8x},"
                f" write:{write}, size:{2**size}, mask:{bin(byte_mask)}")
        byte_mask >>= 1
    if count != 2**size:
        raise TileLinkULMaskSizeError("Number of HIGH bits in mask:{} is not equal size:{}".format(count, 2**size))


def get_write_opcode(size: int, dbus_byte_width: int, byte_mask: int) -> TileLinkULAOP:
    if 2**size == dbus_byte_width and byte_mask == (2**(2**size)) - 1:
        return TileLinkULAOP.PutFullData
    else:
        return TileLinkULAOP.PutPartialData
