# SPDX-FileCopyrightText: 2026 Cindy Gatica
# SPDX-License-Identifier: Apache-2.0

"""cocotb tests for the vaccine vial heat monitor.

uo_out[3:0] = {buzzer, red, yellow, green}
ui_in       = {x, x, test_mode, limit_sel[1:0], temp_code[2:0]}
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

# What the four output pins show in each state
GREEN = 0b0001                   # safe
YELLOW = 0b0010                  # warning
RED = 0b1100                     # discard: red LED + buzzer

DAMAGE = [0, 0, 1, 2, 4, 8, 16, 32]   # damage per step for each temperature code
LIMIT = [128, 256, 512, 1000]         # discard limit for each limit_sel value


def ui(code, limit_sel=0, test_mode=1):
    """Build the ui_in byte."""
    return (test_mode << 5) | (limit_sel << 3) | code


async def init(dut):
    """Start the 10 MHz simulation clock (once per test)."""
    cocotb.start_soon(Clock(dut.clk, 100, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0


async def reset(dut, ui_value):
    """Reset the design (a new vial) with ui_in = ui_value."""
    dut.ui_in.value = ui_value
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1


async def start(dut, ui_value):
    await init(dut)
    await reset(dut, ui_value)


async def clocks(dut, n):
    """Wait n clock cycles, then let the flip-flops settle."""
    await ClockCycles(dut.clk, n)
    await Timer(1, unit="ns")


def leds(dut):
    return int(dut.uo_out.value) & 0x0F


@cocotb.test()
async def test_cold_vial_stays_green(dut):
    await start(dut, ui(0b001))           # 2-8 C: no damage
    await clocks(dut, 20)
    assert leds(dut) == GREEN
    dut.ui_in.value = ui(0b000)           # below 2 C: no damage either
    await clocks(dut, 50)
    assert leds(dut) == GREEN


@cocotb.test()
async def test_hot_vial_code_111(dut):
    await start(dut, ui(0b111))           # above 37 C: 32 per step, limit 128
    await clocks(dut, 1)
    assert leds(dut) == GREEN             # total 32
    await clocks(dut, 1)
    assert leds(dut) == YELLOW            # total 64 = half of the limit
    await clocks(dut, 1)
    assert leds(dut) == YELLOW            # total 96
    await clocks(dut, 1)
    assert leds(dut) == RED               # total 128 = limit


@cocotb.test()
async def test_other_codes(dut):
    # (code, clocks to yellow, clocks to red) with limit 128
    await init(dut)
    for code, to_yellow, to_red in [(0b101, 8, 16), (0b100, 16, 32)]:
        await reset(dut, ui(code))
        await clocks(dut, to_yellow - 1)
        assert leds(dut) == GREEN
        await clocks(dut, 1)
        assert leds(dut) == YELLOW
        await clocks(dut, to_red - to_yellow - 1)
        assert leds(dut) == YELLOW
        await clocks(dut, 1)
        assert leds(dut) == RED


@cocotb.test()
async def test_red_is_latched(dut):
    await start(dut, ui(0b111))
    await clocks(dut, 4)
    assert leds(dut) == RED
    dut.ui_in.value = ui(0b001)           # cool the vial down
    await clocks(dut, 10)
    assert leds(dut) == RED               # still red
    dut.ui_in.value = ui(0b001, limit_sel=3)  # even with a higher limit
    await clocks(dut, 10)
    assert leds(dut) == RED


@cocotb.test()
async def test_damage_is_remembered(dut):
    await start(dut, ui(0b111))
    await clocks(dut, 3)
    assert leds(dut) == YELLOW            # total 96
    dut.ui_in.value = ui(0b000)           # now cold: total must not change
    await clocks(dut, 50)
    assert leds(dut) == YELLOW
    dut.ui_in.value = ui(0b111)           # hot again: 96 + 32 = 128
    await clocks(dut, 1)
    assert leds(dut) == RED


@cocotb.test()
async def test_limit_select(dut):
    # limit 256 (01): yellow after 4 clocks, red after 8
    await start(dut, ui(0b111, limit_sel=1))
    await clocks(dut, 3)
    assert leds(dut) == GREEN
    await clocks(dut, 1)
    assert leds(dut) == YELLOW
    await clocks(dut, 3)
    assert leds(dut) == YELLOW
    await clocks(dut, 1)
    assert leds(dut) == RED


@cocotb.test()
async def test_reset_is_a_new_vial(dut):
    await start(dut, ui(0b111))
    await clocks(dut, 4)
    assert leds(dut) == RED
    dut.rst_n.value = 0
    await clocks(dut, 3)
    dut.rst_n.value = 1
    await Timer(1, unit="ns")
    assert leds(dut) == GREEN
    await clocks(dut, 2)
    assert leds(dut) == YELLOW            # counting again from zero


@cocotb.test()
async def test_real_time_one_step_per_60_clocks(dut):
    await start(dut, ui(0b111, test_mode=0))
    await clocks(dut, 119)
    assert leds(dut) == GREEN             # only 1 step so far (total 32)
    await clocks(dut, 1)
    assert leds(dut) == YELLOW            # step 2 at clock 120
    await clocks(dut, 119)
    assert leds(dut) == YELLOW            # clock 239
    await clocks(dut, 1)
    assert leds(dut) == RED               # step 4 at clock 240


@cocotb.test()
async def test_against_reference_model(dut):
    """Every temperature code and every limit, compared clock by clock
    with a small Python model of the same algorithm."""
    await init(dut)
    for code in range(8):
        for sel in range(4):
            await reset(dut, ui(code, limit_sel=sel))
            limit = LIMIT[sel]
            acc, latch = 0, False
            n = limit // DAMAGE[code] + 3 if DAMAGE[code] else 30
            for _ in range(n):
                over = acc >= limit
                red = latch or over
                latch = latch or over
                if not red:
                    acc += DAMAGE[code]
                over = acc >= limit
                red = latch or over
                alert = (acc >= limit // 2) or red
                expected = (int(not alert)
                            | int(alert and not red) << 1
                            | int(red) << 2
                            | int(red) << 3)
                await clocks(dut, 1)
                assert leds(dut) == expected, (
                    f"code {code}, limit {limit}: total {acc}, "
                    f"expected {expected:04b}, got {leds(dut):04b}")
