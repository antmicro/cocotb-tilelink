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

  input  wire              first_a_valid,
  output wire              first_a_ready,
  input  wire        [2:0] first_a_opcode,
  input  wire        [2:0] first_a_param,
  input  wire [TL_SZW-1:0] first_a_size,
  input  wire [TL_AIW-1:0] first_a_source,
  input  wire  [TL_AW-1:0] first_a_address,
  input  wire [TL_DBW-1:0] first_a_mask,
  input  wire  [TL_DW-1:0] first_a_data,

  output wire              first_d_valid,
  input  wire              first_d_ready,
  output wire        [2:0] first_d_opcode,
  output wire        [2:0] first_d_param,
  output wire [TL_SZW-1:0] first_d_size,
  output wire [TL_AIW-1:0] first_d_source,
  output wire [TL_DIW-1:0] first_d_sink,
  output wire  [TL_DW-1:0] first_d_data,
  output wire              first_d_error,

  input  wire              second_a_valid,
  output wire              second_a_ready,
  input  wire        [2:0] second_a_opcode,
  input  wire        [2:0] second_a_param,
  input  wire [TL_SZW-1:0] second_a_size,
  input  wire [TL_AIW-1:0] second_a_source,
  input  wire  [TL_AW-1:0] second_a_address,
  input  wire [TL_DBW-1:0] second_a_mask,
  input  wire  [TL_DW-1:0] second_a_data,

  output wire              second_d_valid,
  input  wire              second_d_ready,
  output wire        [2:0] second_d_opcode,
  output wire        [2:0] second_d_param,
  output wire [TL_SZW-1:0] second_d_size,
  output wire [TL_AIW-1:0] second_d_source,
  output wire [TL_DIW-1:0] second_d_sink,
  output wire  [TL_DW-1:0] second_d_data,
  output wire              second_d_error
);
  reg   [TL_DW-1:0] storage[2];

  reg               first_d_valid_reg;
  reg               second_d_valid_reg;

  wire first_a_ack, first_d_ack;
  assign first_a_ack = first_a_ready & first_a_valid;
  assign first_d_ack = first_d_ready & first_d_valid;
  assign first_a_ready = first_a_valid & (!first_d_valid_reg | first_d_ready);
  assign first_d_valid = first_d_valid_reg;

  wire second_a_ack, second_d_ack;
  assign second_a_ack = second_a_ready & second_a_valid;
  assign second_d_ack = second_d_ready & second_d_valid;
  assign second_a_ready = second_a_valid & (!second_d_valid_reg | second_d_ready);
  assign second_d_valid = second_d_valid_reg;

  wire first_rd, first_wr;
  reg               first_rd_q, first_wr_q;
  reg        [2:0]  first_a_param_q;
  reg [TL_SZW-1:0]  first_a_size_q;
  reg [TL_AIW-1:0]  first_a_source_q;
  reg  [TL_DW-1:0]  first_d_data_q;

  assign first_rd  = (first_a_opcode == 3'h4) & first_a_ack;
  assign first_wr  = (first_a_opcode != 3'h4) & first_a_ack;
  wire   [TL_DW-1:0] first_masked_data;
  assign  first_masked_data[0+:8] = first_a_mask[0] ? first_a_data[0+:8] : '0;
  assign  first_masked_data[8+:8] = first_a_mask[1] ? first_a_data[8+:8] : '0;
  assign  first_masked_data[16+:8] = first_a_mask[2] ? first_a_data[16+:8] : '0;
  assign  first_masked_data[24+:8] = first_a_mask[3] ? first_a_data[24+:8] : '0;

  wire second_rd, second_wr;
  reg               second_rd_q, second_wr_q;
  reg        [2:0]  second_a_param_q;
  reg [TL_SZW-1:0]  second_a_size_q;
  reg [TL_AIW-1:0]  second_a_source_q;
  reg  [TL_DW-1:0]  second_d_data_q;

  assign second_rd = (second_a_opcode == 3'h4) & second_a_ack;
  assign second_wr = (second_a_opcode != 3'h4) & second_a_ack;
  wire   [TL_DW-1:0] second_masked_data;
  assign  second_masked_data[0+:8] = second_a_mask[0] ? second_a_data[0+:8] : '0;
  assign  second_masked_data[8+:8] = second_a_mask[1] ? second_a_data[8+:8] : '0;
  assign  second_masked_data[16+:8] = second_a_mask[2] ? second_a_data[16+:8] : '0;
  assign  second_masked_data[24+:8] = second_a_mask[3] ? second_a_data[24+:8] : '0;

  assign first_d_opcode = first_rd_q ? 3'h1 : 3'h0;
  assign first_d_param = first_a_param_q;
  assign first_d_size = first_a_size_q;
  assign first_d_source = first_a_source_q;
  assign first_d_sink = '0;
  assign first_d_data = first_d_data_q;
  assign first_d_error = 1'b0;

  assign second_d_opcode = second_rd_q ? 3'h1 : 3'h0;
  assign second_d_param = second_a_param_q;
  assign second_d_size = second_a_size_q;
  assign second_d_source = second_a_source_q;
  assign second_d_sink = '0;
  assign second_d_data = second_d_data_q;
  assign second_d_error = 1'b0;

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      first_d_valid_reg <= 1'b0;
    end else if(first_a_ack & !first_d_valid_reg) begin
      first_d_valid_reg <= 1'b1;
    end else if(!first_a_ack & first_d_ack) begin
      first_d_valid_reg <= 1'b0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      first_rd_q <= 1'b0;
    end else if(first_a_ack) begin
      first_rd_q <= first_rd;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      first_a_param_q <= '0;
    end else if(first_a_ack) begin
      first_a_param_q <= first_a_param;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      first_a_size_q <= '0;
    end else if(first_a_ack) begin
      first_a_size_q <= first_a_size;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      first_a_source_q <= '0;
    end else if(first_a_ack) begin
      first_a_source_q <= first_a_source;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      second_d_valid_reg <= 1'b0;
    end else if(second_a_ack & !second_d_valid_reg) begin
      second_d_valid_reg <= 1'b1;
    end else if(!second_a_ack & second_d_ack) begin
      second_d_valid_reg <= 1'b0;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      second_rd_q <= 1'b0;
    end else if(second_a_ack) begin
      second_rd_q <= second_rd;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      second_a_param_q <= '0;
    end else if(second_a_ack) begin
      second_a_param_q <= second_a_param;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      second_a_size_q <= '0;
    end else if(second_a_ack) begin
      second_a_size_q <= second_a_size;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      second_a_source_q <= '0;
    end else if(second_a_ack) begin
      second_a_source_q <= second_a_source;
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      storage[0] <= 0;
      second_d_data_q <= '0;
    end else if (first_wr & first_a_ack) begin
      second_d_data_q <= '0;
      case(first_a_size)
        2'h0: begin
          case (first_a_address[1:0])
            2'h0:
              storage[0] <= {storage[0][31-:24], first_masked_data[0+:8]};
            2'h1:
              storage[0] <= {storage[0][31-:16], first_masked_data[8+:8], storage[0][0+:8]};
            2'h2:
              storage[0] <= {storage[0][31-:8], first_masked_data[16+:8], storage[0][0+:16]};
            2'h3:
              storage[0] <= {first_masked_data[24+:8], storage[0][0+:24]};
          endcase
        end
        2'h1: begin
          case (first_a_address[1:0])
            2'h0:
              storage[0] <= {storage[0][31-:16], first_masked_data[0+:16]};
            2'h2:
              storage[0] <= {first_masked_data[16+:16], storage[0][0+:16]};
            default: ;
          endcase
        end
        2'h2: begin
          case (first_a_address[1:0])
            2'h0:
              storage[0] <= first_masked_data;
            default: ;
          endcase
        end
        default: begin
        end
      endcase
    end else if (second_rd & second_a_ack) begin
      case(second_a_size)
        2'h0: begin
          case (second_a_address[1:0])
            2'h0:
              second_d_data_q <= {24'h0, storage[0][0+:8]};
            2'h1:
              second_d_data_q <= {16'h0, storage[0][8+:8], 8'h0};
            2'h2:
              second_d_data_q <= {8'h0, storage[0][16+:8], 16'h0};
            2'h3:
              second_d_data_q <= {storage[0][24+:8], 24'h0};
          endcase
        end
        2'h1: begin
          case (second_a_address[1:0])
            2'h0:
              second_d_data_q <= {16'h0, storage[0][0+:16]};
            2'h2:
              second_d_data_q <= {storage[0][16+:16], 16'h0};
            default: ;
          endcase
        end
        2'h2: begin
          case (second_a_address[1:0])
            2'h0:
              second_d_data_q <= storage[0];
            default: ;
          endcase
        end
        default: begin
        end
      endcase
    end
  end

  always_ff @(posedge clk or negedge rstn) begin
    if (!rstn) begin
      storage[1] <= 0;
      first_d_data_q <= '0;
    end else if (second_wr) begin
      first_d_data_q <= '0;
      case(second_a_size)
        2'h0: begin
          case (second_a_address[1:0])
            2'h0:
              storage[1] <= {storage[1][31-:24], second_masked_data[0+:8]};
            2'h1:
              storage[1] <= {storage[1][31-:16], second_masked_data[8+:8], storage[1][0+:8]};
            2'h2:
              storage[1] <= {storage[1][31-:8], second_masked_data[16+:8], storage[1][0+:16]};
            2'h3:
              storage[1] <= {second_masked_data[24+:8], storage[1][0+:24]};
          endcase
        end
        2'h1: begin
          case (second_a_address[1:0])
            2'h0:
              storage[1] <= {storage[0][31-:16], second_masked_data[0+:16]};
            2'h2:
              storage[1] <= {second_masked_data[16+:16], storage[0][0+:16]};
            default: ;
          endcase
        end
        2'h2: begin
          case (second_a_address[1:0])
            2'h0:
              storage[1] <= second_masked_data;
            default: ;
          endcase
        end
        default: begin
        end
      endcase
    end else if (first_rd & first_a_ack) begin
      case(first_a_size)
        2'h0: begin
          case (first_a_address[1:0])
            2'h0:
              first_d_data_q <= {24'h0, storage[1][0+:8]};
            2'h1:
              first_d_data_q <= {16'h0, storage[1][8+:8], 8'h0};
            2'h2:
              first_d_data_q <= {8'h0, storage[1][16+:8], 16'h0};
            2'h3:
              first_d_data_q <= {storage[1][24+:8], 24'h0};
          endcase
        end
        2'h1: begin
          case (first_a_address[1:0])
            2'h0:
              first_d_data_q <= {16'h0, storage[1][0+:16]};
            2'h2:
              first_d_data_q <= {storage[1][16+:16], 16'h0};
            default: ;
          endcase
        end
        2'h2: begin
          case (first_a_address[1:0])
            2'h0:
              first_d_data_q <= storage[1];
            default: ;
          endcase
        end
        default: begin
        end
      endcase
    end
  end

  `ifdef COCOTB_SIM
  initial begin
    $dumpfile ("waveforms.vcd");
    $dumpvars;
  end
  `endif
endmodule
