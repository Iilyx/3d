"""CLI: case3 run notes.txt --prompt "…" → PDF/DOCX (+ Image API if enabled)."""

from __future__ import annotations

from case3.paths import repo_root

import argparse
import logging
import sys
from pathlib import Path

from case3.envfile import load_dotenv
from case3.llm_client import LLMConfigError, LLMError
from case3.parse_output import ParseError
from case3.render import RenderError


def _root() -> Path:
    return repo_root()


def _read_prompt(args: argparse.Namespace) -> str | None:
    if getattr(args, "prompt_file", None):
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if getattr(args, "prompt", None):
        return args.prompt
    return None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        prog="case3",
        description="Text + intent → LaTeX (+ Image API) → PDF/DOCX",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="source.txt → LLM → PDF/DOCX")
    p_run.add_argument("input", type=Path, help=".txt/.md source data")
    p_run.add_argument("--prompt", "-p", default=None, help="Intent in natural language")
    p_run.add_argument("--prompt-file", type=Path, default=None, help="Intent from file")
    p_run.add_argument(
        "--format",
        choices=("pdf", "docx", "both"),
        default="pdf",
        help="Primary artifact is PDF; DOCX is secondary (default: pdf)",
    )
    p_run.add_argument("--dry-run", action="store_true")

    p_gen = sub.add_parser("generate", help="Only LLM → .tex (+ figures.json)")
    p_gen.add_argument("input", type=Path)
    p_gen.add_argument("-o", "--output", type=Path, default=None)
    p_gen.add_argument("--prompt", "-p", default=None)
    p_gen.add_argument("--prompt-file", type=Path, default=None)
    p_gen.add_argument("--dry-run", action="store_true")

    p_ren = sub.add_parser("render", help="Only .tex → PDF/DOCX")
    p_ren.add_argument("tex", type=Path)
    p_ren.add_argument("-o", "--out-dir", type=Path, default=None)
    p_ren.add_argument(
        "--format",
        choices=("pdf", "docx", "both"),
        default="pdf",
        help="Primary artifact is PDF (default: pdf)",
    )

    args = parser.parse_args(argv)
    root = _root()
    # override=False: shell IMAGE_MAX_IMAGES=0 wins over .env (desk api keeps override=True)
    load_dotenv(root / ".env", override=False)

    try:
        if args.cmd == "run":
            from case3.pipeline import run_pipeline

            fmt = {"pdf", "docx"} if args.format == "both" else {args.format}
            out = run_pipeline(
                args.input,
                project_root=root,
                formats=fmt,
                dry_run=args.dry_run,
                intent=_read_prompt(args),
            )
            print(out)
            return 0

        if args.cmd == "generate":
            from case3.generate import generate_document, resolve_text_file

            src = resolve_text_file(args.input)
            out = args.output or (root / "runs" / "work" / f"{src.stem}.tex")
            generate_document(
                src,
                out_tex=out,
                intent=_read_prompt(args),
                gold_dir=root / "prompt" / "gold",
                dry_run=args.dry_run,
            )
            print(out)
            return 0

        if args.cmd == "render":
            from case3.render import render_tex

            out_dir = args.out_dir or (root / "runs" / "out")
            fmt = {"pdf", "docx"} if args.format == "both" else {args.format}
            arts = render_tex(args.tex, out_dir=out_dir, formats=fmt)
            for k, v in arts.items():
                print(f"{k}: {v}")
            return 0
    except (
        LLMConfigError,
        LLMError,
        ParseError,
        RenderError,
        FileNotFoundError,
        ValueError,
        RuntimeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if isinstance(exc, RenderError) and exc.log_path:
            print(f"TeX log: {exc.log_path}", file=sys.stderr)
        print("See runs\\logs\\  then: scripts\\push-debug.cmd", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
