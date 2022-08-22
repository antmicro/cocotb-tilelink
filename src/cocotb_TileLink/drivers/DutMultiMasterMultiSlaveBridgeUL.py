# Copyright (c) 2022, Antmicro
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Tuple, List, Dict

from cocotb.handle import SimHandleBase # type: ignore
from cocotb.triggers import RisingEdge, ReadWrite, ReadOnly, Event, Combine, Timer # type: ignore

from cocotb_bus.bus import Bus # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import *
from cocotb_TileLink.TileLink_common.Interfaces import MasterUL, SlaveUL, SlaveInterfaceUL, MasterInterfaceUL
from cocotb_TileLink.TileLink_common.MonitorInterfaces import MonitorableInterface, TLMonitor

class DutMultiMasterMultiSlaveBridgeUL(MasterUL, SlaveUL):
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

    class MasterInterfaceImpl(MasterInterfaceUL):
        def __init__(self) -> None:
            MasterInterfaceUL.__init__(self)
            self.d_ready: bool = False
            self.a_packet: TileLinkAPacket = TileLinkAPacket()
            self.a_valid: bool = False

        async def get_A_packet_and_valid(self) -> Tuple[TileLinkAPacket, bool]:
            await self.a_packet_and_valid_event.wait()
            return self.a_packet, self.a_valid

        async def get_D_ready(self) -> bool:
            await self.d_ready_event.wait()
            return self.d_ready

    class MasterMonitorableImpl(MonitorableInterface):
        def __init__(self) -> None:
            MonitorableInterface.__init__(self)
            self.a_packet: TileLinkAPacket = TileLinkAPacket()
            self.a_handshake: bool = False
            self.d_packet: TileLinkDPacket = TileLinkDPacket()
            self.d_handshake: bool = False

        async def get_status(self) -> TLMonitor:
            await self.all_done_event.wait()
            self.all_done_event.clear()
            ret = TLMonitor()
            ret.a_packet = self.a_packet
            ret.a_handshake = self.a_handshake
            ret.d_packet = self.d_packet
            ret.d_handshake = self.d_handshake
            return ret


    _signals = [
        "a_valid", "a_ready", "a_opcode", "a_param", "a_size", "a_source", "a_address", "a_mask", "a_data",
        "d_valid", "d_ready", "d_opcode", "d_param", "d_size", "d_source", "d_sink", "d_data", "d_error"]

    def __init__(self, entity: SimHandleBase, clk_name: str ='clk', max_masters_count: int = 1, max_slaves_count: int = 1):
        self.entity = entity
        self.clk_name = clk_name
        self.named_bus: Dict[str, Bus] = {}

        self.max_masters_count: int = max_masters_count
        self.masters: List[MasterInterfaceUL] = []
        self.masters_bus: Dict[MasterInterfaceUL, Bus] = {}

        self.master_name: Dict[MasterInterfaceUL, str] = {}
        self.name_master: Dict[str, MasterInterfaceUL] = {}

        self.named_slave: Dict[str, DutMultiMasterMultiSlaveBridgeUL.SlaveInterfaceImpl] = {}

        self.max_slaves_count: int = max_slaves_count
        self.slaves: List[SlaveInterfaceUL] = []
        self.slaves_bus: Dict[SlaveInterfaceUL, Bus] = {}

        self.slave_name: Dict[SlaveInterfaceUL, str] = {}
        self.name_slave: Dict[str, SlaveInterfaceUL] = {}

        self.named_master: Dict[str, DutMultiMasterMultiSlaveBridgeUL.MasterInterfaceImpl] = {}

        self.master_monitorable: Dict[MasterInterfaceUL,
                                      DutMultiMasterMultiSlaveBridgeUL.MasterMonitorableImpl] = {}

    def register_slave(self, slave: SlaveInterfaceUL, bus_name: str = "") -> None:
        if len(self.slaves) + 1 > self.max_slaves_count:
            raise Exception("Too many slaves for this master")
        assert bus_name not in self.name_slave, f"Two slaves cannot use BUS named: {bus_name}"
        assert bus_name not in self.name_master, f"Slave and master cannot use BUS named: {bus_name}"
        assert slave not in self.slave_name or self.slave_name[slave] == bus_name, \
            f"Slave already registered to BUS {self.slave_name[slave]}"
        self.slaves.append(slave)
        self.slave_name[slave] = bus_name
        self.name_slave[bus_name] = slave

    def get_master_interface(self, bus_name: str = "", **kwargs: Any) -> MasterInterfaceUL:
        if bus_name in self.named_master:
            return self.named_master[bus_name]
        assert bus_name not in self.named_bus, f"Bus: {bus_name} already taken"
        self.named_bus[bus_name] = Bus(self.entity, bus_name, self._signals, **kwargs)
        self.named_master[bus_name] = DutMultiMasterMultiSlaveBridgeUL.MasterInterfaceImpl()
        return self.named_master[bus_name]

    def register_master(self, master: MasterInterfaceUL, bus_name: str = "") -> None:
        if len(self.masters) + 1 > self.max_masters_count:
            raise Exception("Too many masters for this slave")
        assert bus_name not in self.name_master, f"Two masters cannot use BUS named: {bus_name}"
        assert bus_name not in self.name_slave, f"Slave and master cannot use BUS named: {bus_name}"
        assert master not in self.master_name or self.master_name[master] == bus_name, \
            f"Master already registered to BUS {self.master_name[master]}"
        self.masters.append(master)
        self.master_name[master] = bus_name
        self.name_master[bus_name] = master

    def get_slave_interface(self, bus_name: str = "", **kwargs: Any) -> SlaveInterfaceUL:
        assert bus_name not in self.named_bus, f"Bus: {bus_name} already taken"
        self.named_bus[bus_name] = Bus(self.entity, bus_name, self._signals, **kwargs)
        self.named_slave[bus_name] = DutMultiMasterMultiSlaveBridgeUL.SlaveInterfaceImpl()
        return self.named_slave[bus_name]

    def get_monitorable_interface(self, master: MasterInterfaceUL) -> MonitorableInterface:
        if master not in self.master_monitorable:
            self.master_monitorable[master] = DutMultiMasterMultiSlaveBridgeUL.MasterMonitorableImpl()
        return self.master_monitorable[master]

    async def process(self) -> None:
        rw = ReadWrite()
        ce = RisingEdge(getattr(self.entity, self.clk_name))

        for master, bus_name in self.master_name.items():
            self.masters_bus[master] = self.named_bus[bus_name]

        for slave, bus_name in self.slave_name.items():
            self.slaves_bus[slave] = self.named_bus[bus_name]

        while True:
            modified = False

            # Reset events

            for slave_imp in self.named_slave.values():
                slave_imp.d_packet_and_valid_event.clear()
                slave_imp.a_ready_event.clear()

            for master_imp in self.named_master.values():
                master_imp.a_packet_and_valid_event.clear()
                master_imp.d_ready_event.clear()

            await rw

            # A Packet routing: Master(s) ->(registered master interfaces)->
            # Dut ->(handed out master interfaces)->
            # Slave(s)

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

            for bus_name, master_imp in self.named_master.items():
                bus = self.named_bus[bus_name]
                master_imp.a_valid = bool(bus.a_valid.value)
                master_imp.a_packet = TileLinkAPacket(
                    a_opcode=TileLinkULAOP(bus.a_opcode.value),
                    a_param = int(bus.a_param.value),
                    a_size = int(bus.a_size.value),
                    a_source = int(bus.a_source.value),
                    a_address = int(bus.a_address.value),
                    a_mask = int(bus.a_mask.value),
                    a_data = int(bus.a_data.value)
                )
                if master_imp in self.master_monitorable:
                    self.master_monitorable[master_imp].a_packet    = master_imp.a_packet
                    self.master_monitorable[master_imp].a_handshake = master_imp.a_valid

                master_imp.a_packet_and_valid_event.set()

            # D Packet routing: Slave(s) ->(registered slave interfaces)->
            # DUT ->(handed out slave interfaces)->
            # Master(s)

            for slave in self.slaves:
                d_packet, d_valid = await slave.get_D_packet_and_valid()
                bus = self.slaves_bus[slave]

                master_imp = self.named_master[self.slave_name[slave]]
                if master_imp in self.master_monitorable:
                    self.master_monitorable[master_imp].d_packet    = d_packet
                    self.master_monitorable[master_imp].d_handshake = d_valid

                if not bus.d_valid.value.is_resolvable or \
                    int(bus.d_valid.value) != int(d_valid):
                    modified = True
                bus.d_valid.setimmediatevalue(int(d_valid))
                for name in ('d_opcode', 'd_param', 'd_size', 'd_source', 'd_sink', 'd_error', 'd_data'):
                    if not getattr(bus, name).value.is_resolvable or \
                        int(getattr(bus, name).value) != int(getattr(d_packet, name)):
                        modified = True
                    getattr(bus, name).setimmediatevalue(getattr(d_packet, name))

            if modified:
                modified = False
                await rw

            for bus_name, slave_imp in self.named_slave.items():
                bus = self.named_bus[bus_name]
                slave_imp.d_valid = bool(bus.d_valid.value)
                slave_imp.d_packet = TileLinkDPacket(
                    d_opcode=TileLinkULDOP(bus.d_opcode.value),
                    d_param=int(bus.d_param.value),
                    d_size=int(bus.d_size.value),
                    d_source=int(bus.d_source.value),
                    d_sink=int(bus.d_sink.value),
                    d_error=TileLinkULResp(bus.d_error.value),
                    d_data=int(bus.d_data.value)
                )
                slave_imp.d_packet_and_valid_event.set()

            # D Ready routing: Master(s) ->(registered master interfaces)->
            # Dut ->(handed out master interfaces)->
            # Slave(s)

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

            for bus_name, master_imp in self.named_master.items():
                bus = self.named_bus[bus_name]
                master_imp.d_ready = bool(bus.d_ready.value)
                if master_imp in self.master_monitorable:
                    self.master_monitorable[master_imp].d_handshake &= master_imp.d_ready

                master_imp.d_ready_event.set()

            # A Ready routing: Slave(s) ->(registered slave interfaces)->
            # DUT ->(handed out slave interfaces)->
            # Master(s)

            for slave in self.slaves:
                a_ready = await slave.get_A_ready()
                bus = self.slaves_bus[slave]

                master_imp = self.named_master[self.slave_name[slave]]
                if master_imp in self.master_monitorable:
                    self.master_monitorable[master_imp].a_handshake &= a_ready

                if not bus.a_ready.value.is_resolvable or \
                    int(bus.a_ready.value) != int(a_ready):
                    modified = True
                bus.a_ready.setimmediatevalue(a_ready)

            if modified:
                modified = False
                await rw

            for bus_name, slave_imp in self.named_slave.items():
                bus = self.named_bus[bus_name]
                slave_imp.a_ready = bool(bus.a_ready.value)
                slave_imp.a_ready_event.set()

            for _, monitorable in self.master_monitorable.items():
                monitorable.all_done_event.set()

            await ce
