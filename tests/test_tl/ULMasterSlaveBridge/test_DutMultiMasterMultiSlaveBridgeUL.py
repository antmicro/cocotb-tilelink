from typing import List, Tuple
from random import randrange, randint

import cocotb # type: ignore
from cocotb.clock import Clock # type: ignore
from cocotb.handle import SimHandle, SimHandleBase # type: ignore
from cocotb.triggers import ClockCycles, RisingEdge, ReadOnly, Timer, Combine, Join # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import TileLinkDPacket
from cocotb_TileLink.TileLink_common.Interfaces import MemoryInterface

from cocotb_TileLink.drivers.SimSimpleMasterUL import SimSimpleMasterUL
from cocotb_TileLink.drivers.SimTrafficGeneratorUL import SimTrafficGeneratorUL

from cocotb_TileLink.drivers.DutMultiMasterMultiSlaveBridgeUL import DutMultiMasterMultiSlaveBridgeUL
from cocotb_TileLink.drivers.SimSimpleSlaveUL import SimSimpleSlaveUL

from cocotb_TileLink.monitors.TileLinkULMonitor import TileLinkULMonitor

CLK_PERIOD = (10, "ns")

def update_expected_value(previous_value: List[int], write_value: List[int], mask: List[bool]) -> List[int]:
    result = [0 for i in range(len(previous_value))]
    for  i in range(len(previous_value)):
        result[i] = write_value[i] if mask[i] else previous_value[i]
    return result


def compare_read_values(expected_value: List[int], read_value: List[int], address: int) -> None:
    assert len(expected_value) == len (read_value)
    for i in range(len(read_value)):
        assert expected_value[i] == read_value[i], \
            "Read {:#x} at address {:#x}, but was expecting {:#x}".format(read_value[i], address+i, expected_value[i])


def conver_to_int_list(rsp: List[TileLinkDPacket], base_address: int, bus_byte_width: int) -> List[int]:
    ans: List[int] = []
    addr = base_address
    for i in rsp:
        _offset = addr % bus_byte_width
        for j in range(2**i.d_size):
            ans.append((i.d_data >> ((_offset + j)*8)) & 0xFF)
        addr += 2**i.d_size
    return ans


def get_parameters(dut: SimHandle) -> Tuple[int, int]:
    address_width = dut.TL_AW.value
    data_width    = dut.TL_DW.value
    return address_width, data_width


async def setup_dut(dut: SimHandle) -> None:
    cocotb.fork(Clock(dut.clk, *CLK_PERIOD).start())
    dut.rstn.value = 0
    await ClockCycles(dut.clk, 100)
    dut.rstn.value = 1
    await ClockCycles(dut.clk, 10)


def mem_init(TLs: MemoryInterface, size: int) -> None:
    mask = []
    write_value = []
    for i in range(size):
        write_value.append(randint(0, 255))
        mask.append(bool(randint(0, 1)))
    mem_init_array = []
    for _mask, _value in zip(mask, write_value):
        if _mask:
            mem_init_array.append(_value)
        else:
            mem_init_array.append(0)
    TLs.init_memory(mem_init_array, 0)


async def init_random_data(TLm: SimSimpleMasterUL, TLs: MemoryInterface, size: int) -> None:
    before_mem = TLs.memory_dump()
    mask = []
    write_value = []
    for i in range(size):
        write_value.append(randint(0, 255))
        mask.append(bool(randint(0, 1)))
    TLm.write(0, size, write_value, mask)
    await TLm.source_free(0)
    modified_mem = TLs.memory_dump()
    expected_mem = update_expected_value(before_mem, write_value, mask)
    compare_read_values(expected_mem, modified_mem, 0)


@cocotb.test() # type: ignore
async def test_SimpleMasterSimpleSlave(dut: SimHandleBase) -> None:
    TLBridge = DutMultiMasterMultiSlaveBridgeUL(dut)

    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8
    TLm = SimSimpleMasterUL(bus_width)
    TLm.register_clock(dut.clk).register_reset(dut.rstn, True)
    TLm.register_slave(TLBridge.get_slave_interface(bus_name="master"))
    TLBridge.register_master(TLm.get_master_interface(), bus_name="master")

    TLs = SimSimpleSlaveUL(bus_width, size=0x8000)
    TLs.register_clock(dut.clk).register_reset(dut.rstn, True)
    TLBridge.register_slave(TLs.get_slave_interface(), bus_name="slave")
    TLs.register_master(TLBridge.get_master_interface(bus_name="slave"))

    cocotb.fork(TLBridge.process())
    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    await setup_dut(dut)
    mem_init(TLs, 0x8000)
    await init_random_data(TLm, TLs, 0x8000)
    address = randrange(0, 0x8000, bus_byte_width)
    write_value = []
    mask = []
    for i in range(bus_byte_width):
        write_value.append(randint(0,255))
        mask.append(bool(randint(0,1)))
    TLm.read(address, bus_byte_width)
    await TLm.source_free(0)
    previous_value = conver_to_int_list(TLm.get_rsp(0), address, bus_byte_width)
    TLm.write(address, len(mask), write_value, mask)
    await TLm.source_free(0)
    TLm.read(address, bus_byte_width)
    await TLm.source_free(0)
    read_value = conver_to_int_list(TLm.get_rsp(0), address, bus_byte_width)

    expected_value = update_expected_value(previous_value,
                                           write_value, mask)

    compare_read_values(expected_value, read_value, address)
    TLm.finish()
    await TLm.sim_finished()


@cocotb.test() # type: ignore
async def test_TrafficGeneratorMasterSimpleSlave(dut: SimHandleBase) -> None:
    TLBridge = DutMultiMasterMultiSlaveBridgeUL(dut)

    master = SimTrafficGeneratorUL(name="master_sim", addr_width=16, num_of_transactions=int(2e4))
    master.register_clock(dut.clk).register_reset(dut.rstn, True)
    master.register_slave(TLBridge.get_slave_interface(bus_name="master"))
    TLBridge.register_master(master.get_master_interface(), bus_name="master")

    TLmonitor = TileLinkULMonitor().register_clock(dut.clk).register_reset(dut.rstn, True)
    TLmonitor.register_device(master)
    cocotb.fork(TLmonitor.process())

    slave = SimSimpleSlaveUL(size=2**16).register_clock(dut.clk).register_reset(dut.rstn, True)
    TLBridge.register_slave(slave.get_slave_interface(), bus_name="slave")
    slave.register_master(TLBridge.get_master_interface(bus_name="slave"))

    cocotb.fork(TLBridge.process())
    cocotb.fork(master.process())
    cocotb.fork(slave.process())

    await setup_dut(dut)
    await master.sim_finished()
