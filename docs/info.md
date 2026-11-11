<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Vaccines lose potency faster as they warm up. The reaction rate behind that degradation grows exponentially with temperature (Arrhenius law: rate is proportional to exp(-Ea/RT)), so heat damage adds up over time. This chip keeps a running total of that damage, like the heat-sensitive monitors on vaccine vials, and shows green, yellow or red.

**Inputs and outputs**

| Pin | Function |
|---|---|
| `ui_in[2:0]` | temperature code (0-7) |
| `ui_in[4:3]` | discard limit: 128, 256, 512 or 1000 |
| `ui_in[5]` | test mode: 1 = one step per clock, 0 = one step per 60 clocks (one minute at 1 Hz) |
| `rst_n` | new vial: clears the total |
| `uo_out[0]` | green (safe) |
| `uo_out[1]` | yellow (warning) |
| `uo_out[2]` | red (discard) |
| `uo_out[3]` | buzzer |

**Damage table.** A mux acts as a lookup table from temperature code to damage per step. The damage roughly doubles with each warmer bin.

| Code | Temperature | Damage per step |
|---|---|---|
| 0 | below 2 °C | 0 |
| 1 | 2-8 °C | 0 |
| 2 | 8-15 °C | 1 |
| 3 | 15-20 °C | 2 |
| 4 | 20-25 °C | 4 |
| 5 | 25-30 °C | 8 |
| 6 | 30-37 °C | 16 |
| 7 | above 37 °C | 32 |

**Blocks**

1. **Tick generator:** a 6-bit divide-by-60 counter (flip-flops) turns a 1 Hz clock into one step per minute. In test mode a mux bypasses it, so every clock is a step.
2. **Accumulator:** on each step an adder adds the damage to an 11-bit register of flip-flops.
3. **Comparators:** a mux picks the limit. One comparator flags a warning (total >= half the limit) and another flags discard (total >= the limit).
4. **Alarm:** a flip-flop latches the discard state, and the accumulator stops once it is set, so cooling the vial can't undo it. Gates then light one LED: red = latch, yellow = warning AND NOT red, green = NOT (warning OR red). The buzzer follows red.

In total there are 18 flip-flops (11 + 6 + 1) and 3 muxes (lookup, limit, tick), plus the adder, comparators and output gates. The weights and limits are example values. Real ones come from the vaccine maker's stability data.

## How to test

You can run the same tests in simulation or on the demo board.

**Demo board**

1. Plug in the board and open the Tiny Tapeout Commander (commander.tinytapeout.com) in Chrome, Edge, Opera or Brave, since it needs the Web Serial API. Connect and select this project.
2. Set the clock frequency and press SET to start the clock, or skip that and single-step it from the Interact tab. Use 10 Hz.
3. Set the inputs on the DIP switches or in the Interact tab. Use `ui_in[5]` = 1 (test mode) and `ui_in[4:3]` = 00 (limit 128). Put the temperature code on `ui_in[2:0]` for each row below, and reset before each row.
4. Read the result on your LEDs, or on segments a (green), b (yellow), c (red) and d (buzzer) of the board's display.

**Simulation**

Run `make -B` in the `test` folder. This runs the cocotb tests in `test.py`, which check the same rows as the table below and compare every temperature code and limit with a Python model. Then open the waveform with `gtkwave tb.fst tb.gtkw` to watch the accumulator.

**Expected results**

| Code | Clocks after reset | Expected |
|---|---|---|
| 001 | 20 | green only |
| 111 | 2 | yellow |
| 111 | 4 | red + buzzer |
| 101 | 8 / 16 | yellow / red |
| 100 | 16 / 32 | yellow / red |
| 111, then 001 | 4, then 10 more | stays red |

Limit check: with `ui_in[4:3]` = 01 (limit 256) and code 111, yellow appears after 4 clocks and red after 8.

Real-time check: set `ui_in[5]` = 0 and the clock to 1 Hz. With code 111, yellow appears after 120 clocks (2 minutes) and red after 240 (4 minutes).

Pass: every row matches, and reset always returns to green only.

## External hardware

Green, yellow and red LEDs (with resistors) on `uo_out[0]`, `uo_out[1]` and `uo_out[2]`, and a buzzer on `uo_out[3]`. The demo board's DIP switches supply the temperature code, and segments a to d of its 7-segment display mirror the four output pins, so you can test before wiring any LEDs. A real temperature sensor with comparators can replace the switches later.
