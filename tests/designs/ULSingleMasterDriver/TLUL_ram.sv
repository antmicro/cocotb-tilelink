module TLUL_ram #(
  parameter MAX_DELAY=4,
  parameter TL_AW=32,
  parameter TL_DW=32,
  parameter TL_AIW=8,
  parameter TL_DIW=1,
  parameter TL_DBW=(TL_DW>>3),
  parameter TL_SZW=$clog2($clog2(TL_DBW)+1),
  parameter ADDR_BITS=12
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
  localparam DELAY_SIZE = $clog2(MAX_DELAY);
  localparam ADDR_BITS_LEFT = TL_AW - ADDR_BITS - 2;

  wire                  a_ack,
                        d_ack;
  wire [ADDR_BITS-1:0]  line_addr;
  reg  [ADDR_BITS-1:0]  line_addr_q;
  wire           [1:0]  bank_addr;
  reg            [1:0]  bank_addr_q;
  wire                  rd, wr;
  reg                   rd_q, wr_q;
  reg      [TL_DW-1:0]  data_q,
                        return_value_q;
  reg     [TL_DBW-1:0]  mask_q;
  reg     [TL_AIW-1:0]  source_q;
  reg     [TL_SZW-1:0]  size_q;
  reg            [2:0]  param_q;

  reg            [7:0]  mem [2**ADDR_BITS][4];

  reg [DELAY_SIZE-1:0] a_wait,
                       a_count;
  reg [DELAY_SIZE-1:0] d_wait,
                       d_count;

  reg [1:0]             trans;

  initial begin
    for(int i=0; i < 2**ADDR_BITS; i++) begin
      mem[i][0] = 0;
      mem[i][1] = 0;
      mem[i][2] = 0;
      mem[i][3] = 0;
    end
  end

  assign a_ready = (a_count == a_wait) & (trans == 2'h1) & a_valid;
  assign a_ack = a_ready & a_valid;

  assign d_valid = trans == 2'h3 & (d_count == d_wait);
  assign d_ack = d_valid & d_ready;
  assign d_opcode = rd_q ? 3'h1 : 3'h0;
  assign d_param = param_q;
  assign d_size = size_q;
  assign d_source = source_q;
  assign d_sink = 0;
  assign d_data = rd_q ? return_value_q : 0;
  assign d_error = 0;

  assign line_addr = a_address[2+:ADDR_BITS];
  assign bank_addr = a_address[0+:2];
  assign rd        = a_opcode == 3'h4;
  assign wr        = a_opcode != 3'h4;

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      return_value_q <= 0;
    end else if (rd_q && trans == 2'h2) begin
      case(size_q)
        2'h0: begin
            case(bank_addr_q)
              2'h0: begin
                  if(mask_q[0])
                    return_value_q [ 7: 0] <= mem[line_addr_q][0];
                end
              2'h1: begin
                  if(mask_q[1])
                    return_value_q [15: 8] <= mem[line_addr_q][1];
                end
              2'h2: begin
                  if(mask_q[2])
                    return_value_q [23:16] <= mem[line_addr_q][2];
                end
              2'h3: begin
                  if(mask_q[3])
                    return_value_q [31:24] <= mem[line_addr_q][3];
                end
              default:;
            endcase
          end
        2'h1: begin
            case(bank_addr_q)
              2'h0: begin
                  if(mask_q[0])
                    return_value_q [ 7: 0] <= mem[line_addr_q][0];
                  if(mask_q[1])
                    return_value_q [15: 8] <= mem[line_addr_q][1];
                end
              2'h2: begin
                  if(mask_q[2])
                    return_value_q [23:16] <= mem[line_addr_q][2];
                  if(mask_q[3])
                    return_value_q [31:24] <= mem[line_addr_q][3];

                end
              default: ;
            endcase
          end
        2'h2: begin
            if(mask_q[0])
              return_value_q [ 7: 0] <= mem[line_addr_q][0];
            if(mask_q[1])
              return_value_q [15: 8] <= mem[line_addr_q][1];
            if(mask_q[2])
              return_value_q [23:16] <= mem[line_addr_q][2];
            if(mask_q[3])
              return_value_q [31:24] <= mem[line_addr_q][3];
          end
        default: begin end
      endcase
    end else if(wr_q && trans == 2'h2) begin
      case(size_q)
        2'h0: begin
            case(bank_addr_q)
              2'h0: begin
                  if(mask_q[0])
                    mem[line_addr_q][0] <= data_q[ 7: 0];
                end
              2'h1: begin
                  if(mask_q[1])
                    mem[line_addr_q][1] <= data_q[15: 8];
                end
              2'h2: begin
                  if(mask_q[2])
                    mem[line_addr_q][2] <= data_q[23:16];
                end
              2'h3: begin
                  if(mask_q[3])
                    mem[line_addr_q][3] <= data_q[31:24];
                end
              default:;
            endcase
          end
        2'h1: begin
            case(bank_addr_q)
              2'h0: begin
                  if(mask_q[0])
                    mem[line_addr_q][0] <= data_q[ 7: 0];
                  if(mask_q[1])
                    mem[line_addr_q][1] <= data_q[15: 8];
                end
              2'h2: begin
                  if(mask_q[2])
                    mem[line_addr_q][2] <= data_q[23:16];
                  if(mask_q[3])
                    mem[line_addr_q][3] <= data_q[31:24];
                end
              default: ;
            endcase
          end
        2'h2: begin
            if(mask_q[0])
              mem[line_addr_q][0] <= data_q[ 7: 0];
            if(mask_q[1])
              mem[line_addr_q][1] <= data_q[15: 8];
            if(mask_q[2])
              mem[line_addr_q][2] <= data_q[23:16];
            if(mask_q[3])
              mem[line_addr_q][3] <= data_q[31:24];
          end
        default: begin end
      endcase
    end else if(d_ack) begin
      return_value_q <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      trans <= 0;
    end else if(a_valid && trans == 2'h0) begin
      trans <= 2'h1;
    end else if(a_ack) begin
      trans <= 2'h2;
    end else if(trans == 2'h2) begin
      trans <= 2'h3;
    end else if(d_ack || (!a_valid && trans == 2'h1)) begin
      trans <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      a_wait <= 0;
    end else if(a_valid && trans == 2'h0) begin
      a_wait <= DELAY_SIZE'($urandom_range(0, MAX_DELAY-1));
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      a_count <= 0;
    end else if (trans == 2'h1 && a_count < a_wait) begin
      a_count <= a_count + 1;
    end else if (a_ack || (!a_valid && trans == 2'h1)) begin
      a_count <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      d_wait <= 0;
      end else if(trans == 2'h2) begin
      d_wait <= DELAY_SIZE'($urandom_range(0, MAX_DELAY-1));
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      d_count <= 0;
    end else if (trans == 2'h3 && d_count < d_wait) begin
      d_count <= d_count + 1;
    end else if (d_ack) begin
      d_count <= 0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      data_q <= 0;
    end else if (a_ack) begin
      data_q <= a_data;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      source_q <= 0;
    end else if (a_ack) begin
      source_q <= a_source;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      mask_q <= 0;
    end else if (a_ack) begin
      mask_q <= a_mask;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      size_q <= 0;
    end else if (a_ack) begin
      size_q <= a_size;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      param_q <= 0;
    end else if (a_ack) begin
      param_q <= a_param;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      rd_q <= 0;
    end else if (a_ack) begin
      rd_q <= rd;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      wr_q <= 0;
    end else if (a_ack) begin
      wr_q <= wr;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      line_addr_q <= 0;
    end else if (a_ack) begin
      line_addr_q <= line_addr;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if(!rstn) begin
      bank_addr_q <= 0;
    end else if (a_ack) begin
      bank_addr_q <= bank_addr;
    end
  end
endmodule
