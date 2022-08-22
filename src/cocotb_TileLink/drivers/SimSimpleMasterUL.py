# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from random import choice
from typing import List, Tuple, Dict, Union, Set, Optional, TypeVar, Any

from cocotb.log import SimLog # type: ignore
from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import ReadWrite, RisingEdge, Event, ReadOnly # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import*
from cocotb_TileLink.TileLink_common.Interfaces import SimInterface, MasterUL, MasterInterfaceUL, SlaveInterfaceUL
from cocotb_TileLink.TileLink_common.MonitorInterfaces import MonitorableInterface, TLMonitor

T = TypeVar('T')

class SimSimpleMasterUL(SimInterface, MasterUL, MasterInterfaceUL, MonitorableInterface):
    def __init__(self, bus_width: int = 32, name: str = "SimSimpleMasterUL",
                 expect_read_error: bool = False, expect_write_error: bool = False):
        MonitorableInterface.__init__(self)
        MasterInterfaceUL.__init__(self)
        SimInterface.__init__(self)

        self.max_slave_count = 1
        self.slaves: List[SlaveInterfaceUL] = []
        self.log: SimLog = SimLog(f"cocotb.{name}")
        self.bus_byte_width = bus_width//8

        self.a_packet_queue: Dict[int, List[TileLinkAPacket]] = {}
        self.a_packet_queue_send: Dict[int, List[TileLinkAPacket]] = {}
        self.a_packet_sources: Set[int] = set()

        self.a_packet: Optional[TileLinkAPacket] = TileLinkAPacket()
        self.a_valid: bool = False
        self.sending_a: bool = False
        self.was_a_handshake: bool = False

        self.d_packets: Dict[int, List[TileLinkDPacket]] = {}
        self.d_packet: TileLinkDPacket = TileLinkDPacket()
        self.d_ready: bool = False
        self.was_d_handshake: bool = False

        self.expect_read_error = expect_read_error
        self.expect_write_error = expect_write_error

        self.finished: bool = False

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
        assert self.a_packet is not None
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

    def _get_random_A_packet(self) -> Optional[TileLinkAPacket]:
        if len(self.a_packet_queue.keys()) == 0:
            return None
        self.a_valid = False
        source = choice(list(self.a_packet_queue.keys()))
        queue = self.a_packet_queue.pop(source)
        packet = queue[0]
        queue = queue[1:]
        self.a_packet_queue_send[source] = queue
        return packet

    def _A_packet_prep(self) -> None:
        if not self.sending_a:
            self.a_packet = self._get_random_A_packet()
            self.a_valid = True
            self.sending_a = True
        if self.a_packet is None:
            self.a_packet = TileLinkAPacket()
            self.a_valid = False
            self.sending_a = False

    def _A_packet_process(self, a_ready: bool) -> None:
        self.was_a_handshake = False
        if a_ready and self.a_valid:
            self.was_a_handshake = True
            self.sending_a = False
            self.a_valid = False

    def _inner_D_packet_process(self, d_packet: TileLinkDPacket) -> None:
        self.d_packet = d_packet
        source = int(d_packet.d_source)
        read = d_packet.d_opcode == TileLinkULDOP.AccessAckData
        if d_packet.d_error:
            if read and not self.expect_read_error or \
               not(read or self.expect_write_error):
                self.log.warning("Received error respons in d_packet")
        self.d_packets[source].append(d_packet)
        queue = self.a_packet_queue_send.pop(source)
        if len(queue) > 0:
            self.a_packet_queue[source] = queue
            return
        self.a_packet_sources.remove(source)

    def _D_packet_process(self, d_packet: TileLinkDPacket, d_valid: bool) -> None:
        self.was_d_handshake = False
        self.d_ready = False
        if d_valid:
            self.d_ready = True
            self._inner_D_packet_process(d_packet)
            self.was_d_handshake = True

    async def do_reset(self) -> None:
        self.sending_a = False

        self.was_a_handhake = False
        self.a_valid = False
        self.a_packet = TileLinkAPacket()
        self.a_packet_and_valid_event.set()

        self.was_d_handhake = False
        self.d_ready = False
        self.d_ready_event.set()

        self.a_packet_queue.clear()
        self.a_packet_sources.clear()
        self.d_packets.clear()

    async def process(self) -> None:
        ce = RisingEdge(self.clock)
        rw = ReadWrite()
        while True:
            self.a_packet_and_valid_event.clear()
            self.d_ready_event.clear()
            await rw
            if self.is_reset():
                await self.do_reset()
            else:
                self._A_packet_prep()
                self.a_packet_and_valid_event.set()

                d_packet, d_valid = await self.slaves[0].get_D_packet_and_valid()
                self._D_packet_process(d_packet, d_valid)
                self.d_ready_event.set()

                a_ready = await self.slaves[0].get_A_ready()
                self._A_packet_process(a_ready)

            self.all_done_event.set()
            await ce

    async def source_free(self, source: int) -> None:
        if source not in self.a_packet_sources:
            return
        re = RisingEdge(self.clock)
        while source in self.a_packet_sources:
            await re

    def write(self, address: int, length: int, value: List[int],
              byte_mask: List[bool], source: int = 0) -> None:
        assert source not in self.a_packet_sources, "Sending multiple outstanding messages from same source is forbiden"
        assert length == len(value) and length == len(byte_mask)
        cmds = []
        end_address = address + length
        for i in range((self.bus_byte_width).bit_length() - 1):
            if (address & 2**i) and len(value) != 0:
                _mask = 0
                _value = 0
                _offset = address % (self.bus_byte_width)
                for j in range(0, 2**i):
                    if len(value) != 0:
                        _mask |= byte_mask[0] << _offset + j
                        _value |= value[0] << ((_offset + j) * 8)
                        byte_mask = byte_mask[1:]
                        value = value[1:]
                cmds.append(TileLinkAPacket(
                    a_opcode=TileLinkULAOP.PutPartialData, a_param=0, a_size=i,
                    a_source=source, a_address=address, a_mask=_mask, a_data=_value))
                address += 2**i
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        while len(value) >= (self.bus_byte_width):
            _mask = 0
            _value = 0
            _size = (self.bus_byte_width).bit_length() - 1
            for j in range(0, (self.bus_byte_width)):
                _mask |= byte_mask[0] << j
                _value |= value[0] << (j * 8)
                byte_mask = byte_mask[1:]
                value = value[1:]
            _opcode = get_write_opcode(_size, self.bus_byte_width, _mask)
            cmds.append(TileLinkAPacket(
                a_opcode=_opcode, a_param=0, a_size=_size, a_source=source,
                a_address=address, a_mask=_mask, a_data=_value))
            address += (self.bus_byte_width)
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        for i in range((self.bus_byte_width).bit_length()-1, -1 , -1):
            if len(value) & 2**i:
                _mask = 0
                _value = 0
                _offset = address % (self.bus_byte_width)
                for j in range(0, 2**i):
                    _mask |= byte_mask[0] << _offset + j
                    _value |= value[0] << ((_offset + j) * 8)
                    byte_mask = byte_mask[1:]
                    value = value[1:]
                cmds.append(TileLinkAPacket(
                    a_opcode=TileLinkULAOP.PutPartialData, a_param=0, a_size=i,
                    a_source=source, a_address=address, a_mask=_mask, a_data=_value))
                address += 2**i
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        assert False

    def read(self, address: int, length: int, source: int = 0) -> None:
        assert source not in self.a_packet_sources, "Sending multiple outstanding messages from same source is forbiden"
        cmds = []
        end_address = address + length
        for i in range((self.bus_byte_width).bit_length() - 1):
            if (address & 2**i) and address + 2**i <= end_address:
                _mask = 2**(2**i) - 1
                _offset = address % (self.bus_byte_width)
                _mask <<= _offset
                cmds.append(TileLinkAPacket(
                    a_opcode=TileLinkULAOP.Get, a_param=0, a_size=i,
                    a_source=source, a_address=address, a_mask=_mask))
                address += 2**i
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        while address+self.bus_byte_width <= end_address:
            _mask = 2**(self.bus_byte_width) - 1
            _size = (self.bus_byte_width).bit_length() - 1
            cmds.append(TileLinkAPacket(
                a_opcode=TileLinkULAOP.Get, a_param=0, a_size=_size,
                a_source=source, a_address=address, a_mask=_mask))
            address += (self.bus_byte_width)
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        for i in range((self.bus_byte_width).bit_length()-1, -1, -1):
            if address + 2**i <= end_address:
                _mask = 2**(2**i) - 1
                _offset = address % (self.bus_byte_width)
                _mask <<= _offset
                cmds.append(TileLinkAPacket(
                    a_opcode=TileLinkULAOP.Get, a_param=0, a_size=i,
                    a_source=source, a_address=address, a_mask=_mask))
                address += 2**i
        if address >= end_address:
            self.d_packets[source] = []
            self.a_packet_sources.add(source)
            self.a_packet_queue[source] = cmds
            assert len(cmds)>0
            return
        assert False

    def get_rsp(self, source: int) -> List[TileLinkDPacket]:
        rsp = self.d_packets.pop(source)
        return rsp
