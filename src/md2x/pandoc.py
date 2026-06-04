"""Build the pandoc invocation from resolved config."""
from __future__ import annotations

from pathlib import Path


def build_pandoc_cmd(input_md: Path, output_pdf: Path, cfg: dict,
                     pandoc_bin: str, xelatex_bin: str) -> list[str]:
    cmd: list[str] = [
        pandoc_bin, str(input_md),
        "-o", str(output_pdf),
        f"--pdf-engine={xelatex_bin}",
        "-V", f"geometry:margin={cfg['page']['margin']}",
        "-V", f"fontsize={cfg['page']['fontsize']}",
        "-V", f"papersize={cfg['page']['paper']}",
        "-V", f"linestretch={cfg['page']['line_spacing']}",
        "-V", "colorlinks=true",
        "-V", f"linkcolor={cfg['colors']['link']}",
        "-V", f"urlcolor={cfg['colors']['url']}",
        "-V", f"toccolor={cfg['colors']['toc']}",
        f"--highlight-style={cfg['code']['highlight_style']}",
    ]
    # Only pass font vars when explicitly set — otherwise xelatex uses
    # its built-in Computer Modern (no fontspec lookup needed).
    if cfg["fonts"].get("main"):
        cmd += ["-V", f"mainfont={cfg['fonts']['main']}"]
    if cfg["fonts"].get("sans"):
        cmd += ["-V", f"sansfont={cfg['fonts']['sans']}"]
    if cfg["fonts"].get("mono"):
        cmd += ["-V", f"monofont={cfg['fonts']['mono']}"]
    if cfg["page"]["orientation"] == "landscape":
        cmd += ["-V", "classoption=landscape"]
    if cfg["output"]["toc"]:
        cmd += ["--toc", f"--toc-depth={cfg['output']['toc_depth']}"]
    if cfg["output"]["number_sections"]:
        cmd.append("--number-sections")
    if cfg["output"]["citation_processing"]:
        cmd.append("--citeproc")
    if cfg["fonts"].get("cjk"):
        cmd += ["-V", f"CJKmainfont={cfg['fonts']['cjk']}"]
    if cfg["code"]["line_numbers"]:
        cmd.append("--listings")
    hi = cfg["advanced"].get("header_includes", [])
    if hi:
        cmd += ["-V", "header-includes=" + "".join(hi)]
    cmd += cfg["advanced"].get("pandoc_extra_args", [])
    return cmd
