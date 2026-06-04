"""End-to-end build: render diagrams, rewrite markdown, run pandoc."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .binaries import resolve_binary
from .mermaid import MERMAID_RE, extract_caption
from .renderers import render_block
from .pandoc import build_pandoc_cmd


def build(md_path: Path, out_path: Path, cfg: dict) -> int:
    md_path = md_path.resolve()
    out_path = out_path.resolve()
    work_dir = md_path.parent
    diag_dir = work_dir / "diagrams"
    diag_dir.mkdir(exist_ok=True)

    if cfg["advanced"].get("no_clobber") and out_path.exists():
        sys.exit(f"refusing to overwrite existing file (no_clobber): {out_path}")

    bins = cfg["binaries"]
    pandoc_bin  = resolve_binary("pandoc",  bins.get("pandoc"))
    xelatex_bin = resolve_binary("xelatex", bins.get("xelatex"))
    mmdc_bin    = resolve_binary("mmdc",    bins.get("mmdc"))
    dot_bin     = resolve_binary("dot",     bins.get("dot"))

    if not pandoc_bin:
        sys.exit("ERROR: pandoc not found. Run ./install.sh")
    if not xelatex_bin:
        sys.exit("ERROR: xelatex not found. Run ./install.sh")
    if not mmdc_bin and not dot_bin:
        sys.stderr.write("WARN: neither mmdc nor dot found — Mermaid blocks "
                         "will be kept as code blocks.\n")

    print(f"[md2x] pandoc:  {pandoc_bin}")
    print(f"[md2x] xelatex: {xelatex_bin}")
    print(f"[md2x] mmdc:    {mmdc_bin or '(none)'}")
    print(f"[md2x] dot:     {dot_bin or '(none)'}")

    md = md_path.read_text(encoding="utf-8")
    blocks = list(MERMAID_RE.finditer(md))
    print(f"[md2x] found {len(blocks)} mermaid blocks in {md_path.name}")

    chunks: list[str] = []
    last_end = 0
    manifest: list[dict] = []

    for idx, m in enumerate(blocks, 1):
        chunks.append(md[last_end:m.start()])
        src = m.group(1)
        png = diag_dir / f"mermaid_{idx:02d}.png"
        ok, renderer = render_block(src, png, cfg, mmdc_bin, dot_bin)
        caption = extract_caption(src, f"Diagram {idx}")
        manifest.append({
            "index": idx, "renderer": renderer, "ok": ok,
            "caption": caption, "png": str(png.relative_to(work_dir)),
        })

        if ok:
            rel = png.relative_to(work_dir).as_posix()
            chunks.append(
                f"\n![{caption}]({rel}){{width={cfg['images']['width']}}}\n"
            )
            if cfg["images"]["show_captions"]:
                prefix = cfg["images"]["caption_prefix"]
                if prefix:
                    chunks.append(f"\n*{prefix} {idx}: {caption}.*\n")
                else:
                    chunks.append(f"\n*{caption}.*\n")
            print(f"  [{idx:02d}] {renderer} → {png.name}")
        else:
            policy = cfg["mermaid"]["on_failure"]
            if policy == "error":
                sys.exit(f"ERROR: failed to render mermaid block {idx}.")
            elif policy == "omit":
                print(f"  [{idx:02d}] OMITTED (no renderer succeeded)")
            else:
                chunks.append(
                    f"\n*[Diagram {idx} — Mermaid source preserved; "
                    f"renderer unavailable]*\n\n```\n{src}\n```\n"
                )
                print(f"  [{idx:02d}] WARN: kept source; no renderer succeeded")
        last_end = m.end()

    chunks.append(md[last_end:])
    rewritten = "".join(chunks)

    tmp_md = work_dir / (md_path.stem + "._md2x.md")
    tmp_md.write_text(rewritten, encoding="utf-8")

    cmd = build_pandoc_cmd(tmp_md, out_path, cfg, pandoc_bin, xelatex_bin)
    print(f"[md2x] running pandoc …")
    res = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr or res.stdout or "")
        return res.returncode
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
