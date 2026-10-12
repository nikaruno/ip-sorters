# ip-sorters - Specification

Owner: the user. Claude may read it and ask questions, but must not change it
without being asked. If the RTL and this document disagree, this document wins
until the user says otherwise.

## 1. Purpose
What the IP does, in two or three sentences, and where it sits in the pipeline.

## 2. Files provided by the user
- rtl/ : sources that came from the user, and their state (working, untested,
  known issues). Claude reports bugs in them instead of rewriting them.
- ip/  : Xilinx IP (.xci), one line each: which IP, which configuration, what it
  is used for. These must be generated before simulation; the generated output
  belongs in build/ and is never committed.
- test/images/ : the test images, and what each one is meant to catch.

## 3. Interfaces
- Clock / reset:
- AXI4-Stream slave (input): data width, TUSER/TLAST meaning, TREADY behaviour
- AXI4-Stream master (output): same
- Control / configuration (registers, generics, static pins):

## 4. Parameters and generics
| Name | Range | Default | Meaning |
|------|-------|---------|---------|

## 5. Behaviour
Pixel format and bit depth in and out. Frame size: fixed, generic, or taken from
TUSER/TLAST, and the maximum supported. What happens to a frame that breaks the
limits (truncate, drop, flag, undefined). What is computed, and exactly how
(formulas, rounding, saturation, fixed-point Q formats). Which frame a result
applies to (the same frame or the next one). Buffering and whether back-to-back
frames are supported. Reset behaviour, including reset in mid-frame, and what
happens on the very first frame.

## 6. Latency and throughput
Pixels per clock, pipeline or frame latency, back-pressure behaviour (may TREADY
deassert mid-frame?), minimum blanking between frames.

## 7. Corner cases that must be tested
For example: smallest and largest frame, non-square frame, single row, single
pixel, flat image, saturated image, back-pressure, reset in mid-frame, short
blanking, first frame, two frames back to back.

## 8. Verification settings
These must match the "Project settings" block in sim/Makefile:
- IMAGE_FRAMES: (at least 2 if frames interact or are pipelined)
- IMAGE_OUT_BITS:
- IMAGE_TOLERANCE: 0 (bit-exact) unless stated otherwise, with the reason
- Golden model notes: what model/golden.py must implement, and anything it is
  allowed to simplify

## 9. Target and constraints
- FPGA part: xc7z020clg400-1        <- change only if this project differs
  (same value for the GUI: SIM_PART, and for the .xci files and synthesis)
- Target clock:
- Resource limits (LUT, FF, BRAM, DSP):
- Out-of-context synthesis must pass: yes / no

## 10. Out of scope
What this IP explicitly does not do.
