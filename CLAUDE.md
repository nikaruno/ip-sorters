# ip-sorters

FPGA IP project. Before doing anything, read this file, then docs/progress.md,
docs/spec.md (requirements) and docs/tasks.md (plan). The spec is the source of
truth; if something is ambiguous or seems wrong, ask instead of guessing.

## How we work: checkpoints
- Work on exactly ONE task from docs/tasks.md per request. When it is done, STOP
  and wait for the user's approval. Never start the next task on your own.
- A task is done only when all three are true:
  1. `make -C sim regress` passes (or the subset the task names) and the report
     is regenerated;
  2. a handover entry is appended to docs/progress.md (format below);
  3. the work is committed in ONE commit: `<task id>: <short summary>`.
- If a task is bigger than expected, stop, commit what works, and propose a split.
- If something fails and you cannot fix it, stop and report. Never weaken a
  check, raise a tolerance or delete a test to make it pass.
- When the user says the session is ending, update docs/progress.md with the
  current state and the next concrete step, even mid-task.

### Handover entry (append to docs/progress.md)
    ## <task id> - <title> (<date>)
    - Changed: files added/modified, one line each
    - Verify: exact commands the user should run
    - Look at: which report rows / waveform signals to check, and what they should show
    - Test-the-test: the bug you injected and which check caught it (reverted, not committed)
    - Doubts: assumptions, open spec questions, anything you are unsure about

## Environment
- Running in a devenv Docker container (Ubuntu 22.04); the project is at /repo.
- Vivado is mounted read-only; its version is in $VIVADO_VER (set per machine).
- ALWAYS run Xilinx tools through the wrapper: `xrun <tool> <args>` (xvlog,
  xvhdl, xelab, xsim, vivado). Never source settings64.sh yourself.
- No GUI, no DISPLAY. Vivado only in `-mode batch` or `-mode tcl`.
- License error: stop and tell the user; licensing is handled outside the
  container. Never search for, read or change license files.
- The user runs the Vivado GUI on the host, from a different path. Every script
  must find files relative to its own location; never hardcode /repo or any
  absolute path.
- Python 3 with numpy, Pillow and matplotlib is available. No pip installs.

## Layout
    rtl/            IP sources (synthesizable only)
    ip/             Xilinx IP sources (.xci), committed; generated output goes to build/
    tb/directed/    directed and image testbenches
    tb/uvm/         UVM environment (only if the spec asks for it)
    model/          Python golden model, written from docs/spec.md, NOT from the RTL
    test/images/    input images (user-owned, read-only)
    test/expected/  hand-checked references (user-owned, read-only)
    scripts/        run_images.py, make_report.py (template infrastructure),
                    open_sim.tcl, project/synth scripts
    sim/            Makefile, run_xsim.sh, file lists (rtl.f, directed.f, uvm.f)
    sim/wave/       saved waveform layouts (.wcfg), committed
    docs/           spec.md (user-owned), tasks.md, progress.md, course/
    build/          ALL generated output (logs, .wdb, images, report); never
                    commit, safe to delete; nothing generated goes anywhere else

## Do not change without asking
docs/spec.md, test/images/, test/expected/, and every file the spec lists as
user-provided. If you believe a user-provided RTL file has a bug, report it with
evidence (failing check, simulation time) and propose the fix as a separate task.
sim/run_xsim.sh, scripts/run_images.py and scripts/make_report.py are shared
template infrastructure: if they lack something, propose the change instead of
editing them. In sim/Makefile, edit only the "Project settings" block.

## Make targets (sim/Makefile)
    make -C sim directed                    directed testbenches (DIRECTED_TOPS)
    make -C sim uvm TEST=<test> SEED=<n>    one UVM test
    make -C sim uvm-all                     every UVM test with every seed
    make -C sim images                      image tests (IMAGE_TOP) -> build/images/
    make -C sim report                      build/report/index.html
    make -C sim regress                     all of the above + summary table + report;
                                            non-zero exit on any failure
    make -C sim clean                       remove build/
Options: WAVES=1 (save .wdb), SIM_TIMEOUT=<s>. File lists: one path per line,
relative to the repo root, in compile order; VHDL is compiled before SV.

### Image tests (full contract: header of scripts/run_images.py)
- Inputs: test/images/<name>.png (one image, streamed IMAGE_FRAMES times) or
  test/images/<name>/ (a sequence of frames, sorted by file name).
- Image testbench (IMAGE_TOP): in its working directory it reads in.hex and
  writes out.hex (line 1 "<width> <height> <frames>", then one hex pixel per
  line); it prints `METRIC frame=<n> <key>=<int> ...` for the IP's key numbers
  (e.g. gain, offset, histogram min/max) and `RESULT: PASS` once out.hex is
  complete.
- Golden model, model/golden.py: `process(frames, in_bits, out_bits) ->
  (out_frames, metrics)`, with the same metric keys the testbench prints.
- Pass means every pixel of every frame is within IMAGE_TOLERANCE (default 0,
  bit-exact) and fits IMAGE_OUT_BITS. These settings must match docs/spec.md.

## Pass criteria
- Every testbench is self-checking and ends by printing exactly one line
  `RESULT: PASS` or `RESULT: FAIL` (sim/run_xsim.sh looks for it).
- A test passes only if its log has the PASS line, no ERROR, FATAL, UVM_ERROR
  or UVM_FATAL, no assertion failures, and (for UVM) the scoreboard reports all
  expected items matched. Always check the log; never report a pass from the
  exit code alone. "No errors printed" is not a pass.

## Waveform layouts
For every testbench the user may open, keep sim/wave/<tb>.wcfg with signal
groups: AXI-Stream in, control/config, internal state/statistics, AXI-Stream
out. Pixels in unsigned radix. scripts/open_sim.tcl opens it. Simulation .wdb
files go to build/.

## XSIM / UVM notes
- VHDL: `xrun xvhdl` (set VHDL_OPTS = --2008 if needed); SystemVerilog:
  `xrun xvlog -sv`; mixed language is fine.
- UVM: compile with `xrun xvlog -sv -L uvm`, elaborate with
  `xrun xelab -L uvm -timescale 1ns/1ps -debug typical`.
- Always elaborate with `-debug typical` so waveforms can be opened.
- In every UVM file: `import uvm_pkg::*;` and `` `include "uvm_macros.svh" ``.
- Never use SV reserved words as identifiers (checker, property, sequence,
  config, cover, ...).
- XSIM is picky with `local::` in inline constraints and with some advanced
  constraint/coverage constructs; if rejected, use a simpler equivalent and
  leave a short comment explaining why.
- On xsim SIGSEGV, first suspect null handles (failed uvm_config_db get) and a
  missing `super.build_phase()`.

## Coding rules
- RTL: synthesizable, single clock `aclk`, sync active-low `aresetn` unless the
  spec says otherwise; no latches, no initial blocks, no `#` delays.
- One module/entity/class per file; file name = module/entity/class name.
- Keep the directed test and the image tests passing after every RTL change.

## Writing
All documents, code comments and commit messages in English. docs/course/ is
for an engineer new to this IP: explain why, not only what.
