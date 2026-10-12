#!/usr/bin/env bash
# run_xsim.sh - compile, elaborate and run XSIM, and judge the result.
# Called by sim/Makefile; you rarely need it directly.
#
#   run_xsim.sh build <name> <top> <list.f>...  compile + elaborate into build/sim/<name>/
#   run_xsim.sh run   <name> <run-id> [xsim args] run that snapshot, judge its log
#   run_xsim.sh skip  <name> <reason>             record a SKIP line
#   run_xsim.sh fail  <name> <reason>             record a FAIL line (exit 1)
#   run_xsim.sh record <PASS|FAIL|SKIP> <name> [detail]  record any line
#   run_xsim.sh summary                           print the results table; exit 1 on failure
#
# File lists (.f, in sim/): one path per line relative to the repo root, in
# compile order; '#' starts a comment; '+incdir+<dir>' adds an include dir.
# VHDL files are compiled first (xvhdl), then Verilog/SV (xvlog -sv).
#
# A run PASSES only if: the log has a line 'RESULT: PASS', no 'RESULT: FAIL',
# no ERROR/FATAL/FAILURE lines, no UVM_ERROR/UVM_FATAL messages or non-zero
# UVM summary counts, and xsim exited normally within SIM_TIMEOUT seconds.
#
# Environment: UVM=1 (add -L uvm), VHDL_OPTS (e.g. --2008), WAVES=1 (record
# all signals to build/sim/<name>/<run-id>.wdb), SIM_TIMEOUT (default 600),
# RECORD=0 (judge and print, but don't add the line to the results table).
set -uo pipefail
SIM="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ROOT="${ROOT:-$(dirname "$SIM")}"
BUILD="${BUILD:-$ROOT/build}"
RESULTS="$BUILD/results.txt"
XRUN="${XRUN:-xrun}"

record() {  # record <PASS|FAIL|SKIP> <name> <detail>; paths shown relative to the repo
  local detail="${3//$ROOT\//}"
  mkdir -p "$BUILD"
  [ "${RECORD:-1}" = 0 ] || printf '%-4s  %-40s  %s\n' "$1" "$2" "$detail" >> "$RESULTS"
  printf '%-4s  %-40s  %s\n' "$1" "$2" "$detail"
}

cmd_build() {
  local name="$1" top="$2"; shift 2
  local dir="$BUILD/sim/$name" line p
  local -a vhd=() sv=() inc=() uvm=()
  [ "${UVM:-0}" = 1 ] && uvm=(-L uvm)
  for f in "$@"; do
    [ -f "$SIM/$f" ] || { record FAIL "build:$name" "missing file list sim/$f"; return 1; }
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line%%#*}"; line="$(echo "$line" | xargs)"   # strip comment + whitespace
      [ -z "$line" ] && continue
      case "$line" in
        +incdir+*) inc+=(-i "$ROOT/${line#+incdir+}"); continue ;;
      esac
      p="$ROOT/$line"
      [ -f "$p" ] || { record FAIL "build:$name" "file not found: $line (in sim/$f)"; return 1; }
      case "$line" in
        *.vhd|*.vhdl) vhd+=("$p") ;;
        *.sv|*.v)     sv+=("$p") ;;
        *) record FAIL "build:$name" "unknown file type: $line"; return 1 ;;
      esac
    done < "$SIM/$f"
  done
  [ $(( ${#vhd[@]} + ${#sv[@]} )) -gt 0 ] || { record FAIL "build:$name" "file lists are empty: $*"; return 1; }

  rm -rf "$dir"; mkdir -p "$dir"; cd "$dir" || return 1
  echo "---- build $name (top: $top)"
  if [ ${#vhd[@]} -gt 0 ]; then
    # shellcheck disable=SC2086
    $XRUN xvhdl ${VHDL_OPTS:-} "${vhd[@]}" > compile_vhdl.log 2>&1 \
      || { record FAIL "build:$name" "VHDL compile error, see $dir/compile_vhdl.log"; return 1; }
  fi
  if [ ${#sv[@]} -gt 0 ]; then
    $XRUN xvlog -sv "${uvm[@]}" "${inc[@]}" "${sv[@]}" > compile_sv.log 2>&1 \
      || { record FAIL "build:$name" "SV compile error, see $dir/compile_sv.log"; return 1; }
  fi
  $XRUN xelab "${uvm[@]}" -debug typical -timescale 1ns/1ps "work.$top" -s snap > elab.log 2>&1 \
    || { record FAIL "build:$name" "elaboration error, see $dir/elab.log"; return 1; }
  return 0
}

cmd_run() {
  local name="$1" id="$2"; shift 2
  local dir="$BUILD/sim/$name" rc reason=""
  [ -d "$dir/xsim.dir/snap" ] || { record FAIL "$name/$id" "not built"; return 1; }
  cd "$dir" || return 1
  local log="$dir/$id.log" tcl="$dir/$id.tcl"
  local -a wdb=()
  if [ "${WAVES:-0}" = 1 ]; then
    printf 'log_wave -recursive *\nrun all\nquit\n' > "$tcl"; wdb=(-wdb "$dir/$id.wdb")
  else
    printf 'run all\nquit\n' > "$tcl"
  fi
  echo "---- run $name/$id"
  timeout "${SIM_TIMEOUT:-600}" $XRUN xsim snap -tclbatch "$tcl" -log "$log" "${wdb[@]}" "$@" > /dev/null 2>&1
  rc=$?
  if   [ "$rc" -eq 124 ];                                     then reason="timeout after ${SIM_TIMEOUT:-600}s"
  elif [ ! -f "$log" ];                                       then reason="no log written (xsim exit $rc)"
  elif grep -qE '^[[:space:]]*RESULT: FAIL' "$log";           then reason="testbench reported RESULT: FAIL"
  elif grep -qiE '^(error|fatal|failure)[: ]' "$log";         then reason="error/fatal line in log"
  elif grep -qE '^UVM_(ERROR|FATAL) [^:]' "$log";             then reason="UVM_ERROR/UVM_FATAL message"
  elif grep -qE '^UVM_(ERROR|FATAL) *: *[1-9]' "$log";        then reason="non-zero UVM error count"
  elif [ "$rc" -ne 0 ];                                       then reason="xsim exit code $rc"
  elif ! grep -qE '^[[:space:]]*RESULT: PASS' "$log";         then reason="no 'RESULT: PASS' line"
  fi
  if [ -n "$reason" ]; then record FAIL "$name/$id" "$reason ($log)"; return 1; fi
  record PASS "$name/$id" "$log"
}

cmd_summary() {
  [ -s "$RESULTS" ] || { echo "No results in $RESULTS"; echo "REGRESSION: FAIL"; return 1; }
  local p f s
  p=$(grep -c '^PASS' "$RESULTS" || true)
  f=$(grep -c '^FAIL' "$RESULTS" || true)
  s=$(grep -c '^SKIP' "$RESULTS" || true)
  echo
  echo "================================ REGRESSION SUMMARY ================================"
  cat "$RESULTS"
  echo "------------------------------------------------------------------------------------"
  echo "PASS $p   FAIL $f   SKIP $s"
  if [ "$f" -eq 0 ] && [ "$p" -gt 0 ]; then echo "REGRESSION: PASS"; return 0; fi
  echo "REGRESSION: FAIL"; return 1
}

cmd="${1:-}"; shift || true
case "$cmd" in
  build)   [ $# -ge 3 ] || { echo "usage: run_xsim.sh build <name> <top> <list.f>..." >&2; exit 2; }; cmd_build "$@" ;;
  run)     [ $# -ge 2 ] || { echo "usage: run_xsim.sh run <name> <run-id> [xsim args]" >&2; exit 2; }; cmd_run "$@" ;;
  skip)    record SKIP "$1" "${2:-}" ;;
  fail)    record FAIL "$1" "${2:-}"; exit 1 ;;
  record)  [ $# -ge 2 ] || { echo "usage: run_xsim.sh record <PASS|FAIL|SKIP> <name> [detail]" >&2; exit 2; }
           record "$1" "$2" "${3:-}" ;;
  summary) cmd_summary ;;
  *) sed -n '2,/^set /p' "$0" | grep '^#' >&2; exit 2 ;;
esac
