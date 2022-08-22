module top #(
  parameter TL_AW=32,
  parameter TL_DW=32,
  parameter TL_AIW=8,
  parameter TL_DIW=1,
  parameter TL_DBW=(TL_DW>>3),
  parameter TL_SZW=$clog2($clog2(TL_DBW)+1)
)(
  input  wire       clk,
  input  wire       rstn
);
  `ifdef COCOTB_SIM
  initial begin
    $dumpfile ("waveforms.vcd");
    $dumpvars;
  end
  `endif
endmodule
