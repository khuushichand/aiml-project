#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "[lint-changed] Not inside a git repository."
  exit 1
fi

cd "${repo_root}"

base_ref="${1:-}"
if [[ -n "${base_ref}" ]]; then
  diff_range="${base_ref}...HEAD"
  changed_files="$(git diff --name-only --diff-filter=ACMRTUXB "${diff_range}" -- '*.py' || true)"
  untracked_files=""
else
  changed_files="$(git diff --name-only --diff-filter=ACMRTUXB -- '*.py' || true)"
  untracked_files="$(git ls-files --others --exclude-standard -- '*.py' || true)"
fi

files="$(
  printf '%s\n%s\n' "${changed_files}" "${untracked_files:-}" \
    | sed '/^$/d' \
    | sort -u
)"

if [[ -z "${files}" ]]; then
  echo "[lint-changed] No Python changes detected."
  exit 0
fi

echo "[lint-changed] Ruff check on changed files:"
while IFS= read -r file; do
  echo " - ${file}"
done <<< "${files}"

mapfile -t file_list < <(printf '%s\n' "${files}")
ruff check "${file_list[@]}"
