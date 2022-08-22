# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Tuple, List, Dict, TypeVar, Optional

from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import RisingEdge, ReadWrite, Event, Combine, ReadOnly # type: ignore

from cocotb_bus.bus import Bus # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import *
from cocotb_TileLink.TileLink_common.Interfaces import SlaveUL, SlaveInterfaceUL, MasterInterfaceUL, SimInterface, MemoryInterface

T = TypeVar('T')

class SimSimpleSlaveUL(SimInterface, SlaveUL, SlaveInterfaceUL, MemoryInterface):
    def __init__(self, bus_width: int = 32, sink_id: int = 0, size: int = 0x4000):
        SlaveInterfaceUL.__init__(self)
        self.max_number_of_masters = 1
        self.masters: List[MasterInterfaceUL] = []

        self.memory: Dict[int, int] = {}
        self.bus_width = bus_width
        self.bus_byte_width = bus_width//8
        self.size = size

        self.a_ready: bool = False

        self.d_packet: TileLinkDPacket = TileLinkDPacket()
        self.d_valid: bool = False
        self.sink_id: int = sink_id

    def init_memory(self, init_array: List[int], start_address: int) -> None:
        for i, data in enumerate(init_array):
            self.memory[start_address+i] = data

    def memory_dump(self) -> List[int]:
        ret = []
        for i in range(self.size):
            if i in self.memory:
                ret.append(self.memory[i])
            else:
                ret.append(0)
        return ret

    def register_master(self, master: MasterInterfaceUL, bus_name: str = "") -> None:
        if len(self.masters) + 1 > self.max_number_of_masters:
            raise Exception("Too many masters for this slave")
        self.masters.append(master)

    def get_slave_interface(self, bus_name: str = "", **kwargs: Any) -> SlaveInterfaceUL:
        return self

    def register_clock(self: T, clock: SimHandleBase) -> T:
        self.clock = clock
        return self

    def register_reset(self: T, reset: SimHandleBase, inverted: bool = False) -> T:
        self.reset = reset
        self.inverted = inverted
        return self

    def is_reset(self) -> bool:
        if not self.reset.value.is_resolvable:
            return True
        return bool(self.reset.value ^ self.inverted)

    async def get_D_packet_and_valid(self) -> Tuple[TileLinkDPacket, bool]:
        await self.d_packet_and_valid_event.wait()
        return self.d_packet, self.d_valid

    async def get_A_ready(self) -> bool:
        await self.a_ready_event.wait()
        return self.a_ready

    @staticmethod
    def _create_d_packet(opcode: TileLinkULDOP, param: int, size: int,
                         source: int, sink_id: int, return_value: int) -> TileLinkDPacket:
        return TileLinkDPacket(
            d_opcode=opcode, d_param=param, d_size=size, d_source=source,
            d_sink=sink_id, d_error=TileLinkULResp.Processed, d_data=return_value
        )


    async def do_reset(self) -> None:
        self.d_valid = False
        self.d_packet = TileLinkDPacket()
        self.d_packet_and_valid_event.set()

        self.a_ready = False
        self.a_ready_event.set()
        self.memory = {}

    async def process(self) -> None:
        rw = ReadWrite()
        ce = RisingEdge(self.clock)
        assert len(self.masters) == 1
        while True:
            self.d_packet_and_valid_event.clear()
            self.a_ready_event.clear()

            await rw
            if self.is_reset():
                await self.do_reset()
            else:
                a_packet, a_valid = await self.masters[0].get_A_packet_and_valid()
                self.a_ready = False

                if a_valid and not self.d_valid:
                    a_address = a_packet.a_address % self.size
                    a_size = a_packet.a_size
                    a_mask = a_packet.a_mask

                    check_address(a_address, self.bus_byte_width, a_size)

                    write = a_packet.a_opcode != TileLinkULAOP.Get
                    check_mask(a_address, self.bus_byte_width, a_mask, a_size, write)

                    self.a_ready = True
                    self.d_valid = True

                    _offset = a_address % self.bus_byte_width
                    return_value = 0
                    opcode = TileLinkULDOP.AccessAck
                    if write:
                        opcode = TileLinkULDOP.AccessAck
                        for i in range(2**a_size):
                            if a_mask & (2**(i+_offset)):
                                self.memory[a_address + i] = \
                                    (a_packet.a_data >> ((i+_offset)*8)) & 0xFF
                    else:
                        opcode = TileLinkULDOP.AccessAckData
                        for i in range(2**a_size):
                            if a_address + i not in self.memory.keys():
                                self.memory[a_address + i] = 0
                            return_value |= self.memory[a_address + i] << ((i+_offset)*8)

                    self.d_packet = SimSimpleSlaveUL._create_d_packet(opcode, a_packet.a_param, a_size,
                                                                      a_packet.a_source, self.sink_id, return_value)

                self.d_packet_and_valid_event.set()
                d_ready  = await self.masters[0].get_D_ready()
                if d_ready and self.d_valid:
                    self.d_valid = False
                    self.d_packet = TileLinkDPacket()
                self.a_ready_event.set()
            await ce
