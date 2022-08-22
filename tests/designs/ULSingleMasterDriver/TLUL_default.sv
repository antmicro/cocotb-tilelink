module TLUL_default #(
  parameter MAX_DELAY=4,
  parameter TL_AW=32,
  parameter TL_DW=32,
  parameter TL_AIW=8,
  parameter TL_DIW=1,
  parameter TL_DBW=(TL_DW>>3),
  parameter TL_SZW=$clog2($clog2(TL_DBW)+1)
)(
  input  wire       clk,
  input  wire       rstn,

  input  wire              a_valid,
  output wire              a_ready,
  input  wire        [2:0] a_opcode,
  input  wire        [2:0] a_param,
  input  wire [TL_SZW-1:0] a_size,
  input  wire [TL_AIW-1:0] a_source,
  input  wire  [TL_AW-1:0] a_address,
  input  wire [TL_DBW-1:0] a_mask,
  input  wire  [TL_DW-1:0] a_data,

  output wire              d_valid,
  input  wire              d_ready,
  output wire        [2:0] d_opcode,
  output wire        [2:0] d_param,
  output wire [TL_SZW-1:0] d_size,
  output wire [TL_AIW-1:0] d_source,
  output wire [TL_DIW-1:0] d_sink,
  output wire  [TL_DW-1:0] d_data,
  output wire              d_error
);

  wire a_ack, d_ack;

  reg [TL_SZW-1:0] size;
  reg        [2:0] opcode;
  reg        [2:0] param;
  reg [TL_AIW-1:0] source;
  reg              resp;

  assign a_ready = !resp;
  assign a_ack = a_valid & a_ready;

  assign d_valid = resp;
  assign d_ack = d_valid & d_ready;

  assign d_opcode = opcode;
  assign d_param = param;
  assign d_size = size;
  assign d_source = source;
  assign d_sink = 0;
  assign d_data = 0;
  assign d_error = 1;

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      resp <= 0;
    end else if (a_ack) begin
      resp <= 1;
    end else if (d_ack) begin
      resp <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      size <= 0;
    end else if (a_ack) begin
      size <= a_size;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      opcode <= 0;
    end else if (a_ack) begin
      opcode <= a_opcode == 3'h4 ? 1 : 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      param <= 0;
    end else if (a_ack) begin
      param <= a_param;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      source <= 0;
    end else if (a_ack) begin
      source <= a_source;
    end
  end
endmodule
