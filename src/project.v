/*
 * Copyright (c) 2026 Cindy Gatica
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Vaccine vial heat monitor (time-temperature integrator).
//
// Vaccines lose potency faster as they warm up (Arrhenius law), so heat
// damage adds up over time. This chip adds up that damage and lights
// green / yellow / red, like the heat-sensitive labels on vaccine vials.
//
// Inputs
//   ui_in[2:0]  temperature code (0-7)
//   ui_in[4:3]  discard limit: 00 = 128, 01 = 256, 10 = 512, 11 = 1000
//   ui_in[5]    test mode: 1 = one step per clock, 0 = one step per 60 clocks
//   rst_n       new vial: clears everything
// Outputs
//   uo_out[0]   green  (safe)
//   uo_out[1]   yellow (warning, total >= half of the limit)
//   uo_out[2]   red    (discard, total >= limit, latched until reset)
//   uo_out[3]   buzzer (follows red)

module tt_um_CINDYGAT_tt_cg (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // ---------------------------------------------------------------------
  // Input names
  // ---------------------------------------------------------------------
  wire [2:0] temp_code  = ui_in[2:0];
  wire [1:0] limit_sel  = ui_in[4:3];
  wire       test_mode  = ui_in[5];

  // ---------------------------------------------------------------------
  // Mux 1: damage lookup table (temperature code -> damage per step)
  // The damage roughly doubles with each warmer bin.
  // ---------------------------------------------------------------------
  reg [5:0] damage;
  always @(*) begin
    case (temp_code)
      3'd0:    damage = 6'd0;   // below 2 C
      3'd1:    damage = 6'd0;   // 2-8 C (the safe cold-chain range)
      3'd2:    damage = 6'd1;   // 8-15 C
      3'd3:    damage = 6'd2;   // 15-20 C
      3'd4:    damage = 6'd4;   // 20-25 C
      3'd5:    damage = 6'd8;   // 25-30 C
      3'd6:    damage = 6'd16;  // 30-37 C
      default: damage = 6'd32;  // above 37 C
    endcase
  end

  // ---------------------------------------------------------------------
  // Block 1: tick generator = divide-by-60 counter (6 flip-flops)
  // With a 1 Hz clock this makes one step per minute.
  // Mux 2 (test mode) bypasses it so every clock is a step.
  // ---------------------------------------------------------------------
  reg [5:0] div_cnt;
  wire      div_done = (div_cnt == 6'd59);
  wire      tick     = test_mode ? 1'b1 : div_done;

  always @(posedge clk) begin
    if (!rst_n)        div_cnt <= 6'd0;
    else if (div_done) div_cnt <= 6'd0;
    else               div_cnt <= div_cnt + 6'd1;
  end

  // ---------------------------------------------------------------------
  // Mux 3: discard limit
  // ---------------------------------------------------------------------
  reg [10:0] limit;
  always @(*) begin
    case (limit_sel)
      2'd0:    limit = 11'd128;
      2'd1:    limit = 11'd256;
      2'd2:    limit = 11'd512;
      default: limit = 11'd1000;
    endcase
  end
  wire [10:0] half_limit = {1'b0, limit[10:1]};

  // ---------------------------------------------------------------------
  // Block 3: comparators
  // ---------------------------------------------------------------------
  reg  [10:0] acc;                    // Block 2: accumulated damage (11 flip-flops)
  reg         red_latch;              // Block 4: latched discard flag (1 flip-flop)

  wire warn = (acc >= half_limit);    // warning: at least half of the limit
  wire over = (acc >= limit);         // discard: limit reached
  wire red  = red_latch | over;       // once red, it stays red until reset

  // ---------------------------------------------------------------------
  // Block 2 + 4: accumulator and latch
  // On every step an adder adds the damage to the total.
  // Once red, the total stops, so cooling the vial cannot undo it.
  // ---------------------------------------------------------------------
  always @(posedge clk) begin
    if (!rst_n) begin
      acc       <= 11'd0;
      red_latch <= 1'b0;
    end else begin
      if (over) red_latch <= 1'b1;
      if (tick && !red) acc <= acc + {5'd0, damage};
    end
  end

  // ---------------------------------------------------------------------
  // Outputs
  // ---------------------------------------------------------------------
  wire alert  = warn | red;
  wire green  = ~alert;
  wire yellow = alert & ~red;

  //                 unused    buzzer red  yellow green
  assign uo_out  = {4'b0000,   red,   red, yellow, green};
  assign uio_out = 8'h00;
  assign uio_oe  = 8'h00;

  // List all unused inputs to prevent warnings
  wire _unused = &{ena, ui_in[7:6], uio_in, 1'b0};

endmodule
