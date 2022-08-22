# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Tuple, List, Dict

from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import RisingEdge, ReadWrite, ReadOnly, Event, Combine, Timer # type: ignore

from cocotb_bus.bus import Bus # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import *
from cocotb_TileLink.TileLink_common.Interfaces import SlaveUL, SlaveInterfaceUL, MasterInterfaceUL

class DutMultiMasterSlaveUL(SlaveUL):
    class SlaveInterfaceImpl(SlaveInterfaceUL):
        def __init__(self) -> None:
            SlaveInterfaceUL.__init__(self)
            self.a_ready: bool = False
            self.d_packet: TileLinkDPacket = TileLinkDPacket()
            self.d_valid: bool = False

        async def get_D_packet_and_valid(self) -> Tuple[TileLinkDPacket, bool]:
            await self.d_packet_and_valid_event.wait()
            return self.d_packet, self.d_valid

        async def get_A_ready(self) -> bool:
            await self.a_ready_event.wait()
            return self.a_ready

    _signals = [
        "a_valid", "a_ready", "a_opcode", "a_param", "a_size", "a_source", "a_address", "a_mask", "a_data",
        "d_valid", "d_ready", "d_opcode", "d_param", "d_size", "d_source", "d_sink", "d_data", "d_error"]

    def __init__(self, entity: SimHandleBase, clk_name: str ='clk', max_masters_count: int = 1):
        self.entity = entity
        self.clk_name = clk_name
        self.named_bus: Dict[str, Bus] = {}

        self.max_masters_count: int = max_masters_count
        self.masters: List[MasterInterfaceUL] = []
        self.masters_bus: Dict[MasterInterfaceUL, Bus] = {}

        self.master_name: Dict[MasterInterfaceUL, str] = {}
        self.name_master: Dict[str, MasterInterfaceUL] = {}

        self.named_slave: Dict[str, DutMultiMasterSlaveUL.SlaveInterfaceImpl] = {}

    def register_master(self, master: MasterInterfaceUL, bus_name: str = "") -> None:
        if len(self.masters) + 1 > self.max_masters_count:
            raise Exception("Too many masters for this slave")
        assert bus_name not in self.name_master, f"Two masters cannot use BUS named: {bus_name}"
        assert master not in self.master_name or self.master_name[master] == bus_name, \
            f"Master already registered to BUS {self.master_name[master]}"
        self.masters.append(master)
        self.master_name[master] = bus_name
        self.name_master[bus_name] = master

    def get_slave_interface(self, bus_name: str = "", **kwargs: Any) -> SlaveInterfaceUL:
        assert bus_name not in self.named_bus, f"Bus: {bus_name} already taken"
        self.named_bus[bus_name] = Bus(self.entity, bus_name, self._signals, **kwargs)
        self.named_slave[bus_name] = DutMultiMasterSlaveUL.SlaveInterfaceImpl()
        return self.named_slave[bus_name]

    async def process(self) -> None:
        rw = ReadWrite()
        ce = RisingEdge(getattr(self.entity, self.clk_name))
        for master, bus_name in self.master_name.items():
            self.masters_bus[master] = self.named_bus[bus_name]

        while True:
            modified = False

            # Reset events

            for slave_imp in self.named_slave.values():
                slave_imp.d_packet_and_valid_event.clear()
                slave_imp.a_ready_event.clear()

            await rw

            # A Packet routing: Master(s) ->(registered master interfaces)-> Dut

            for master in self.masters:
                a_packet, a_valid = await master.get_A_packet_and_valid()
                bus = self.masters_bus[master]

                if not bus.a_valid.value.is_resolvable or \
                    int(bus.a_valid.value) != int(a_valid):
                    modified = True
                bus.a_valid.setimmediatevalue(int(a_valid))
                for name in ('a_opcode', 'a_param', 'a_size', 'a_source', 'a_address', 'a_mask', 'a_data'):
                    if not getattr(bus, name).value.is_resolvable or \
                        int(getattr(bus, name).value) != int(getattr(a_packet, name)):
                        modified = True
                    getattr(bus, name).setimmediatevalue(getattr(a_packet, name))

            if modified:
                modified = False
                await rw

            # D Packet routing: DUT ->(handed out slave interfaces)-> Master(s)

            for bus_name, slave_imp in self.named_slave.items():
                bus = self.named_bus[bus_name]
                slave_imp.d_valid = bool(bus.d_valid.value)
                slave_imp.d_packet = TileLinkDPacket(
                    d_opcode=TileLinkULDOP(bus.d_opcode.value),
                    d_param=int(bus.d_param.value),
                    d_size=int(bus.d_size.value),
                    d_source=int(bus.d_source.value),
                    d_sink=int(bus.d_sink.value),
                    d_error=TileLinkULResp(int(bus.d_error.value)),
                    d_data=int(bus.d_data.value)
                )
                slave_imp.d_packet_and_valid_event.set()

            # D Ready routing: Master(s) ->(registered master interfaces)-> Dut

            for master in self.masters:
                bus = self.masters_bus[master]
                d_ready = await master.get_D_ready()
                if not bus.d_ready.value.is_resolvable or \
                    int(bus.d_ready.value) != int(d_ready):
                    modified = True
                bus.d_ready.setimmediatevalue(d_ready)
            if modified:
                modified = False
                await rw

            # A Ready routing: DUT ->(handed out slave interfaces)-> Master(s)

            for bus_name, slave in self.named_slave.items():
                bus = self.named_bus[bus_name]
                slave.a_ready = bool(bus.a_ready.value)
                slave.a_ready_event.set()
            await ce
