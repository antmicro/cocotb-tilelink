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

  wire              a_valid_d[3];
  wire              a_ready_d[3];
  wire        [2:0] a_opcode_d[3];
  wire        [2:0] a_param_d[3];
  wire [TL_SZW-1:0] a_size_d[3];
  wire [TL_AIW-1:0] a_source_d[3];
  wire  [TL_AW-1:0] a_address_d[3];
  wire [TL_DBW-1:0] a_mask_d[3];
  wire  [TL_DW-1:0] a_data_d[3];

  wire              d_valid_d[3];
  wire              d_ready_d[3];
  wire        [2:0] d_opcode_d[3];
  wire        [2:0] d_param_d[3];
  wire [TL_SZW-1:0] d_size_d[3];
  wire [TL_AIW-1:0] d_source_d[3];
  wire [TL_DIW-1:0] d_sink_d[3];
  wire  [TL_DW-1:0] d_data_d[3];
  wire              d_error_d[3];

  // address map:
  // 0x0 - 0x3fff ram0
  // 0x4000 - 0x7fff ram1
  // 0x8000 - 0xffffffff - default resp


  logic [1:0] switch;
  logic [1:0] value;
  logic       d_ack;
  wire       ready_for_grant;
  reg        granted;
  reg  [1:0] grant;

  assign ready_for_grant = d_valid_d[0] | d_valid_d[1] | d_valid_d[2];

  always_comb begin
    case(grant)
      2'h0: begin
          if (d_valid_d[1]) begin
            value = 1;
          end else if (d_valid_d[2]) begin
            value = 2;
          end else if (d_valid_d[0]) begin
            value = 0;
          end
        end
      2'h1: begin
          if (d_valid_d[2]) begin
            value = 2;
          end else if (d_valid_d[0]) begin
            value = 0;
          end else if (d_valid_d[1]) begin
            value = 1;
          end
        end
      2'h2: begin
          if (d_valid_d[0]) begin
            value = 0;
          end else if (d_valid_d[1]) begin
            value = 1;
          end else if (d_valid_d[2]) begin
            value = 2;
          end
        end
      default:
        value = 2;
    endcase
  end

  always_comb begin
    switch = 2;
    if (a_address < 32'h4000) begin
      switch = 0;
    end else if (a_address < 32'h8000) begin
      switch = 1;
    end
  end

  genvar i;
  generate
    for(i=0; i<3; i++) begin
      assign a_valid_d[i] = switch == i ? a_valid : 0;
      assign a_opcode_d[i] = switch == i ? a_opcode : 0;
      assign a_param_d[i] = switch == i ? a_param : 0;
      assign a_size_d[i] = switch == i ? a_size : 0;
      assign a_source_d[i] = switch == i ? a_source : 0;
      assign a_address_d[i] = switch == i ? a_address : 0;
      assign a_mask_d[i] = switch == i ? a_mask : 0;
      assign a_data_d[i] = switch == i ? a_data : 0;
    end
  endgenerate

  assign a_ready = a_ready_d[switch];

  assign d_valid = d_valid_d[grant] & granted;
  assign d_ready_d[0] = grant == 0 ? d_ready : 0;
  assign d_ready_d[1] = grant == 1 ? d_ready : 0;
  assign d_ready_d[2] = grant == 2 ? d_ready : 0;
  assign d_opcode = d_opcode_d[grant];
  assign d_param = d_param_d[grant];
  assign d_size = d_size_d[grant];
  assign d_source = d_source_d[grant];
  assign d_sink = d_sink_d[grant];
  assign d_data = d_data_d[grant];
  assign d_error = d_error_d[grant];
  assign d_ack = d_valid_d[grant] & d_ready;

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      granted <= 0;
    end else if (!granted & ready_for_grant) begin
      granted <= 1;
    end else if (d_ack) begin
      granted <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      grant <= 0;
    end else if (!granted & ready_for_grant) begin
      grant <= value;
    end
  end

  TLUL_ram ram0_u(
    .clk,
    .rstn,

    .a_valid(a_valid_d[0]),
    .a_ready(a_ready_d[0]),
    .a_opcode(a_opcode_d[0]),
    .a_param(a_param_d[0]),
    .a_size(a_size_d[0]),
    .a_source(a_source_d[0]),
    .a_address(a_address_d[0]),
    .a_mask(a_mask_d[0]),
    .a_data(a_data_d[0]),

    .d_valid(d_valid_d[0]),
    .d_ready(d_ready_d[0]),
    .d_opcode(d_opcode_d[0]),
    .d_param(d_param_d[0]),
    .d_size(d_size_d[0]),
    .d_source(d_source_d[0]),
    .d_sink(d_sink_d[0]),
    .d_data(d_data_d[0]),
    .d_error(d_error_d[0])
  );

  TLUL_ram ram1_u(
    .clk,
    .rstn,

    .a_valid(a_valid_d[1]),
    .a_ready(a_ready_d[1]),
    .a_opcode(a_opcode_d[1]),
    .a_param(a_param_d[1]),
    .a_size(a_size_d[1]),
    .a_source(a_source_d[1]),
    .a_address(a_address_d[1]),
    .a_mask(a_mask_d[1]),
    .a_data(a_data_d[1]),

    .d_valid(d_valid_d[1]),
    .d_ready(d_ready_d[1]),
    .d_opcode(d_opcode_d[1]),
    .d_param(d_param_d[1]),
    .d_size(d_size_d[1]),
    .d_source(d_source_d[1]),
    .d_sink(d_sink_d[1]),
    .d_data(d_data_d[1]),
    .d_error(d_error_d[1])
  );

  TLUL_default default_u2(
    .clk,
    .rstn,

    .a_valid(a_valid_d[2]),
    .a_ready(a_ready_d[2]),
    .a_opcode(a_opcode_d[2]),
    .a_param(a_param_d[2]),
    .a_size(a_size_d[2]),
    .a_source(a_source_d[2]),
    .a_address(a_address_d[2]),
    .a_mask(a_mask_d[2]),
    .a_data(a_data_d[2]),

    .d_valid(d_valid_d[2]),
    .d_ready(d_ready_d[2]),
    .d_opcode(d_opcode_d[2]),
    .d_param(d_param_d[2]),
    .d_size(d_size_d[2]),
    .d_source(d_source_d[2]),
    .d_sink(d_sink_d[2]),
    .d_data(d_data_d[2]),
    .d_error(d_error_d[2])
  );

  `ifdef COCOTB_SIM
  initial begin
    $dumpfile ("waveforms.vcd");
    $dumpvars;
  end
  `endif
endmodule
