#!/usr/bin/env bash
# Save or restore the finished per-symbol P1 scan outputs on a separate git branch.
#
#   research/liquidations/p1_checkpoint.sh save      # pack DONE symbols, force-push branch
#   research/liquidations/p1_checkpoint.sh restore   # unpack the branch's archive into data/
#
# The branch (p1-scan-checkpoint) holds one commit with one file, replaced on every save,
# so the project branches never carry these intermediate files. Only symbols with a DONE
# marker are packed; a restored symbol is skipped by `p1_scan.py scan`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SYM="$ROOT/data/liquidations/p1/sym"
BRANCH="p1-scan-checkpoint"
WORK="$ROOT/data/liquidations/p1/checkpoint"

case "${1:-}" in
  save)
    rm -rf "$WORK" && mkdir -p "$WORK"
    (cd "$SYM" && find . -maxdepth 2 -name DONE -printf '%h\n' | sort > "$WORK/done.txt")
    n=$(wc -l < "$WORK/done.txt")
    (cd "$SYM" && tar -czf "$WORK/p1_sym.tar.gz" -T "$WORK/done.txt")
    git -C "$WORK" init -q -b "$BRANCH"
    cp "$WORK/done.txt" "$WORK/DONE_SYMBOLS.txt"
    rm "$WORK/done.txt"
    git -C "$WORK" add p1_sym.tar.gz DONE_SYMBOLS.txt
    git -C "$WORK" -c user.name=Claude -c user.email=noreply@anthropic.com \
      commit -q -m "P1 scan checkpoint: $n symbols ($(date -u +%Y-%m-%dT%H:%MZ))"
    url="$(git -C "$ROOT" remote get-url origin)"
    pushed=0
    for i in 1 2 3 4; do
      if git -C "$WORK" push -q -f "$url" "$BRANCH:$BRANCH"; then pushed=1; break; fi
      sleep $((2 ** i))
    done
    if [ "$pushed" -ne 1 ]; then echo "checkpoint push FAILED" >&2; exit 1; fi
    echo "checkpoint: $n symbols, $(du -h "$WORK/p1_sym.tar.gz" | cut -f1)"
    ;;
  restore)
    mkdir -p "$SYM" "$WORK"
    git -C "$ROOT" fetch -q --depth=1 origin "$BRANCH"
    git -C "$ROOT" show "FETCH_HEAD:p1_sym.tar.gz" > "$WORK/p1_sym.tar.gz"
    tar -xzf "$WORK/p1_sym.tar.gz" -C "$SYM"
    echo "restored $(find "$SYM" -maxdepth 2 -name DONE | wc -l) symbols"
    ;;
  *)
    echo "usage: $0 save|restore" >&2
    exit 2
    ;;
esac
