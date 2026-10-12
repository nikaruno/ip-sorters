# ip-sorters - Tasks

One task per request. At the end of a task: tests pass, the report is
regenerated, docs/progress.md gets a handover entry, and everything goes into
ONE commit. Then STOP and wait for approval (see CLAUDE.md).

Adjust this list to the project before starting: drop what does not apply, split
what is too big, and mark tasks that need user input. Keep the status column up
to date: todo / doing / done.

| id | task | status |
|----|------|--------|
| T0 | Environment check | todo |
| T1 | Spec review: questions and assumptions | todo |
| T2 | Golden model from the spec | todo |
| T3 | Image testbench and first RTL vs model comparison | todo |
| T4 | Directed tests for the corner cases | todo |
| T5 | Waveform layout for the GUI | todo |
| T6 | UVM environment (only if the spec asks for it) | todo |
| T7 | Out-of-context synthesis check | todo |
| T8 | docs/course/ | todo |
| T9 | Publishable repo: README and project regeneration | todo |

## T0 - Environment check
Check `xrun vivado -version`, run `make -C sim regress` (everything is empty, so
it must end in REGRESSION: FAIL with only SKIP lines), and confirm
build/report/index.html is generated. Report the Vivado version and any problem.
No source files yet.

## T1 - Spec review: questions and assumptions
Read docs/spec.md and every file it lists as user-provided. Write into
docs/progress.md: what you understood, the assumptions you would make, and the
open questions, most important first. Propose changes to this task list. Write
no RTL, no testbench, no model.

## T2 - Golden model from the spec
Write model/golden.py (`process(frames, in_bits, out_bits)`) from docs/spec.md
only - not from the RTL, so that the model can disagree with it. Add a small
self-check (a few hand-computed values, e.g. a flat image) that runs under
python3 and prints RESULT: PASS. Explain in the handover which lines of the spec
each formula comes from.

## T3 - Image testbench and first RTL vs model comparison
Write tb/directed/tb_<ip>_img.sv (contract in CLAUDE.md), fill sim/rtl.f and
sim/directed.f, set the Project settings block in sim/Makefile (IMAGE_TOP,
IMAGE_FRAMES, IMAGE_OUT_BITS, IMAGE_TOLERANCE). Run `make -C sim images` on the
images in test/images/ and report the result. Differences between RTL and model
are findings to report, not something to fix by changing the model or raising
the tolerance.

## T4 - Directed tests for the corner cases
One self-checking directed test per corner case in the spec (section 7), each
ending with RESULT: PASS/FAIL. Add the tops to DIRECTED_TOPS. Test-the-test:
break one RTL detail, show which test catches it, revert it.

## T5 - Waveform layout for the GUI
Create sim/wave/<tb>.wcfg for the image testbench and the most useful directed
test, with the signal groups listed in CLAUDE.md. Verify that
`vivado -source scripts/open_sim.tcl -tclargs <tb>` works on the host, and write
in the handover which signals to watch and what they should show.

## T6 - UVM environment
Only if docs/spec.md asks for it: agent, scoreboard against the golden model,
randomised frame sizes and back-pressure. Fill sim/uvm.f, UVM_TOP and UVM_TESTS.

## T7 - Out-of-context synthesis check
Synthesise the IP out of context for the target part in the spec, and report
timing (met or not, worst slack) and resources (LUT, FF, BRAM, DSP). Script it
under scripts/ so the user can rerun it.

## T8 - docs/course/
Short English documents for an engineer new to this IP: the algorithm and why it
is done this way, the hardware trade-offs, a walkthrough of the RTL, and how the
verification works. Split across files with a numbered prefix (01-, 02-, ...).

## T9 - Publishable repo
README.md (what it is, how to simulate, how to regenerate), scripts to rebuild
the Vivado project and any Xilinx IP from source, and a check that a fresh clone
plus `make -C sim regress` works.
