#!/bin/bash
# Build PyQt app cho Linux
pyinstaller \
  --noconfirm \
  --onedir \
  --windowed \
  --name SerialCommandTester \
  --add-data "ui/main.ui:ui" \
  main.py

echo
echo "Đã build xong! File chạy ở dist/SerialCommandTester/main"