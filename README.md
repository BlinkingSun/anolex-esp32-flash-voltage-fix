# AnoleX controller random-reboot fix (ESP32 flash voltage / GPIO12 strap)

A guided tool for Mac and Windows that fixes AnoleX CNC controllers that **reboot at random**. Symptoms:

- the DRO suddenly reads `0,0,0`
- the sender disconnects and reconnects by itself
- `Guru Meditation Error: Core 0 panic'ed (IllegalInstruction)` appears in the console
- `$` settings are accepted, but are gone after a power cycle

**Download:** go to the [**latest release**](../../releases/latest) and get `AnoleX-Fix-Tool-*.zip`, unzip it, and read `README.txt`.
**Full story with logs:** [docs/AnoleX-4030-random-reboots-ESP32-flash-voltage-fix.pdf](docs/AnoleX-4030-random-reboots-ESP32-flash-voltage-fix.pdf)

> Not affiliated with AnoleX or Espressif. The fix is a **permanent** change to the ESP32 chip and is at your own risk (MIT license, no warranty).

## Cause

On the original ESP32, the **GPIO12 (MTDI)** strapping pin selects the flash supply (VDD_SDIO) at reset: low gives 3.3 V, high gives 1.8 V. On the affected AnoleX board (A-X5.9.2, ESP32-WROOM-32UE, Grbl_ESP32 1.3a build 20211103), GPIO12 is high at reset, so the module's **3.3 V flash runs at 1.8 V**. The bootloader often still loads, and the firmware then crashes once it runs at full speed. Writes to flash (NVS settings) don't stick.

Signs in a serial log: the ROM banner shows `boot:0x3f` (bit 5 = GPIO12 high), and `esptool flash-id` reports `Flash voltage set by a strapping pin: 1.8V` with the flash ID reading `00 0000`.

## Fix

```
espefuse --chip esp32 --port <PORT> set-flash-voltage 3.3V
```

This burns the `XPD_SDIO_FORCE`, `XPD_SDIO_REG` and `XPD_SDIO_TIEH` eFuses, so VDD_SDIO is always 3.3 V and GPIO12 is ignored for the flash supply. Firmware, settings and wiring are not changed. It is **only valid for modules with 3.3 V flash**: see [Which ESP32 modules this is for](#which-esp32-modules-this-is-for).

## Which ESP32 modules this is for

The ESP32 module is the square, metal-shielded part on the controller board, and its name is printed on the shield. **Read the label before applying the fix.** The chip name the tool reports can't tell a WROOM from a WROVER.

| Module (label on the shield) | Chip the tool reports | Flash voltage | Use this fix? |
|---|---|---|---|
| ESP32-WROOM-32 | ESP32-D0WDQ6 | 3.3 V | Yes |
| ESP32-WROOM-32D | ESP32-D0WD | 3.3 V | Yes |
| ESP32-WROOM-32U | ESP32-D0WD | 3.3 V | Yes |
| ESP32-WROOM-32E | ESP32-D0WD-V3 | 3.3 V | Yes |
| **ESP32-WROOM-32UE** | ESP32-D0WD-V3 | 3.3 V | **Yes. This is the module on the AnoleX A-X5.9.2 board, where the fix was verified.** |
| ESP32-WROVER (any variant) | ESP32-D0WD / -V3 | some variants 1.8 V | **No.** Not covered by this tool. |
| ESP32-S2 / S3 / C3 / C6 / H2 modules (e.g. ESP32-S3-WROOM-1) | not an original ESP32 | n/a | **No.** Different chip family; the tool refuses. |
| Anything else (PICO, SOLO, MINI, clones, unmarked) | varies | check the datasheet | **Only** if the module's datasheet says its flash is 3.3 V |

"U" in a module name means an external-antenna connector; electrically it's the same module. The tool also refuses to burn if the eFuse is already set, or if the flash answers normally at 1.8 V.

## Quick start

1. Quit your G-code sender (UGS, Candle, LightBurn, ...). Plug the controller into USB and switch the machine on. Nothing moves.
2. Double-click the launcher for your computer:
   - **Mac:** `Fix-AnoleX-Mac.command`
   - **Windows:** `Fix-AnoleX-Windows.bat` (needs [Python](https://www.python.org/downloads/windows/) with "Add python.exe to PATH" ticked, and possibly the [CH340 driver](https://learn.sparkfun.com/tutorials/how-to-install-ch340-drivers))
3. Answer the questions. On first run the launcher installs [esptool](https://github.com/espressif/esptool) v5 into a private Python environment.

What the tool does:
- finds the controller, and refuses to run if another program has the port open
- reads the chip, the eFuse state and the flash voltage over 3 resets, then reports **problem found**, **not seen right now** or **already fixed**
- offers the fix only when it applies, after you answer `Y`, confirm the module marking and type `BURN`
- refuses to burn if the eFuse is already set, or if the flash answers normally at 1.8 V (a possible 1.8 V part)
- verifies the eFuse afterwards and runs a 60 s crash watch (status queries only, no motion)
- writes a `fix-log-<date>.txt` file next to itself

Command line (Python 3.8+, `python -m pip install -U esptool`):

```
python fix-tool/anolex_flash_voltage_fix.py            # diagnose only
python fix-tool/anolex_flash_voltage_fix.py --burn     # diagnose, confirm, burn, verify, watch
python fix-tool/anolex_flash_voltage_fix.py --guided   # what the launchers run
  --port COM5|/dev/cu.usbserial-XXX  --expect-mac aa:bb:cc:dd:ee:ff  --yes  --force  --watch <s>
```

## Tested

| | Result |
|---|---|
| Fix (manual `espefuse` burn) on an affected A-X5.9.2 board | Before: crashes within ~2 s of boot, settings lost. After: 7/7 clean boots, 0 crashes in 10 min, settings persist. |
| Tool on macOS (Apple Silicon) with esptool 5.6.0 | Full guided run on the fixed board: "already fixed", 3/3 restarts at 3.3 V, health check PASS |
| Windows launcher | Python detection, environment setup, esptool install, guided start and port scan (no controller attached) |
| Tool's own burn step | Same command as the manual burn above, but not yet run end-to-end by the tool on an unfixed board |

esptool v4.8.1 is refused on purpose: its `espefuse` crashes with current versions of `bitstring`.

## Files

```
fix-tool/
  Fix-AnoleX-Mac.command        Mac launcher
  Fix-AnoleX-Windows.bat        Windows launcher
  anolex_flash_voltage_fix.py   the tool
  README.txt                    step-by-step guide for end users
docs/
  AnoleX-4030-random-reboots-ESP32-flash-voltage-fix.pdf   write-up with logs
```

## License

MIT, see [LICENSE](LICENSE).
