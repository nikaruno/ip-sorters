#!/usr/bin/env python3
"""make_report.py - build/report/index.html: one self-contained page (images
embedded) with the regression summary and one card per image test.

Reads build/results.txt (from `make -C sim regress`) and build/images/*/
(from scripts/run_images.py). Open the page in any browser; it needs no
network and can be copied or attached as a single file.
"""
import base64
import datetime
import html
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("BUILD", ROOT / "build"))
IMAGES = BUILD / "images"
REPORT = BUILD / "report" / "index.html"
esc = html.escape


def b64_png_file(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def b64_png_pil(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def load_array(path):
    return np.array(Image.open(path)).astype(np.int64)


def stretched(path):
    """Contrast-stretched 8-bit view (0.5..99.5 percentile), for looking only."""
    a = load_array(path)
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    if hi <= lo:
        hi = lo + 1
    return Image.fromarray(np.clip((a - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8), mode="L")


def histogram(d, res):
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.6), dpi=90)
    if (d / "input.png").exists():
        a = load_array(d / "input.png")
        axes[0].hist(a.ravel(), bins=256, range=(0, 2 ** res.get("in_bits", 8)), color="#555")
    axes[0].set_title(f"input ({res.get('in_bits', '?')}-bit)", fontsize=9)
    rng = (0, 2 ** res.get("out_bits", 8))
    for fname, label, color in (("golden.png", "golden", "#2a7"), ("rtl.png", "rtl", "#d33")):
        if (d / fname).exists():
            axes[1].hist(load_array(d / fname).ravel(), bins=256, range=rng, histtype="step",
                         color=color, label=label)
    axes[1].set_title(f"output ({res.get('out_bits', '?')}-bit)", fontsize=9)
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.tick_params(labelsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def metrics_table(m):
    rtl, gold = m.get("rtl", []), m.get("golden", [])
    if not rtl and not gold:
        return "<p class='muted'>No metrics (TB prints <code>METRIC frame=&lt;n&gt; key=value</code>).</p>"
    keys = sorted({k for f in rtl + gold for k in f})
    head = "".join(f"<th colspan=2>{esc(k)}</th>" for k in keys)
    sub = "".join("<th>rtl</th><th>golden</th>" for _ in keys)
    rows = []
    for i in range(max(len(rtl), len(gold))):
        r = rtl[i] if i < len(rtl) else {}
        g = gold[i] if i < len(gold) else {}
        cells = []
        for k in keys:
            rv, gv = r.get(k, "–"), g.get(k, "–")
            cls = " class='bad'" if rv != gv else ""
            cells.append(f"<td{cls}>{esc(str(rv))}</td><td{cls}>{esc(str(gv))}</td>")
        rows.append(f"<tr><td>{i}</td>{''.join(cells)}</tr>")
    return (f"<table class='metrics'><tr><th rowspan=2>frame</th>{head}</tr><tr>{sub}</tr>"
            f"{''.join(rows)}</table>")


def image_card(d):
    res = json.loads((d / "result.json").read_text())
    ok = res.get("pass", False)
    w = res.get("width", 0)
    disp = f"width:{min(w * 2, 480)}px" if w else ""
    tiles = []
    if (d / "input.png").exists():
        tiles.append(("input (contrast-stretched, view only)", b64_png_pil(stretched(d / "input.png"))))
    for fname, label in (("rtl.png", "RTL output"), ("golden.png", "golden output"),
                         ("diff.png", "|rtl − golden| (black = equal)")):
        if (d / fname).exists():
            tiles.append((label, b64_png_file(d / fname)))
    tiles_html = "".join(f"<figure><img src='{src}' style='{disp}'><figcaption>{esc(lbl)}</figcaption></figure>"
                         for lbl, src in tiles)
    facts = [f"{res.get('width', '?')}×{res.get('height', '?')}, {res.get('frames', '?')} frame(s)",
             f"{res.get('in_bits', '?')}-bit in → {res.get('out_bits', '?')}-bit out",
             f"tolerance {res.get('tolerance', 0)}"]
    if "max_abs_diff" in res:
        facts.append(f"max |diff| {res['max_abs_diff']}, {res.get('mismatches', 0)} pixel(s) over tolerance")
    fm = res.get("first_mismatch")
    fm_html = ""
    if fm:
        fm_html = (f"<p class='bad'>First mismatch: frame {fm['frame']}, x={fm['x']}, y={fm['y']} "
                   f"(pixel #{fm['pixel_index']} of the frame): rtl={fm['rtl']}, golden={fm['golden']}. "
                   f"Use the pixel number to find the beat in the waveform.</p>")
    err = f"<p class='bad'>{esc(res['error'])}</p>" if res.get("error") and not fm else ""
    note = f"<p class='muted'>{esc(res['note'])}</p>" if res.get("note") else ""
    shown = " (last frame shown; all frames in frames/)" if res.get("frames", 1) > 1 else ""
    return f"""
<section class='card {"pass" if ok else "fail"}' id='{esc(res["name"])}'>
  <h2><span class='badge'>{"PASS" if ok else "FAIL"}</span> {esc(res["name"])}
      <small>{esc(", ".join(res.get("source", [])))}</small></h2>
  <p class='muted'>{esc(" · ".join(facts))}{esc(shown)}</p>
  {err}{fm_html}{note}
  <div class='tiles'>{tiles_html}</div>
  <img class='hist' src='{histogram(d, res)}'>
  {metrics_table(res.get("metrics", {}))}
  <p class='muted'>Files: build/images/{esc(res["name"])}/</p>
</section>"""


def git_info():
    try:
        rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return rev + (" + uncommitted changes" if dirty else "")
    except Exception:  # noqa: BLE001
        return "not a git repo"


CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--card:#f6f6f8;--pass:#1f8a4c;--fail:#c62828;--line:#ddd}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececef;--muted:#9a9aa0;--card:#222226;--line:#3a3a3f}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0 auto;max-width:1200px;padding:24px}
h1{margin:0 0 4px}h2{margin:0 0 6px;font-size:18px}h2 small{color:var(--muted);font-weight:400;font-size:12px;margin-left:8px}
.muted{color:var(--muted)}.bad{color:var(--fail)}code{font-size:12px}
.card{background:var(--card);border-left:6px solid var(--line);border-radius:8px;padding:16px;margin:16px 0}
.card.pass{border-left-color:var(--pass)}.card.fail{border-left-color:var(--fail)}
.badge{display:inline-block;color:#fff;border-radius:4px;padding:1px 8px;font-size:13px}
.pass .badge{background:var(--pass)}.fail .badge{background:var(--fail)}
.tiles{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0}
figure{margin:0}figure img{max-width:100%;image-rendering:pixelated;border:1px solid var(--line);background:#000}
figcaption{font-size:12px;color:var(--muted)}
img.hist{max-width:100%;background:#fff;border-radius:4px;margin:6px 0}
table{border-collapse:collapse;font-size:12px;margin:8px 0}td,th{border:1px solid var(--line);padding:3px 8px;text-align:right}
td.bad{background:rgba(198,40,40,.15)}
pre{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px}
.sum span{margin-right:16px;font-weight:600}
"""


def main():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    cards = sorted(d for d in IMAGES.glob("*") if (d / "result.json").exists()) if IMAGES.exists() else []
    card_html = "".join(image_card(d) for d in cards)
    n_pass = sum(json.loads((d / "result.json").read_text()).get("pass", False) for d in cards)
    results = BUILD / "results.txt"
    reg = results.read_text() if results.exists() else ""
    reg_lines = reg.splitlines()
    reg_pass = sum(line.startswith("PASS") for line in reg_lines)
    reg_fail = sum(line.startswith("FAIL") for line in reg_lines)
    overall = "FAIL" if reg_fail or (cards and n_pass < len(cards)) else ("PASS" if reg_pass or cards else "—")
    color = {"PASS": "var(--pass)", "FAIL": "var(--fail)"}.get(overall, "var(--muted)")
    page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{esc(ROOT.name)} – test report</title><style>{CSS}</style></head><body>
<h1>{esc(ROOT.name)} <span style='color:{color}'>{overall}</span></h1>
<p class='muted'>Generated {datetime.datetime.now():%Y-%m-%d %H:%M} · commit {esc(git_info())}</p>
<p class='sum'><span>Regression: {reg_pass} pass, {reg_fail} fail</span>
<span>Images: {n_pass}/{len(cards)} pass</span></p>
<h2>Regression results</h2>
<pre>{esc(reg) if reg else "No build/results.txt yet - run: make -C sim regress"}</pre>
<h2>Image tests</h2>
{card_html or "<p class='muted'>No image results yet - run: make -C sim images</p>"}
</body></html>"""
    REPORT.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
