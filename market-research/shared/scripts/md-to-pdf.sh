#!/usr/bin/env bash
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
header_file="${script_dir}/header.tex"

usage() {
  echo "Usage: $0 REPORT.md [OUTPUT.pdf]"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 2
fi

input="$1"
output="${2:-${input%.md}.pdf}"

if [[ ! -f "${input}" ]]; then
  echo "Markdown input not found: ${input}" >&2
  exit 2
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "PDF not generated: pandoc is not installed or not on PATH." >&2
  exit 0
fi

if ! command -v xelatex >/dev/null 2>&1; then
  echo "PDF not generated: xelatex is not installed or not on PATH." >&2
  exit 0
fi

pandoc_args=(
  "${input}"
  --pdf-engine=xelatex
  -V "mainfont=Noto Sans"
  -V "geometry:margin=1in"
  -o "${output}"
)

if [[ -f "${header_file}" ]]; then
  pandoc_args+=(-H "${header_file}")
fi

if pandoc "${pandoc_args[@]}"; then
  echo "PDF generated: ${output}"
  exit 0
fi

echo "PDF not generated: pandoc failed for ${input}." >&2
echo "If xelatex is installed but LaTeX reports missing lmodern.sty, install the missing package." >&2
echo "Install a TeX distribution with lmodern support or disable PDF generation." >&2
exit 0
