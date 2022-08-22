from typing import Tuple, Dict, List, Iterator
from random import randrange, randint
from itertools import chain, combinations, permutations
import warnings

import cocotb # type: ignore
from cocotb.clock import Clock # type: ignore
from cocotb.handle import SimHandle, SimHandleBase # type: ignore
from cocotb.triggers import ClockCycles, Combine, Join, RisingEdge # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import*
from cocotb_TileLink.TileLink_common.Interfaces import MemoryInterface

from cocotb_TileLink.drivers.SimSimpleMasterUL import SimSimpleMasterUL
from cocotb_TileLink.drivers.SimTrafficGeneratorUL import SimTrafficGeneratorUL
from cocotb_TileLink.drivers.SimRandomTrafficGeneratorUL import SimRandomTrafficGeneratorUL

from cocotb_TileLink.drivers.SimSimpleSlaveUL import SimSimpleSlaveUL
from cocotb_TileLink.drivers.SimCheckInvalidSlaveUL import SimCheckInvalidSlaveUL

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


def compare_read_size_values(expected_value: List[int], read_value: List[int],
                             address: int, bus_byte_width: int, size: int) -> None:
    _offset = ((address % bus_byte_width) & ~(size - 1))
    expected_value = expected_value[_offset:_offset+size]
    assert expected_value == read_value, "Read {} at address {:#x}, but was expecting {}".format(read_value, address, expected_value)


def get_powerset(address_writes: List[Tuple[List[int], List[bool]]]) -> Iterator[Tuple[Tuple[List[int], List[bool]], ...]]:
    s = list(address_writes)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s)+1))


def compare_multimaster_read_values(data_width: int, start_value: List[int],
                                    addr_value_mask: Dict[int, List[Tuple[List[int], List[bool]]]],
                                    read_value: List[int], address: int) -> None:
    all_subsets = get_powerset(addr_value_mask[address])
    for subset in all_subsets:
        for perm in permutations(subset):
            res = start_value
            for (value, mask) in perm:
                res = update_expected_value(res, value, mask)
            if res == read_value:
                return
    assert False, "Read {} at address {},"\
                  " but there is no such write ordering,"\
                  " that would lead to this value".format(read_value, address)


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
async def test_single_master_simple_slave(dut: SimHandle) -> None:
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8
    TLm = SimSimpleMasterUL(bus_width)
    TLm.register_clock(dut.clk).register_reset(dut.rstn, True)

    TLs = SimSimpleSlaveUL(bus_width, size=0x8000)
    TLs.register_clock(dut.clk).register_reset(dut.rstn, True)
    TLs.register_master(TLm.get_master_interface())
    TLm.register_slave(TLs.get_slave_interface())

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
async def test_trafic_generator_simple_slave(dut: SimHandle) -> None:
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8
    TLm = SimTrafficGeneratorUL(bus_width=bus_width, addr_width=address_width, num_of_transactions=int(2e4))
    TLm.register_clock(dut.clk).register_reset(dut.rstn, True)

    TLs = SimSimpleSlaveUL(bus_width, size=0x8000)
    TLs.register_clock(dut.clk).register_reset(dut.rstn, True)

    TLs.register_master(TLm.get_master_interface())
    TLm.register_slave(TLs.get_slave_interface())

    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    await setup_dut(dut)
    await TLm.sim_finished()


@cocotb.test() # type: ignore
async def test_random_trafic_master_check_invalid_slave(dut: SimHandle) -> None:
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8
    TLm = SimRandomTrafficGeneratorUL(bus_width=bus_width, addr_width=address_width)
    TLm.register_clock(dut.clk).register_reset(dut.rstn, True)

    TLs = SimCheckInvalidSlaveUL(bus_width, size=0x8000)
    TLs.register_clock(dut.clk).register_reset(dut.rstn, True)
    TLs.register_master(TLm.get_master_interface())
    TLm.register_slave(TLs.get_slave_interface())

    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    await setup_dut(dut)
    await TLm.sim_finished()


@cocotb.test() # type: ignore
async def test_TileLinkUL_monitor(dut: SimHandle) -> None:
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8

    TLm = SimSimpleMasterUL().register_clock(dut.clk).register_reset(dut.rstn, True)
    TLmonitor = TileLinkULMonitor().register_clock(dut.clk).register_reset(dut.rstn, True)
    TLmonitor.register_device(TLm)
    cocotb.fork(TLmonitor.process())

    TLs = SimSimpleSlaveUL(bus_width, 0x8000)
    TLs.register_clock(dut.clk).register_reset(dut.rstn, True)
    TLs.register_master(TLm.get_master_interface())
    TLm.register_slave(TLs.get_slave_interface())

    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    warnings.simplefilter("ignore")
    await setup_dut(dut)

    for _ in range(100):
        address = randrange(0, 0x8000)
        length = randint(1, 16)
        write_value = []
        mask        = []
        for _ in range(length):
            write_value.append(randint(0, 255))
            mask.append(bool(randint(0, 1)))
        TLm.read(address, length)
        await TLm.source_free(0)
        previous_value = conver_to_int_list(TLm.get_rsp(0), address, bus_byte_width)
        TLm.write(address, length, write_value, mask)
        await TLm.source_free(0)
        TLm.read(address, length)
        await TLm.source_free(0)
        read_value = conver_to_int_list(TLm.get_rsp(0), address, bus_byte_width)

        expected_value = update_expected_value(previous_value,
                                               write_value, mask)

        compare_read_values(expected_value, read_value, address)
    TLm.finish()
    await TLm.sim_finished()
