AnoleX CNC CONTROLLER - RANDOM REBOOT FIX (ESP32 FLASH VOLTAGE)
=================================================================

WHAT THIS FIXES
---------------
Some AnoleX controllers (board A-X5.9.2, ESP32-WROOM-32UE module, Grbl_ESP32 1.3a)
reboot at random. You may see:
  - the position (DRO) suddenly reads 0,0,0 even though the machine has moved
  - UGS / your sender disconnects and reconnects by itself
  - "Guru Meditation Error ... panic'ed" in the console
  - settings ($ commands) that are accepted but gone after a power cycle
  - a jog that keeps going on its own after a reconnect

The cause: at every power-up the board holds one ESP32 pin (GPIO12) high, and the
ESP32 reads that as "power the memory chip at 1.8 V". The memory chip needs 3.3 V.
Underpowered, it misreads the firmware and the controller crashes.

The fix sets a permanent switch (an "eFuse") inside the ESP32 so the memory chip
always gets 3.3 V, whatever GPIO12 does. It takes about a second.

WHAT THE FIX DOES NOT DO
------------------------
  - It does not change the firmware, your settings, steps/mm or homing.
  - It does not change wiring, and GPIO12 keeps doing its normal job.
  - It never moves the machine. The tool only reads the chip and asks for status.

IMPORTANT
---------
  - The fix is PERMANENT. It cannot be undone. There is no reason to undo it on a
    3.3 V module, but you should know.
  - It is only correct for ESP32 modules with 3.3 V memory: ESP32-WROOM-32, -32D,
    -32E, -32U, -32UE. AnoleX boards use the WROOM-32UE. The module is the square
    metal-covered part on the board, and its name is printed on it.
  - It may affect your warranty. Use at your own risk.
  - The tool checks first and only offers the fix if the problem is present
    (or if you confirm your controller has been rebooting at random).

WHAT YOU NEED
-------------
  - A Mac or a Windows PC with internet (the first run downloads "esptool", the
    official ESP32 tool from Espressif, about 10 MB).
  - Python 3.8 or newer (see the steps below if you don't have it).
  - The USB cable you normally use for the machine.
  - About 5 minutes.

-----------------------------------------------------------------
STEPS - MAC
-----------------------------------------------------------------
1. Quit UGS (or whatever sender you use). It must not be connected.
2. Plug the controller into the Mac by USB and switch the machine on.
   Nothing will move.
3. Double-click  "Fix-AnoleX-Mac.command".
     - If the Mac says it "cannot be opened because it is from an unidentified
       developer": right-click the file, choose Open, then click Open.
     - If it says you "do not have appropriate access privileges": open
       Terminal, type  chmod +x  (with a space after it), drag the file into the
       Terminal window, and press Enter. Then double-click it again.
     - If a box asks to install "command line developer tools", click Install,
       wait for it to finish, and double-click the file again (that installs
       Python). You can also install Python from https://www.python.org/downloads/
4. Follow the questions in the window (see "WHAT YOU WILL SEE" below).

-----------------------------------------------------------------
STEPS - WINDOWS
-----------------------------------------------------------------
1. Install Python if you don't have it: https://www.python.org/downloads/windows/
   On the FIRST installer screen tick "Add python.exe to PATH", then Install Now.
2. Install the CH340 USB driver if Windows doesn't already see the controller.
   The driver is from WCH, the chip maker. Download and install steps:
   https://learn.sparkfun.com/tutorials/how-to-install-ch340-drivers
   (Windows 10/11 often installs it automatically. In Device Manager the
   controller shows as "USB-SERIAL CH340 (COMx)".)
3. Quit UGS (or whatever sender you use).
4. Plug the controller into the PC by USB and switch the machine on.
5. Double-click  "Fix-AnoleX-Windows.bat".
     - If Windows shows "Windows protected your PC": click "More info", then "Run anyway".
6. Follow the questions in the window.

-----------------------------------------------------------------
WHAT YOU WILL SEE
-----------------------------------------------------------------
  - First run only: "setting up..." and "Installing esptool..." (about a minute).
  - "Controller found on COM5" (Windows) or "/dev/cu.usbserial-xxx" (Mac).
    If more than one device is listed, type the number of the CNC controller.
  - The controller restarts a few times while it is being read. That's normal.
  - A RESULT section. One of:
      PROBLEM FOUND: on 3 of 3 restarts the memory chip got 1.8 V ...
          -> it offers the fix
      Not seen right now: all restarts chose the correct 3.3 V ...
          -> only apply the fix if your controller has been rebooting at random
      GOOD NEWS: this controller is already fixed.
          -> nothing to do
  - To apply the fix you answer Y, confirm the module, then type BURN.
  - "FIXED: ... (verified)", then a 60-second HEALTH CHECK.
    "HEALTH CHECK: PASS" means no crashes.
  - A log file (fix-log-<date>.txt) is saved next to the tool. Keep it if you
    need help.

AFTER THE FIX
-------------
  1. Unplug USB, switch the machine off and on again.
  2. Connect your sender as usual and HOME the machine.
  3. Do an "air cut" (spindle off, Z well above the work) of a real job before
     cutting for real.

TROUBLESHOOTING
---------------
  "No controller found"
      Check the cable, machine power, and (Windows) the CH340 driver. Try another
      USB cable or port. Some cables only carry power, not data.
  "... is being used by another program" / "Access is denied" / "port is busy"
      UGS, Candle, LightBurn, gSender or similar is still connected. Quit it.
  "Python 3.8 or newer is needed / not installed"
      Install Python (see the steps above). On Windows, re-run the installer and
      tick "Add python.exe to PATH".
  "Install failed"
      There's no internet, or a firewall is blocking it. Connect and try again.
  "could not talk to the ESP32"
      Unplug and replug USB, power-cycle the machine, close other programs, and
      try again.
  "the flash-voltage eFuse is already set to something else"
      Stop. This board is configured differently, and the tool won't touch it.

IF IT STILL RESETS AFTER THE FIX
--------------------------------
The fix removes one specific cause. If the health check still fails, or the
machine still reboots:
  - Try a different USB cable and USB port, and keep the USB cable away from the
    motor and spindle cables.
  - Check that the controller's power connectors are tight.
  - Contact AnoleX support (support@anolexcnc.com) and send them the fix-log file.

ADVANCED - DOING IT BY HAND
---------------------------
  python -m pip install -U esptool                 (needs esptool v5 or newer)
  python -m esptool --chip esp32 --port <PORT> --no-stub flash-id
      -> "Flash voltage set by a strapping pin: 1.8V" = problem present
  python -m espefuse --chip esp32 --port <PORT> summary
      -> "determined by GPIO12" = fuse not set yet
  python -m espefuse --chip esp32 --port <PORT> set-flash-voltage 3.3V      (PERMANENT)
      -> afterwards the summary says "set to 3.3V by efuse"
  The script also runs from the command line:
  python anolex_flash_voltage_fix.py --help

FILES
-----
  Fix-AnoleX-Mac.command        double-click on a Mac
  Fix-AnoleX-Windows.bat        double-click on Windows
  anolex_flash_voltage_fix.py   the tool itself (both launchers run this)
  README.txt                    this file
  The launchers keep their Python setup outside this folder (Mac: ~/.anolex-fix-venv,
  Windows: %LOCALAPPDATA%\anolex-fix-venv), so the folder stays small enough to share.
