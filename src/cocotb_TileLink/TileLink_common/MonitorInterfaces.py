# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from abc import ABC
from typing import TypeVar, Dict, Any, Optional

from cocotb.triggers import Event # type: ignore
from cocotb_TileLink.TileLink_common.TileLink_types import TileLinkAPacket, TileLinkDPacket, TileLinkULResp, TileLinkULAOP, TileLinkULDOP

T = TypeVar('T')

class TLMonitor():
    def __init__(self) -> None:
        self.a_packet: Optional[TileLinkAPacket] = TileLinkAPacket()
        self.a_handshake: bool = False
        self.d_packet: TileLinkDPacket = TileLinkDPacket()
        self.d_handshake: bool = False

class MonitorableInterface():
    def __init__(self) -> None:
        self.all_done_event: Event = Event()

    async def get_status(self) -> TLMonitor:
        raise Exception("Unimplemented")

class MonitorInterface(ABC):
    def register_device(self: T, device: MonitorableInterface) -> T:
        raise Exception("Unimplemented")

class Packet():
    def __init__(self) -> None:
        self._age: int = 0
        self.cmd: Dict[Any, Any] = {}
        self.rsp: Dict[Any, Any] = {}

    def age(self) -> None:
        self._age +=1

    def add_cmd(self, packet: TileLinkAPacket) -> None:
        self.cmd['a_opcode']  = TileLinkULAOP(packet.a_opcode)
        self.cmd['a_param']   = int(packet.a_param)
        self.cmd['a_size']    = int(packet.a_size)
        self.cmd['a_source']  = int(packet.a_source)
        self.cmd['a_address'] = int(packet.a_address)
        self.cmd['a_mask']    = int(packet.a_mask)
        self.cmd['a_data']    = int(packet.a_data)

    def add_rsp(self, packet: TileLinkDPacket) -> None:
        self.rsp['d_opcode'] = TileLinkULDOP(packet.d_opcode)
        self.rsp['d_param']  = int(packet.d_param)
        self.rsp['d_size']   = int(packet.d_size)
        self.rsp['d_source'] = int(packet.d_source)
        self.rsp['d_sink']   = int(packet.d_sink)
        self.rsp['d_data']   = int(packet.d_data)
        self.rsp['d_error']  = TileLinkULResp(packet.d_error)

    def __str__(self) -> str:
        _cmd = "Command:\n\t"
        for key, value in self.cmd.items():
            _cmd += " " + key.capitalize() + ": "
            if type(value) is not int:
                _cmd += str(value) + ";"
            else:
                _cmd += str(hex(value)) + ";"
        _resp = "Response:\n\t"
        for key, value in self.rsp.items():
            _resp += " " + key.capitalize() + ": "
            if type(value) is not int:
                _resp += str(value) + ";"
            else:
                _resp += str(hex(value)) + ";"
        return _cmd + "\n" + _resp + "\n" + f"Took {self._age} cycles"

