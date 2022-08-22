# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from random import randint
from typing import Optional, TypeVar, Any, Tuple, List, Set

from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import ReadWrite, RisingEdge, Event # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import *
from cocotb_TileLink.TileLink_common.Interfaces import SimInterface, MasterInterfaceUL, MasterUL, SlaveInterfaceUL
from cocotb_TileLink.TileLink_common.MonitorInterfaces import MonitorableInterface, TLMonitor

T = TypeVar('T')

class SimRandomTrafficGeneratorUL(MasterUL, MasterInterfaceUL, SimInterface, MonitorableInterface):
    def __init__(self, num_of_transactions: int = 100, bus_width: int = 32, addr_width: int = 32, name: str = "") -> None:
        MonitorableInterface.__init__(self)
        MasterInterfaceUL.__init__(self)
        SimInterface.__init__(self)

        self.name = name
        self.max_slave_count = 1
        self.slaves: List[SlaveInterfaceUL] = []
        self.bus_width = bus_width
        self.addr_width = addr_width

        self.num_of_transactions_send = num_of_transactions
        self.num_of_transactions_recv = num_of_transactions

        self.a_packet: TileLinkAPacket = TileLinkAPacket()
        self.a_valid: bool = False
        self.sending_a: bool = False
        self.was_a_handshake: bool = False

        self.d_packet: TileLinkDPacket = TileLinkDPacket()
        self.d_ready: bool = False
        self.was_d_handshake: bool = False

        self.wait_for: int = 0
        self.master_in_use: Set[int] = set()

    def register_slave(self, slave: SlaveInterfaceUL, bus_name: str = "") -> None:
        if len(self.slaves) + 1 > self.max_slave_count:
            raise Exception("Too many slaves")
        self.slaves.append(slave)

    def get_master_interface(self, bus_name: str = "", **kwargs: Any) -> MasterInterfaceUL:
        return self

    def register_clock(self: T, clock: SimHandleBase) -> T:
        self.clock = clock
        return self

    def register_reset(self: T, reset: SimHandleBase, inverted: bool = False) -> T:
        self.reset = reset
        self.inverted = inverted
        return self

    def finish(self) -> None:
        self.sim_finish_event.set()

    async def sim_finished(self) -> None:
        await self.sim_finish_event.wait()
        return

    async def get_A_packet_and_valid(self) -> Tuple[TileLinkAPacket, bool]:
        await self.a_packet_and_valid_event.wait()
        return self.a_packet, self.a_valid

    async def get_D_ready(self) -> bool:
        await self.d_ready_event.wait()
        return self.d_ready

    def is_reset(self) -> bool:
        if not self.reset.value.is_resolvable:
            return True
        return bool(self.reset.value ^ self.inverted)

    async def get_status(self) -> TLMonitor:
        await self.all_done_event.wait()
        self.all_done_event.clear()
        ret = TLMonitor();
        ret.a_handshake = self.was_a_handshake
        ret.a_packet = self.a_packet
        ret.d_handshake = self.was_d_handshake
        ret.d_packet = self.d_packet
        return ret

    def _get_random_A_packet(self) -> TileLinkAPacket:
        op = randint(0,2) # 0 - read, 1 - write
        bus_byte_width = self.bus_width//8
        log_bus_byte_width = bus_byte_width.bit_length() - 1

        size = 0
        mask = 0
        data = randint(0, 2**self.bus_width - 1)
        address = randint(0, 2**self.bus_width - 1)
        source = randint(0, 15)

        correct_address = randint(0,1)
        correct_size = randint(0,1)
        correct_mask = randint(0,1)

        if op == 0:
            opcode = TileLinkULAOP.Get
        elif op == 1:
            opcode = TileLinkULAOP.PutPartialData
        else:
            opcode = TileLinkULAOP.PutFullData

        if correct_mask or correct_size:
            size = randint(0, log_bus_byte_width)
        else:
            size = randint(0, 2**(log_bus_byte_width.bit_length()) - 1)

        if correct_mask or correct_address:
            address = address & ~(2**size - 1)

        if correct_mask:
            if op == 2:
                mask = 2**bus_byte_width - 1
            elif op == 1:
                mask = randint(0, 2**bus_byte_width - 1)
            else:
                mask = (2**(2**size) - 1) << (address & (bus_byte_width-1 >> size))
        else:
            mask = randint(0, 2**bus_byte_width - 1)
        assert mask.bit_length() <= 4, f"{correct_mask=}, {op=}"


        return TileLinkAPacket(
                    a_opcode=opcode, a_size=size,
                    a_source=source, a_address=address,
                    a_mask=mask, a_data=data)

    def _A_packet_prep(self) -> None:
        if not self.sending_a or randint(0,99) in range(75, 100):
            self.a_packet = self._get_random_A_packet()
            self.sending_a = True
        if self.sending_a:
            self.a_valid = bool(randint(0,1))
            if self.a_packet.a_source in self.master_in_use or self.num_of_transactions_send <= 0:
                self.a_valid = False

    def _A_packet_process(self, a_ready: bool) -> None:
        self.was_a_handshake = False
        if self.a_valid and a_ready:
            self.was_a_handshake = True
            self.master_in_use.add(self.a_packet.a_source)
            self.num_of_transactions_send -= 1
            self.sending_a = False

    async def do_reset(self) -> None:
        self.sending_a = False

        self.was_a_handhake = False
        self.a_valid = False
        self.a_packet = TileLinkAPacket()
        self.a_packet_and_valid_event.set()

        self.was_d_handhake = False
        self.d_ready = False
        self.d_ready_event.set()

    async def process(self) -> None:
        ce = RisingEdge(self.clock)
        rw = ReadWrite()
        while self.num_of_transactions_recv > 0:
            self.a_packet_and_valid_event.clear()
            self.d_ready_event.clear()

            await rw
            if self.is_reset():
                await self.do_reset()
            else:
                self._A_packet_prep()
                self.a_packet_and_valid_event.set()

                d_packet, d_valid = await self.slaves[0].get_D_packet_and_valid()

                self.was_d_handshake = False
                self.d_ready = False
                if d_valid and self.wait_for <= 0:
                    self.d_ready = True
                    self.wait_for = randint(0,20)
                    self.num_of_transactions_recv -= 1
                    self.was_d_handshake = True
                    self.d_packet = d_packet
                self.wait_for -= 1
                self.d_ready_event.set()

                a_ready = await self.slaves[0].get_A_ready()
                self._A_packet_process(a_ready)

                if self.was_d_handshake:
                    self.master_in_use.remove(d_packet.d_source)

            self.all_done_event.set()
            await ce

        self.a_valid = False
        self.sim_finish_event.set()
        while True:
            await self.do_reset()
            await ce
