"""Build the pandoc invocation from resolved config."""
from __future__ import annotations

from pathlib import Path

from .formats import Target


def build_pandoc_cmd(input_md: Path, output_pdf: Path, cfg: dict,
                     pandoc_bin: str, xelatex_bin: str) -> list[str]:
    """
                     Builds the pandoc command-line arguments needed to render the given Markdown input to a PDF.
                     
                     Constructs an argument list that sets the PDF engine and applies page layout, fonts (including optional CJK), colors, code highlighting and line-numbering, table of contents and depth, section numbering, citation processing, header-includes, and any extra pandoc arguments taken from `cfg`.
                     
                     Parameters:
                         cfg (dict): Resolved configuration expected to contain:
                             - page: dict with keys `margin`, `fontsize`, `paper`, `line_spacing`, `orientation`
                             - colors: dict with keys `link`, `url`, `toc`
                             - code: dict with keys `highlight_style`, `line_numbers`
                             - fonts: dict with optional keys `main`, `sans`, `mono`, `cjk`
                             - output: dict with keys `toc` (bool), `toc_depth`, `number_sections` (bool), `citation_processing` (bool)
                             - advanced: dict with optional `header_includes` (list[str]) and `pandoc_extra_args` (list[str])
                     
                     Returns:
                         cmd (list[str]): The assembled pandoc CLI argument list for producing the PDF output.
                     """
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


def build_generic_cmd(input_md: Path, output: Path, cfg: dict,
                      pandoc_bin: str, target: Target) -> list[str]:
    """
                      Builds a pandoc command-line argument list for non-PDF output writers.
                      
                      Assembles only portable pandoc flags appropriate for writers such as docx, html, epub, and latex (writer selection, standalone, embed-resources, table of contents and depth, section numbering, citation processing, highlight style) and appends any `pandoc_extra_args` from the configuration.
                      
                      Parameters:
                          input_md (Path): Path to the input Markdown file.
                          output (Path): Path to the output file.
                          cfg (dict): Resolved configuration dictionary containing output, code, and advanced settings.
                          pandoc_bin (str): Path or name of the pandoc executable.
                          target (Target): Target descriptor with writer, standalone, and embed preferences.
                      
                      Returns:
                          list[str]: The list of pandoc command-line arguments to invoke.
                      """
    cmd: list[str] = [pandoc_bin, str(input_md), "-o", str(output)]
    if target.writer:
        cmd += ["-t", target.writer]
    if target.standalone:
        cmd.append("--standalone")
    if target.embed:
        cmd.append("--embed-resources")
    if cfg["output"]["toc"]:
        cmd += ["--toc", f"--toc-depth={cfg['output']['toc_depth']}"]
    if cfg["output"]["number_sections"]:
        cmd.append("--number-sections")
    if cfg["output"]["citation_processing"]:
        cmd.append("--citeproc")
    cmd.append(f"--highlight-style={cfg['code']['highlight_style']}")
    cmd += cfg["advanced"].get("pandoc_extra_args", [])
    return cmd


def build_cmd(input_md: Path, output: Path, cfg: dict, target: Target,
              pandoc_bin: str, xelatex_bin: str) -> list[str]:
    """
              Builds pandoc command-line arguments for the given output target by dispatching
              to the PDF-specific or generic command builder.
              
              Parameters:
                  input_md (Path): Path to the source Markdown file.
                  output (Path): Desired output path (file or directory depending on target).
                  cfg (dict): Resolved configuration dictionary used to derive pandoc flags.
                  target (Target): Target description; when target.name == "pdf" the PDF builder is used.
                  pandoc_bin (str): Path or executable name for the pandoc binary.
                  xelatex_bin (str): Path or executable name for the XeLaTeX binary (used for PDF builds).
              
              Returns:
                  list[str]: A list of pandoc command-line arguments ready to be executed.
              """
    if target.name == "pdf":
        return build_pandoc_cmd(input_md, output, cfg, pandoc_bin, xelatex_bin)
    return build_generic_cmd(input_md, output, cfg, pandoc_bin, target)
