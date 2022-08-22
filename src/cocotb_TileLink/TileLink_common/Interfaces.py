# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from abc import ABC
from typing import TypeVar, Any, Optional, Tuple, List

from cocotb.handle import SimHandle # type: ignore
from cocotb.triggers import Event # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import *

class ProcessInterface(ABC):
    async def process(self) -> None:
        raise Exception("Unimplemented")

T = TypeVar('T')

class SimInterface():
    def __init__(self) -> None:
        self.sim_finish_event: Event = Event()

    def register_reset(self: T, rst: SimHandle, inverted: bool) -> T:
        raise Exception("Unimplemented")

    def register_clk(self: T, clk: SimHandle) -> T:
        raise Exception("Unimplemented")

    def finish(self) -> None:
        raise Exception("Unimplemented")

    async def sim_finished(self) -> None:
        raise Exception("Unimplemented")


class MemoryInterface(ABC):
    def init_memory(self, init_array: List[int], start_address: int) -> None:
        raise Exception("Unimplemented")

    def memory_dump(self) -> List[int]:
        raise Exception("Unimplemented")


class MasterUL(ProcessInterface):
    def register_slave(self, slave: SlaveInterfaceUL, bus_name: str = "") -> None:
        raise Exception("Unimplemented")

    def get_master_interface(self, bus_name: str = "", **kwargs: Any) -> MasterInterfaceUL:
        raise Exception("Unimplemented")


class MasterInterfaceUL():
    def __init__(self) -> None:
        self.a_packet_and_valid_event: Event = Event()
        self.d_ready_event: Event = Event()

    async def get_A_packet_and_valid(self) -> Tuple[TileLinkAPacket, bool]:
        raise Exception("Unimplemented")

    async def get_D_ready(self) -> bool:
        raise Exception("Unimplemented")


class SlaveUL(ProcessInterface):
    def register_master(self, master: MasterInterfaceUL, bus_name: str = "") -> None:
        raise Exception("Unimplemented")

    def get_slave_interface(self, bus_name: str = "", **kwargs: Any) -> SlaveInterfaceUL:
        raise Exception("Unimplemented")


class SlaveInterfaceUL():
    def __init__(self) -> None:
        self.d_packet_and_valid_event: Event = Event()
        self.a_ready_event: Event = Event()

    async def get_D_packet_and_valid(self) -> Tuple[TileLinkDPacket, bool]:
        raise Exception("Unimplemented")

    async def get_A_ready(self) -> bool:
        raise Exception("Unimplemented")
