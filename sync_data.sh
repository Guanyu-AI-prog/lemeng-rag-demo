#!/bin/bash
# 同步知识库 markdown 到项目 data/ 目录（脱敏演示版：用 docs_src/ 下的示例文档）
# 用法：把你的 md 文档放进 docs_src/，再跑本脚本
set -e
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docs_src"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/data"

mkdir -p "$SRC" "$DST"
rm -rf "$DST"
mkdir -p "$DST"

rsync -av \
  --include='*/' --include='*.md' \
  --exclude='*' \
  "$SRC/" "$DST/"

echo '--- 同步完成,md 文件数: ---'
find "$DST" -name '*.md' | wc -l
