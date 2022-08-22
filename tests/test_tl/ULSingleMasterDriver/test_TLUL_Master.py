from typing import Tuple, Dict, List, Iterator
from random import randrange, randint, getrandbits
from itertools import chain, combinations, permutations
import warnings

import cocotb # type: ignore
from cocotb.clock import Clock # type: ignore
from cocotb.handle import SimHandle, SimHandleBase # type: ignore
from cocotb.regression import TestFactory # type: ignore
from cocotb.triggers import ClockCycles, Combine, Join, RisingEdge # type: ignore

from cocotb_TileLink.TileLink_common.TileLink_types import*

from cocotb_TileLink.drivers.SimSimpleMasterUL import SimSimpleMasterUL

from cocotb_TileLink.drivers.DutMultiMasterSlaveUL import DutMultiMasterSlaveUL

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


def split_read_to_bus_width(values: Dict[int, List[int]], bus_width: int) -> Dict[int, List[int]]:
    ret: Dict[int, List[int]] = {}
    for address, _values in values.items():
        base_address = (address//bus_width)*bus_width
        offset = 0
        while base_address < address + len(_values):
            if base_address not in ret:
                ret[base_address] = [0] * bus_width
            for i in range(bus_width):
                if base_address + i in range(address, address + len(_values)):
                    ret[base_address][i] = _values[offset]
                    offset += 1
            base_address += bus_width
    return ret


def split_write_to_bus_width(values: Dict[int, List[Tuple[List[int], List[bool]]]], bus_width: int) \
        -> Dict[int, List[Tuple[List[int], List[bool]]]]:
    ret: Dict[int, List[Tuple[List[int], List[bool]]]] = {}

    for address, _sequances in values.items():
        for _write_values, _mask in _sequances:
            base_address = (address//bus_width)*bus_width
            offset = 0
            while base_address < address + len(_mask):
                if base_address not in ret:
                    ret[base_address] = []
                temp_write_values: List[int] = []
                temp_write_mask: List[bool] = []
                for i in range(bus_width):
                    if base_address + i in range(address, address + len(_mask)):
                        temp_write_values.append(_write_values[offset])
                        temp_write_mask.append(_mask[offset])
                        offset += 1
                    else:
                        temp_write_values.append(0)
                        temp_write_mask.append(False)
                ret[base_address].append((temp_write_values, temp_write_mask))
                base_address += bus_width
    return ret


def get_powerset(address_writes: List[Tuple[List[int], List[bool]]]) -> Iterator[Tuple[Tuple[List[int], List[bool]], ...]]:
    s = list(address_writes)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s)+1))


def compare_multimaster_read_values(data_width: int, start_value: List[int],
                                    addr_value_mask: List[Tuple[List[int], List[bool]]],
                                    read_value: List[int], address: int) -> None:
    all_subsets = get_powerset(addr_value_mask)
    for subset in all_subsets:
        for perm in permutations(subset):
            res = start_value
            for (value, mask) in perm:
                res = update_expected_value(res, value, mask)
            if res == read_value:
                return
    assert False, f"Read {read_value} at {address=},"\
                  " but there is no such write ordering,"\
                  " that would lead to this value"


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


async def init_random_data(TLm: SimSimpleMasterUL, data_byte_width: int) -> None:
    mask = []
    write_value = []
    for i in range(0, 0x8000):
        write_value.append(randint(0, 255))
        mask.append(bool(randint(0, 1)))
    TLm.write(0, 0x8000, write_value, mask)
    await TLm.source_free(0)


used: bool = False
async def test_single_master_sizes(dut: SimHandle, read_size: int, write_size: int) -> None:
    await setup_dut(dut)
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8

    TLm = SimSimpleMasterUL(bus_width).register_clock(dut.clk).register_reset(dut.rstn, True)
    TLs = DutMultiMasterSlaveUL(dut)

    TLm.register_slave(TLs.get_slave_interface())
    TLs.register_master(TLm.get_master_interface())

    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    global used
    if not used:
        await init_random_data(TLm, bus_byte_width)
        used = True

    for i in range(20):
        address = randrange(0, 0x8000, 2**write_size)
        write_value = []
        mask = []
        for i in range(2**write_size):
            write_value.append(randint(0, 255))
            mask.append(bool(randint(0, 1)))
        _mask = bus_byte_width - 1

        TLm.read(address & ~(_mask), bus_byte_width)
        await TLm.source_free(0)
        previous_value = conver_to_int_list(TLm.get_rsp(0), address&~_mask, bus_byte_width)

        TLm.write(address, 2**write_size, write_value, mask)
        _offset = address % bus_byte_width
        for i in range(0, 2**write_size):
            previous_value[i+_offset] = write_value[i] if mask[i] else previous_value[i+_offset]
        await TLm.source_free(0)

        TLm.read(address & ~(2**read_size - 1), 2**read_size)
        await TLm.source_free(0)
        read_value = conver_to_int_list(TLm.get_rsp(0), address&~(2**read_size - 1), bus_byte_width)

        compare_read_size_values(previous_value, read_value, address, bus_byte_width, 2**read_size)

    TLm.finish()
    await TLm.sim_finished()


async def test_multiple_masters(dut: SimHandle, num: int = 4, multiply: int = 1) -> None:
    await setup_dut(dut)
    address_width, bus_width = get_parameters(dut)
    bus_byte_width = bus_width//8

    TLm = SimSimpleMasterUL(bus_width).register_clock(dut.clk).register_reset(dut.rstn, True)
    TLs = DutMultiMasterSlaveUL(dut)

    TLm.register_slave(TLs.get_slave_interface())
    TLs.register_master(TLm.get_master_interface())

    cocotb.fork(TLs.process())
    cocotb.fork(TLm.process())

    addresses = [randrange((i%2)*0x4000, 0x4000*(1+i%2) - bus_byte_width * multiply) for i in range(num)]

    write_values = [[randint(0, 255) for j in range(bus_byte_width * multiply)] for i in range(num)]
    masks = [[bool(randint(0, 1)) for j in range(bus_byte_width * multiply)] for i in range(num)]

    previous_values = {}
    for i, address in enumerate(addresses):
        TLm.read(address, bus_byte_width * multiply, i)

    for i, address in enumerate(addresses):
        await TLm.source_free(i)
        previous_values[address] = conver_to_int_list(TLm.get_rsp(i), address, bus_byte_width)
    temp_previous_values = split_read_to_bus_width(previous_values, bus_byte_width)

    for i, address in enumerate(addresses):
        TLm.write(address, bus_byte_width * multiply, write_values[i], masks[i], i)

    addr_value_mask: Dict[int, List[Tuple [List[int], List[bool]]]] = {}
    for (address, value, mask) in zip(addresses, write_values, masks):
        if not address in addr_value_mask.keys():
            addr_value_mask[address] = []
        addr_value_mask[address].append((value, mask))

    temp_addr_value_mask = split_write_to_bus_width(addr_value_mask, bus_byte_width)

    for i, address in enumerate(addresses):
        await TLm.source_free(i)

    read_values: Dict[int, List[int]] = {}
    for i, address in enumerate(addresses):
        TLm.read(address, bus_byte_width * multiply, i)

    for i, address in enumerate(addresses):
        await TLm.source_free(i)
        read_values[address] = conver_to_int_list(TLm.get_rsp(i), address, bus_byte_width)

    temp_read_values = split_read_to_bus_width(read_values, bus_byte_width)

    for address, read_value in temp_read_values.items():
        compare_multimaster_read_values(bus_byte_width,
                                        temp_previous_values[address],
                                        temp_addr_value_mask[address],
                                        read_value, address)
    TLm.finish()
    await TLm.sim_finished()




single_master_sizes = TestFactory(test_single_master_sizes)
single_master_sizes.add_option('read_size', (0,1,2))
single_master_sizes.add_option('write_size', (0,1,2))
single_master_sizes.generate_tests()


multiple_masters = TestFactory(test_multiple_masters)
multiple_masters.add_option('num', (2,4,6,8))
multiple_masters.add_option('multiply', (2,2,4,6,8,10))
multiple_masters.generate_tests()
