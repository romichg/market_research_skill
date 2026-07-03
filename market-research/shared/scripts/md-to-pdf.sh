#!/usr/bin/env bash
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
header_file="${script_dir}/header.tex"

usage() {
  echo "Usage: $0 REPORT.md [OUTPUT.pdf]"
}

json_escape() {
  local python_bin="${PYTHON:-/usr/bin/python3}"
  printf '%s' "$1" | "${python_bin}" -c 'import json, sys; print(json.dumps(sys.stdin.read()))'
}

emit_status() {
  local generated="$1"
  local reason="$2"
  printf '{"generated":%s,"input":%s,"output":%s,"reason":%s}\n' \
    "${generated}" \
    "$(json_escape "${input:-}")" \
    "$(json_escape "${output:-}")" \
    "$(json_escape "${reason}")"
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
  emit_status false "pandoc_missing"
  exit 0
fi

if ! command -v xelatex >/dev/null 2>&1; then
  echo "PDF not generated: xelatex is not installed or not on PATH." >&2
  emit_status false "xelatex_missing"
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

pandoc_stderr="$(mktemp)"
trap 'rm -f "${pandoc_stderr}"' EXIT

if pandoc "${pandoc_args[@]}" 2>"${pandoc_stderr}"; then
  echo "PDF generated: ${output}"
  emit_status true "generated"
  exit 0
fi

cat "${pandoc_stderr}" >&2
echo "PDF not generated: pandoc failed for ${input}." >&2

if grep -qi "lmodern.sty" "${pandoc_stderr}"; then
  echo "LaTeX reports missing lmodern.sty; install the missing package." >&2
  echo "Install a TeX distribution with lmodern support or disable PDF generation." >&2
  emit_status false "pandoc_failed_missing_lmodern"
elif grep -qiE "not loadable: Metric \(TFM\) file|mktextfm" "${pandoc_stderr}"; then
  missing_font="$(grep -oiE '@font=[A-Za-z0-9_-]+' "${pandoc_stderr}" | head -n1 | cut -d= -f2)"
  echo "LaTeX/xelatex is missing a font metric (TFM) file${missing_font:+ for '${missing_font}'} (commonly a dingbats/symbol font from texlive-fonts-extra), not lmodern." >&2
  echo "Install the missing TeX font package (e.g. texlive-fonts-extra) or disable PDF generation." >&2
  emit_status false "pandoc_failed_missing_font_metric"
else
  echo "See captured pandoc/xelatex output above for the underlying LaTeX error." >&2
  emit_status false "pandoc_failed"
fi
exit 0
