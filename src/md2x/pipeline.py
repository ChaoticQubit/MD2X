"""End-to-end build: render diagrams, rewrite markdown, run pandoc."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

from .binaries import resolve_binary
from .renderers import render_into_markdown, MermaidRenderError
from .pandoc import build_cmd
from .formats import detect_target


_QUARANTINE_ATTR = "com.apple.quarantine"


def _strip_quarantine(path: Path) -> None:
    """Best-effort removal of the macOS com.apple.quarantine xattr from a file md2x wrote.

    When md2x's output carries com.apple.quarantine, Gatekeeper shows a spurious
    "<file> could not be verified ... free of malware" warning the first time the
    user opens it. The file is md2x's own product, so clear the flag.

    Self-contained and silent: removes the attribute through libSystem's
    removexattr(2) directly, so it works on a stock macOS with no Command Line
    Tools and without spawning a process; falls back to the `xattr` CLI only if
    the direct call is unavailable. Never raises — cleanup must not fail a build
    that already succeeded. (os.removexattr is Linux-only in CPython and absent
    on macOS, so the libSystem call is the portable primitive here.)

    Only clears quarantine present when the build finishes; a flag applied
    afterwards — e.g. iCloud Drive re-materialising the file — is outside our
    control.
    """
    if sys.platform != "darwin":
        return
    try:
        libc = ctypes.CDLL("libSystem.B.dylib", use_errno=True)
        libc.removexattr.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int)
        libc.removexattr.restype = ctypes.c_int
        # options=0 -> follow symlinks to the real file. A missing attribute
        # (ENOATTR) just returns -1, which we deliberately ignore.
        libc.removexattr(os.fsencode(str(path)), _QUARANTINE_ATTR.encode(), 0)
        return
    except Exception:
        pass
    try:
        subprocess.run(
            ["/usr/bin/xattr", "-d", _QUARANTINE_ATTR, str(path)],
            capture_output=True,
            check=False,
        )
    except OSError:
        pass


def build(md_path: Path, out_path: Path, cfg: dict) -> int:
    """
    Builds a target document from a Markdown source: renders Mermaid diagrams, rewrites the Markdown, runs Pandoc, and optionally emits a manifest and cleans intermediates.
    
    Parameters:
        md_path (Path): Path to the input Markdown file.
        out_path (Path): Path for the generated output file.
        cfg (dict): Configuration dictionary controlling binaries, image and Mermaid handling, output format, and advanced options.
    
    Returns:
        int: `0` on success, or the Pandoc process exit code on failure.
    
    Raises:
        SystemExit: If overwrite is disallowed and the output exists; if required binaries (pandoc, or xelatex when the chosen target needs it) are missing; or if a Mermaid block fails to render and `cfg["mermaid"]["on_failure"]` is set to `"error"`.
    """
    md_path = md_path.resolve()
    out_path = out_path.resolve()
    target = detect_target(out_path, cfg["output"].get("format"))
    work_dir = md_path.parent

    if cfg["advanced"].get("no_clobber") and out_path.exists():
        sys.exit(f"refusing to overwrite existing file (no_clobber): {out_path}")

    bins = cfg["binaries"]
    pandoc_bin  = resolve_binary("pandoc",  bins.get("pandoc"))
    xelatex_bin = resolve_binary("xelatex", bins.get("xelatex"))
    mmdc_bin    = resolve_binary("mmdc",    bins.get("mmdc"))
    dot_bin     = resolve_binary("dot",     bins.get("dot"))

    if not pandoc_bin:
        sys.exit("ERROR: pandoc not found. Run ./install.sh")
    if target.needs_xelatex and not xelatex_bin:
        sys.exit("ERROR: xelatex not found (required for PDF). "
                 "Run ./install.sh, or choose another format with --to.")
    if not mmdc_bin and not dot_bin:
        sys.stderr.write("WARN: neither mmdc nor dot found — Mermaid blocks "
                         "will be kept as code blocks.\n")

    print(f"[md2x] pandoc:  {pandoc_bin}")
    if target.needs_xelatex:
        print(f"[md2x] xelatex: {xelatex_bin}")
    print(f"[md2x] mmdc:    {mmdc_bin or '(none)'}")
    print(f"[md2x] dot:     {dot_bin or '(none)'}")

    md = md_path.read_text(encoding="utf-8")
    try:
        rewritten, manifest = render_into_markdown(
            md, work_dir, cfg, mmdc_bin, dot_bin
        )
    except MermaidRenderError as e:
        sys.exit(f"ERROR: {e}.")

    print(f"[md2x] found {len(manifest)} mermaid blocks in {md_path.name}")
    policy = cfg["mermaid"]["on_failure"]
    for entry in manifest:
        if entry["ok"]:
            print(f"  [{entry['index']:02d}] {entry['renderer']} "
                  f"→ {Path(entry['png']).name}")
        elif policy == "omit":
            print(f"  [{entry['index']:02d}] OMITTED (no renderer succeeded)")
        else:
            print(f"  [{entry['index']:02d}] WARN: kept source; "
                  f"no renderer succeeded")

    tmp_md = work_dir / (md_path.stem + "._md2x.md")
    tmp_md.write_text(rewritten, encoding="utf-8")

    cmd = build_cmd(tmp_md, out_path, cfg, target, pandoc_bin, xelatex_bin)
    print(f"[md2x] running pandoc …")
    res = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr or res.stdout or "")
        return res.returncode
    _strip_quarantine(out_path)
    print(f"[md2x] wrote {out_path} ({out_path.stat().st_size} bytes)")

    if cfg["advanced"].get("emit_manifest"):
        man_path = work_dir / (md_path.stem + "._md2x.json")
        man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[md2x] manifest → {man_path}")

    if not cfg["advanced"].get("keep_intermediate"):
        try:
            tmp_md.unlink()
        except OSError:
            pass
    return 0
