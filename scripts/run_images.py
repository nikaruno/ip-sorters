#!/usr/bin/env python3
"""run_images.py - run every test image through the RTL image testbench and the
golden model, compare them, and write build/images/<name>/.

Called by `make -C sim images` after the image testbench has been built into
build/sim/images/. Settings come from the environment (set in sim/Makefile):
  IMAGE_FRAMES     frames per test when the test is a single image file (default 1)
  IMAGE_OUT_BITS   bit depth of the output pixels (default: same as the input)
  IMAGE_TOLERANCE  max allowed |rtl - golden| per pixel (default 0 = bit-exact)

Inputs, test/images/:
  <name>.png|.pgm|.tif|.bmp   one grayscale image, streamed IMAGE_FRAMES times
  <name>/                     a sequence: every image file inside, sorted by name
  Colour images are converted to 8-bit grayscale (noted in the result).

Testbench contract (IMAGE_TOP). Its working directory is build/sim/images/.
  reads  in.hex   line 1: "<width> <height> <frames>" in decimal, then one pixel
                  per line in hex, row-major, frame after frame
  writes out.hex  same format; the output size may differ from the input
  prints "METRIC frame=<n> <key>=<int> ..." lines (optional), and
         "RESULT: PASS" once out.hex is completely written

Golden model contract, model/golden.py (written from docs/spec.md, not the RTL):
  process(frames, in_bits, out_bits) -> (out_frames, metrics)
    frames      list of 2-D numpy uint16 arrays, one per frame
    out_frames  list of 2-D integer numpy arrays
    metrics     list of dicts, one per frame, with the keys the TB prints

Output, build/images/<name>/:
  input.png rtl.png golden.png   the LAST frame (steady state for frame-to-frame IPs)
  diff.png                       |rtl - golden| of the last frame; black = equal
  frames/                        every frame, when there is more than one
  in.hex out.hex sim.log         raw exchange files and the simulation log
  result.json                    see the end of run_test()
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("BUILD", ROOT / "build"))
SIM_DIR = BUILD / "sim" / "images"
OUT_DIR = BUILD / "images"
RUNNER = ROOT / "sim" / "run_xsim.sh"
IMAGE_EXT = {".png", ".pgm", ".ppm", ".tif", ".tiff", ".bmp"}

FRAMES = int(os.environ.get("IMAGE_FRAMES") or 1)
OUT_BITS_ENV = os.environ.get("IMAGE_OUT_BITS") or ""
TOLERANCE = int(os.environ.get("IMAGE_TOLERANCE") or 0)


# ---------------------------------------------------------------- image I/O
def load_gray(path):
    """Return (uint16 array, bit depth 8|16, note)."""
    img = Image.open(path)
    note = ""
    if img.mode in ("I;16", "I;16B", "I;16L", "I"):
        a = np.array(img).astype(np.int64)
        if a.min() < 0 or a.max() > 0xFFFF:
            raise ValueError(f"{path.name}: pixel values outside 0..65535")
        return a.astype(np.uint16), 16, note
    if img.mode != "L":
        note = f"converted from {img.mode} to 8-bit grayscale"
        img = img.convert("L")
    return np.array(img).astype(np.uint16), 8, note


def save_png(arr, bits, path):
    a = np.asarray(arr).astype(np.int64)
    if bits <= 8:
        Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), mode="L").save(path)
    else:
        Image.fromarray(np.clip(a, 0, 65535).astype(np.uint16)).save(path)


def write_hex(frames, path):
    h, w = frames[0].shape
    digits = 4 if max(int(f.max()) for f in frames) > 0xFF else 2
    with open(path, "w") as f:
        f.write(f"{w} {h} {len(frames)}\n")
        for fr in frames:
            f.write("\n".join(f"{int(v):0{digits}x}" for v in fr.ravel()))
            f.write("\n")


def read_hex(path):
    with open(path) as f:
        header = f.readline().split()
        if len(header) != 3:
            raise ValueError(f"out.hex header must be '<width> <height> <frames>', got {header}")
        w, h, n = (int(x) for x in header)
        vals = [int(t, 16) for line in f for t in line.split()]
    if len(vals) != w * h * n:
        raise ValueError(f"out.hex has {len(vals)} pixels, header says {w}x{h}x{n} = {w * h * n}")
    a = np.array(vals, dtype=np.int64).reshape(n, h, w)
    return [a[i] for i in range(n)]


def parse_metrics(log_text):
    """'METRIC frame=0 gain=123 ...' lines -> list of dicts indexed by frame."""
    by_frame = {}
    for line in log_text.splitlines():
        m = re.match(r"^\s*METRIC\s+(.*)$", line)
        if not m:
            continue
        kv = dict(t.split("=", 1) for t in m.group(1).split() if "=" in t)
        try:
            frame = int(kv.pop("frame"), 0)
            by_frame.setdefault(frame, {}).update({k: int(v, 0) for k, v in kv.items()})
        except (KeyError, ValueError):
            continue
    return [by_frame.get(i, {}) for i in range(max(by_frame) + 1)] if by_frame else []


# ---------------------------------------------------------------- helpers
def find_tests():
    tests = []
    for p in sorted((ROOT / "test" / "images").iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT)
            if files:
                tests.append((p.name, files, False))
        elif p.suffix.lower() in IMAGE_EXT:
            tests.append((p.stem, [p], True))
    return tests


def load_golden():
    path = ROOT / "model" / "golden.py"
    if not path.exists():
        return None, "model/golden.py not found"
    try:
        spec = importlib.util.spec_from_file_location("golden", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "process"):
            return None, "model/golden.py has no process() function"
        return mod, ""
    except Exception as e:  # noqa: BLE001 - report any model import error
        return None, f"model/golden.py failed to import: {e!r}"


def record(status, name, detail):
    subprocess.run([str(RUNNER), "record", status, f"images/{name}", detail], check=False)


def diff_rgb(diff):
    """Black where equal, red (brighter = larger) where different."""
    d = np.abs(diff).astype(np.int64)
    rgb = np.zeros(d.shape + (3,), dtype=np.uint8)
    if d.max() > 0:
        rgb[..., 0] = np.where(d > 0, np.maximum(80, d * 255 // d.max()), 0)
    return Image.fromarray(rgb, mode="RGB")


# ---------------------------------------------------------------- one test
def run_test(name, files, repeat, golden, golden_err):
    out = OUT_DIR / name
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    res = {"name": name, "pass": False, "error": "", "note": "", "tolerance": TOLERANCE}

    def finish(reason=""):
        res["error"] = reason
        (out / "result.json").write_text(json.dumps(res, indent=2))
        if res["pass"]:
            record("PASS", name, f"max_abs_diff={res['max_abs_diff']} build/images/{name}/")
        else:
            record("FAIL", name, f"{reason} (build/images/{name}/)")
        return res["pass"]

    # 1. inputs
    try:
        loaded = [load_gray(f) for f in files]
    except Exception as e:  # noqa: BLE001
        return finish(f"cannot read input: {e}")
    frames = [a for a, _, _ in loaded]
    in_bits = max(b for _, b, _ in loaded)
    res["note"] = "; ".join(sorted({n for _, _, n in loaded if n}))
    if len({f.shape for f in frames}) != 1:
        return finish("frames in the sequence have different sizes")
    if repeat:
        frames = frames * FRAMES
    out_bits = int(OUT_BITS_ENV) if OUT_BITS_ENV else in_bits
    h, w = frames[0].shape
    res.update(width=w, height=h, frames=len(frames), in_bits=in_bits, out_bits=out_bits,
               source=[str(f.relative_to(ROOT)) for f in files])
    save_png(frames[-1], in_bits, out / "input.png")
    write_hex(frames, out / "in.hex")

    # 2. RTL
    rtl, rtl_metrics, sim_err = None, [], ""
    shutil.copy(out / "in.hex", SIM_DIR / "in.hex")
    (SIM_DIR / "out.hex").unlink(missing_ok=True)
    run = subprocess.run([str(RUNNER), "run", "images", name], env={**os.environ, "RECORD": "0"},
                         capture_output=True, text=True, check=False)
    log = SIM_DIR / f"{name}.log"
    if log.exists():
        shutil.copy(log, out / "sim.log")
        rtl_metrics = parse_metrics(log.read_text(errors="replace"))
    if run.returncode != 0:
        last = (run.stdout.strip().splitlines() or ["simulation failed"])[-1]
        sim_err = "simulation: " + re.sub(r"^FAIL\s+\S+\s+", "", last)
    elif not (SIM_DIR / "out.hex").exists():
        sim_err = "simulation passed but wrote no out.hex"
    else:
        shutil.copy(SIM_DIR / "out.hex", out / "out.hex")
        try:
            rtl = read_hex(out / "out.hex")
            save_png(rtl[-1], out_bits, out / "rtl.png")
        except Exception as e:  # noqa: BLE001
            sim_err = f"bad out.hex: {e}"

    # 3. golden model
    gold, gold_metrics, gold_err = None, [], golden_err
    if golden is not None:
        try:
            g_frames, gold_metrics = golden.process([f.copy() for f in frames], in_bits, out_bits)
            gold = [np.asarray(g).astype(np.int64) for g in g_frames]
            gold_metrics = list(gold_metrics or [])
            save_png(gold[-1], out_bits, out / "golden.png")
        except Exception as e:  # noqa: BLE001
            gold_err = f"golden model raised {e!r}"
    res["metrics"] = {"rtl": rtl_metrics, "golden": gold_metrics}

    # 4. compare
    if sim_err or gold_err:
        return finish(sim_err or gold_err)
    shapes_r = [f.shape for f in rtl]
    shapes_g = [f.shape for f in gold]
    if shapes_r != shapes_g:
        return finish(f"size mismatch: rtl {len(rtl)} frames {shapes_r[0]}, "
                      f"golden {len(gold)} frames {shapes_g[0]} (rows, cols)")
    limit = (1 << out_bits) - 1
    for label, seq in (("rtl", rtl), ("golden", gold)):
        lo, hi = min(int(f.min()) for f in seq), max(int(f.max()) for f in seq)
        if lo < 0 or hi > limit:
            return finish(f"{label} output range {lo}..{hi} does not fit {out_bits} bits "
                          f"(set IMAGE_OUT_BITS in sim/Makefile?)")
    diffs = [r - g for r, g in zip(rtl, gold)]
    per_frame = [int(np.abs(d).max()) for d in diffs]
    bad = [int((np.abs(d) > TOLERANCE).sum()) for d in diffs]
    res.update(max_abs_diff=max(per_frame), max_abs_diff_per_frame=per_frame,
               mismatches=sum(bad), mismatches_per_frame=bad, first_mismatch=None)
    for i, d in enumerate(diffs):
        ys, xs = np.nonzero(np.abs(d) > TOLERANCE)
        if len(ys):
            y, x = int(ys[0]), int(xs[0])
            res["first_mismatch"] = {"frame": i, "x": x, "y": y, "rtl": int(rtl[i][y, x]),
                                     "golden": int(gold[i][y, x]), "pixel_index": y * shapes_r[i][1] + x}
            break
    diff_rgb(diffs[-1]).save(out / "diff.png")
    if len(frames) > 1:
        (out / "frames").mkdir()
        for i in range(len(frames)):
            save_png(frames[i], in_bits, out / "frames" / f"{i:03d}_input.png")
            save_png(rtl[i], out_bits, out / "frames" / f"{i:03d}_rtl.png")
            save_png(gold[i], out_bits, out / "frames" / f"{i:03d}_golden.png")
    res["pass"] = res["mismatches"] == 0
    if res["pass"]:
        return finish()
    fm = res["first_mismatch"]
    return finish(f"{res['mismatches']} pixels differ (max {res['max_abs_diff']}); first at "
                  f"frame {fm['frame']} x={fm['x']} y={fm['y']}: rtl={fm['rtl']} golden={fm['golden']}")


def main():
    if not (SIM_DIR / "xsim.dir" / "snap").exists():
        print("run_images: image testbench not built (build/sim/images/)", file=sys.stderr)
        return 1
    tests = find_tests()
    if not tests:
        record("SKIP", "(none)", "no images in test/images/")
        return 0
    golden, golden_err = load_golden()
    results = [run_test(n, f, r, golden, golden_err) for n, f, r in tests]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
