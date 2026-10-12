# open_sim.tcl - open a testbench in the Vivado GUI, on the HOST.
#
#   cd <project root>
#   vivado -source scripts/open_sim.tcl                  # first directed TB
#   vivado -source scripts/open_sim.tcl -tclargs tb_foo  # a specific TB
#   vivado -source scripts/open_sim.tcl -tclargs tb_img grad
#                                        # image TB, fed with build/images/grad/in.hex
#
# It builds a throwaway project in build/vivado_sim/ from the same file lists
# the batch flow uses (sim/rtl.f + sim/directed.f, or sim/uvm.f when the top is
# UVM_TOP), launches behavioral simulation, loads sim/wave/<top>.wcfg if it
# exists, and runs to the end.
#
# After arranging signals in the GUI: File > Simulation Waveform > Save
# Configuration As... -> sim/wave/<top>.wcfg, and commit that file.
#
# The FPGA part comes from $env(SIM_PART), else the default below.

set script_dir [file normalize [file dirname [info script]]]
set root       [file normalize $script_dir/..]
set part       [expr {[info exists ::env(SIM_PART)] ? $::env(SIM_PART) : "xc7z020clg400-1"}]

proc mk_var {name} {
    # read one variable out of sim/Makefile ("NAME ?= value")
    global root
    set path $root/sim/Makefile
    if {![file exists $path]} { return "" }
    set fh [open $path r]; set text [read $fh]; close $fh
    foreach line [split $text \n] {
        if {[regexp "^\\s*$name\\s*\\??=\\s*(.*)\$" $line -> value]} {
            return [string trim [regsub {#.*$} $value ""]]
        }
    }
    return ""
}

proc read_flist {name} {
    # -> {files incdirs}; same rules as sim/run_xsim.sh
    global root
    set files {}; set incdirs {}
    set path $root/sim/$name
    if {![file exists $path]} { return [list $files $incdirs] }
    set fh [open $path r]; set text [read $fh]; close $fh
    foreach line [split $text \n] {
        set line [string trim [regsub {#.*$} $line ""]]
        if {$line eq ""} { continue }
        if {[string match "+incdir+*" $line]} {
            lappend incdirs [file normalize $root/[string range $line 8 end]]
        } else {
            lappend files [file normalize $root/$line]
        }
    }
    return [list $files $incdirs]
}

# ---- what to simulate --------------------------------------------------------
set top   [lindex $argv 0]
set image [lindex $argv 1]
set uvm_top [mk_var UVM_TOP]
if {$top eq ""} {
    set top [lindex [mk_var DIRECTED_TOPS] 0]
    if {$top eq ""} { set top [mk_var IMAGE_TOP] }
}
if {$top eq ""} {
    puts "open_sim: no testbench given and DIRECTED_TOPS/IMAGE_TOP are empty in sim/Makefile"
    return
}
set is_uvm [expr {$uvm_top ne "" && $top eq $uvm_top}]

lassign [read_flist rtl.f] rtl_files rtl_inc
lassign [read_flist [expr {$is_uvm ? "uvm.f" : "directed.f"}]] tb_files tb_inc
set incdirs [concat $rtl_inc $tb_inc]
if {[llength $rtl_files] + [llength $tb_files] == 0} {
    puts "open_sim: sim/rtl.f and the testbench list are empty"
    return
}
foreach f [concat $rtl_files $tb_files] {
    if {![file exists $f]} { puts "open_sim: file not found: $f"; return }
}

# ---- project -----------------------------------------------------------------
set proj_dir $root/build/vivado_sim
file delete -force $proj_dir
create_project -force sim_gui $proj_dir -part $part
if {[llength $rtl_files]} { add_files -norecurse $rtl_files }
if {[llength $tb_files]}  { add_files -fileset sim_1 -norecurse $tb_files }

if {[string first "2008" [mk_var VHDL_OPTS]] >= 0} {
    foreach f [concat $rtl_files $tb_files] {
        if {[string match -nocase "*.vhd*" $f]} {
            catch { set_property FILE_TYPE {VHDL 2008} [get_files $f] }
        }
    }
}
if {[llength $incdirs]} {
    set_property include_dirs $incdirs [get_filesets sim_1]
}
if {$is_uvm} {
    set_property -name {xsim.compile.xvlog.more_options} -value {-L uvm} -objects [get_filesets sim_1]
    set_property -name {xsim.elaborate.xelab.more_options} -value {-L uvm} -objects [get_filesets sim_1]
    if {$image ne ""} {
        set_property -name {xsim.simulate.xsim.more_options} \
            -value "-testplusarg UVM_TESTNAME=$image" -objects [get_filesets sim_1]
    }
}
set_property top $top [get_filesets sim_1]
set_property top_lib xil_defaultlib [get_filesets sim_1]
update_compile_order -fileset sim_1

# ---- image input -------------------------------------------------------------
# The simulation's working directory; an image TB reads in.hex from there.
set run_dir $proj_dir/sim_gui.sim/sim_1/behav/xsim
if {$image ne "" && !$is_uvm} {
    set src $root/build/images/$image/in.hex
    if {![file exists $src]} {
        puts "open_sim: $src not found - run 'make -C sim images' first"
        return
    }
    file mkdir $run_dir
    file copy -force $src $run_dir/in.hex
    puts "open_sim: fed build/images/$image/in.hex to the simulation"
}

# ---- run ---------------------------------------------------------------------
launch_simulation
set wcfg $root/sim/wave/$top.wcfg
if {[file exists $wcfg]} {
    open_wave_config $wcfg
    puts "open_sim: loaded sim/wave/$top.wcfg"
} else {
    catch { log_wave -recursive * }
    puts "open_sim: no sim/wave/$top.wcfg yet - arrange the signals, then"
    puts "          File > Simulation Waveform > Save Configuration As... -> sim/wave/$top.wcfg"
}
run all
puts "open_sim: $top finished; check the Tcl console for RESULT: PASS/FAIL"
