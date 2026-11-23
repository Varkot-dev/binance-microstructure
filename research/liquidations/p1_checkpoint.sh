#!/usr/bin/env bash
# Save or restore the finished per-symbol P1 scan outputs on a separate git branch.
#
#   research/liquidations/p1_checkpoint.sh save      # pack newly DONE symbols, push a batch
#   research/liquidations/p1_checkpoint.sh restore   # unpack every batch into data/
#
# The branch (claude/p1-scan-checkpoint) is append-only: each save adds archives holding
# only the symbols finished since the previous save, at most BATCH_MAX symbols each (about
# 0.5 MB per symbol, so an archive stays well below GitHub's 100 MB file limit), and
# appends their names to DONE_SYMBOLS.txt. Each archive is its own commit and push. The
# project branches never carry these intermediate files. A restored symbol has its DONE
# marker, so `p1_scan.py scan` skips it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SYM="$ROOT/data/liquidations/p1/sym"
BRANCH="claude/p1-scan-checkpoint"
BATCH_MAX=60
WORK="$ROOT/data/liquidations/p1/checkpoint"
URL="$(git -C "$ROOT" remote get-url origin)"

open_work() {
  # Local clone of the checkpoint branch, created from the remote branch if it exists.
  if [ -d "$WORK/.git" ]; then return; fi
  rm -rf "$WORK"
  if git ls-remote --exit-code --heads "$URL" "$BRANCH" > /dev/null 2>&1; then
    git clone -q --depth=1 --branch "$BRANCH" "$URL" "$WORK"
  else
    mkdir -p "$WORK"
    git -C "$WORK" init -q -b "$BRANCH"
    touch "$WORK/DONE_SYMBOLS.txt"
  fi
}

push_work() {
  for i in 1 2 3 4; do
    if git -C "$WORK" push -q "$URL" "$BRANCH:$BRANCH"; then return 0; fi
    sleep $((2 ** i))
  done
  echo "checkpoint push FAILED" >&2
  return 1
}

case "${1:-}" in
  save)
    open_work
    mkdir -p "$SYM"
    (cd "$SYM" && find . -mindepth 2 -maxdepth 2 -name DONE -printf '%h\n' \
      | sed 's#^\./##' | sort) > "$WORK/.done_now"
    sort "$WORK/DONE_SYMBOLS.txt" > "$WORK/.done_saved"
    comm -23 "$WORK/.done_now" "$WORK/.done_saved" > "$WORK/.new"
    n=$(wc -l < "$WORK/.new")
    if [ "$n" -eq 0 ]; then
      rm -f "$WORK"/.done_* "$WORK/.new"
      echo "checkpoint: nothing new ($(wc -l < "$WORK/DONE_SYMBOLS.txt") saved)"
      exit 0
    fi
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    split -l "$BATCH_MAX" -d -a 3 "$WORK/.new" "$WORK/.part_"
    rm -f "$WORK"/.done_* "$WORK/.new"
    for part in "$WORK"/.part_*; do
      k=$(wc -l < "$part")
      batch="batch_${stamp}_${part##*_}.tar.gz"
      (cd "$SYM" && tar -czf "$WORK/$batch" -T "$part")
      cat "$part" >> "$WORK/DONE_SYMBOLS.txt"
      rm -f "$part"
      git -C "$WORK" add "$batch" DONE_SYMBOLS.txt
      git -C "$WORK" -c user.name=Claude -c user.email=noreply@anthropic.com \
        commit -q -m "P1 scan checkpoint: +$k symbols, $(wc -l < "$WORK/DONE_SYMBOLS.txt") total"
      push_work
      echo "checkpoint: +$k symbols in $batch ($(du -h "$WORK/$batch" | cut -f1)), $(wc -l < "$WORK/DONE_SYMBOLS.txt") total"
    done
    ;;
  restore)
    open_work
    mkdir -p "$SYM"
    for f in "$WORK"/batch_*.tar.gz; do
      [ -e "$f" ] || continue
      tar -xzf "$f" -C "$SYM"
    done
    echo "restored $(find "$SYM" -mindepth 2 -maxdepth 2 -name DONE | wc -l) symbols"
    ;;
  *)
    echo "usage: $0 save|restore" >&2
    exit 2
    ;;
esac
