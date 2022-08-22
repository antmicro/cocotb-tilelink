# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Set, TypeVar, Dict

from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import RisingEdge, ReadOnly # type: ignore
from cocotb.log import SimLog # type: ignore

from cocotb_TileLink.TileLink_common.Interfaces import SimInterface, ProcessInterface
from cocotb_TileLink.TileLink_common.MonitorInterfaces import MonitorInterface, MonitorableInterface, Packet


T = TypeVar('T')

class TileLinkULMonitor(MonitorInterface, SimInterface, ProcessInterface):
    def __init__(self, name: str ="TLULMonitor"):
        self.log: SimLog = SimLog(f"cocotb.{name}")
        self.waiting_for_resp: Dict[int, Packet] = {}

    def register_device(self: T, device: MonitorableInterface) -> T:
        self.device = device
        return self

    def register_clock(self: T, clock: SimHandleBase) -> T:
        self.clock = clock
        return self

    def register_reset(self: T, reset: SimHandleBase, inverted: bool = False) -> T:
        self.reset = reset
        self.inverted = inverted
        return self

    def is_reset(self) -> bool:
        return bool(self.reset.value ^ self.inverted)

    async def process(self) -> None:
        ce = RisingEdge(self.clock)
        ro = ReadOnly()
        while True:
            await ro
            status = await self.device.get_status()
            if not self.is_reset():
                if status.a_handshake:
                    assert status.a_packet is not None
                    assert int(status.a_packet.a_source) not in self.waiting_for_resp or \
                        (status.d_handshake and status.d_packet.d_source == status.a_packet.a_source), \
                        f"Source {status.a_packet.a_source} already used for other transaction\n"
                    if int(status.a_packet.a_source) in self.waiting_for_resp:
                        packet = self.waiting_for_resp.pop(int(status.a_packet.a_source))
                        packet.add_rsp(status.d_packet)
                        self.log.info(packet)
                        status.d_handshake = False
                    packet = Packet()
                    packet.add_cmd(status.a_packet)
                    self.waiting_for_resp[status.a_packet.a_source] = packet
                if status.d_handshake:
                    assert int(status.d_packet.d_source) in self.waiting_for_resp, \
                        f"D packet to no active source {int(status.d_packet.d_source)}\n"
                    packet = self.waiting_for_resp.pop(int(status.d_packet.d_source))
                    packet.add_rsp(status.d_packet)
                    self.log.info(packet)
            for _, packet in self.waiting_for_resp.items():
                packet.age()
            await ce
