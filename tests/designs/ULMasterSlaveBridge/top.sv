module top #(
  parameter TL_AW=32,
  parameter TL_DW=32,
  parameter TL_AIW=8,
  parameter TL_DIW=1,
  parameter TL_DBW=(TL_DW>>3),
  parameter TL_SZW=$clog2($clog2(TL_DBW)+1)
)(
  input  wire       clk,
  input  wire       rstn,

  input  wire               master_a_valid,
  output logic              master_a_ready,
  input  wire         [2:0] master_a_opcode,
  input  wire         [2:0] master_a_param,
  input  wire  [TL_SZW-1:0] master_a_size,
  input  wire  [TL_AIW-1:0] master_a_source,
  input  wire   [TL_AW-1:0] master_a_address,
  input  wire  [TL_DBW-1:0] master_a_mask,
  input  wire   [TL_DW-1:0] master_a_data,

  output logic              master_d_valid,
  input  wire               master_d_ready,
  output logic        [2:0] master_d_opcode,
  output logic        [2:0] master_d_param,
  output logic [TL_SZW-1:0] master_d_size,
  output logic [TL_AIW-1:0] master_d_source,
  output logic [TL_DIW-1:0] master_d_sink,
  output logic  [TL_DW-1:0] master_d_data,
  output logic              master_d_error,

  output logic              slave_a_valid,
  input  wire               slave_a_ready,
  output logic        [2:0] slave_a_opcode,
  output logic        [2:0] slave_a_param,
  output logic [TL_SZW-1:0] slave_a_size,
  output logic [TL_AIW-1:0] slave_a_source,
  output logic  [TL_AW-1:0] slave_a_address,
  output logic [TL_DBW-1:0] slave_a_mask,
  output logic  [TL_DW-1:0] slave_a_data,

  input  wire               slave_d_valid,
  output logic              slave_d_ready,
  input  wire         [2:0] slave_d_opcode,
  input  wire         [2:0] slave_d_param,
  input  wire  [TL_SZW-1:0] slave_d_size,
  input  wire  [TL_AIW-1:0] slave_d_source,
  input  wire  [TL_DIW-1:0] slave_d_sink,
  input  wire   [TL_DW-1:0] slave_d_data,
  input  wire               slave_d_error
);

  always_comb begin
    if (!rstn) begin
      master_a_ready  = 0;

      slave_a_valid   = 0;
      slave_a_opcode  = 0;
      slave_a_param   = 0;
      slave_a_size    = 0;
      slave_a_source  = 0;
      slave_a_address = 0;
      slave_a_mask    = 0;
      slave_a_data    = 0;

      slave_d_ready   = 0;

      master_d_valid  = 0;
      master_d_opcode = 0;
      master_d_param  = 0;
      master_d_size   = 0;
      master_d_source = 0;
      master_d_sink   = 0;
      master_d_data   = 0;
      master_d_error  = 0;
    end else begin
      master_a_ready  = slave_a_ready;

      slave_a_valid   = master_a_valid;
      slave_a_opcode  = master_a_opcode;
      slave_a_param   = master_a_param;
      slave_a_size    = master_a_size;
      slave_a_source  = master_a_source;
      slave_a_address = master_a_address;
      slave_a_mask    = master_a_mask;
      slave_a_data    = master_a_data;

      slave_d_ready   = master_d_ready;

      master_d_valid  = slave_d_valid;
      master_d_opcode = slave_d_opcode;
      master_d_param  = slave_d_param;
      master_d_size   = slave_d_size;
      master_d_source = slave_d_source;
      master_d_sink   = slave_d_sink;
      master_d_data   = slave_d_data;
      master_d_error  = slave_d_error;
    end
  end

  `ifdef COCOTB_SIM
  initial begin
    $dumpfile ("waveforms.vcd");
    $dumpvars;
  end
  `endif
endmodule
