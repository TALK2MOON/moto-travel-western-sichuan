#!/usr/bin/env python3
"""校验一份 roadbook.json，并一次性导出 Markdown、HTML 与 Excel。"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
EXPORTERS = {
    "md": ("export_markdown.py", ".md"),
    "html": ("export_html.py", ".html"),
    "xlsx": ("export_excel.py", ".xlsx"),
}


def parse_formats(value):
    formats = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = sorted(set(formats) - EXPORTERS.keys())
    if unknown:
        raise argparse.ArgumentTypeError(f"未知格式: {', '.join(unknown)}")
    return formats


def run(command, env=None):
    subprocess.run(command, check=True, env=env)


def main():
    parser = argparse.ArgumentParser(description="一键校验并导出川西摩旅路书")
    parser.add_argument("roadbook", help="已经汇总 MCP/API 结果的 roadbook.json")
    parser.add_argument("--output-dir", default="roadbook-output", help="输出目录")
    parser.add_argument("--name", default=None, help="输出文件名（不含扩展名，默认取 JSON 文件名）")
    parser.add_argument("--formats", type=parse_formats, default=parse_formats("md,html,xlsx"))
    parser.add_argument("--amap-js-key", default=None, help="高德 Web端(JS API) Key；推荐改用环境变量")
    parser.add_argument("--amap-js-security-code", default=None, help="高德 JS 安全密钥；推荐改用环境变量")
    args = parser.parse_args()

    source = Path(args.roadbook).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or source.stem

    run([sys.executable, str(SCRIPT_DIR / "validate_roadbook.py"), str(source)])
    env = os.environ.copy()
    if args.amap_js_key:
        env["AMAP_JS_KEY"] = args.amap_js_key
    if args.amap_js_security_code:
        env["AMAP_JS_SECURITY_CODE"] = args.amap_js_security_code

    generated = []
    for format_name in args.formats:
        script, suffix = EXPORTERS[format_name]
        target = output_dir / f"{stem}{suffix}"
        run([sys.executable, str(SCRIPT_DIR / script), str(source), "-o", str(target)], env=env)
        generated.append(target)
    print("构建完成：")
    for target in generated:
        print(f"- {target}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
