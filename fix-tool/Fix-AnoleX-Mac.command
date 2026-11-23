#!/bin/bash
# AnoleX controller flash-voltage fix - Mac launcher.
# Double-click this file. It sets up Python's esptool (first run only, needs internet)
# and starts the guided fix. It never moves the machine.

cd "$(dirname "$0")" || exit 1
clear
echo "AnoleX controller fix (Mac)"
echo "---------------------------"
echo

pause_and_exit() { echo; read -r -p "Press Enter to close this window..." _; exit "$1"; }

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
  echo "Python 3.8 or newer is needed and was not found."
  echo "  - If a box popped up asking to install 'command line developer tools', click Install,"
  echo "    wait for it to finish, then double-click this file again."
  echo "  - Or install Python from https://www.python.org/downloads/ and run this again."
  pause_and_exit 1
fi

VENV="$HOME/.anolex-fix-venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "First run: setting up a private Python environment (needs internet, about a minute)..."
  python3 -m venv "$VENV" || { echo "Could not create the Python environment."; pause_and_exit 1; }
fi

if ! "$VENV/bin/python" -c "import esptool,sys; sys.exit(0 if int(esptool.__version__.split('.')[0]) >= 5 else 1)" >/dev/null 2>&1; then
  echo "Installing esptool (one time, needs internet)..."
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade esptool \
    || { echo "Install failed. Check the internet connection and try again."; pause_and_exit 1; }
fi

"$VENV/bin/python" anolex_flash_voltage_fix.py --guided
pause_and_exit $?
