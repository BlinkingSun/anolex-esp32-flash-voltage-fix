#!/usr/bin/env python3
"""
AnoleX controller fix: ESP32 flash memory powered at 1.8 V instead of 3.3 V.

Cause: the ESP32's GPIO12 (MTDI) strapping pin is high at reset, which selects a 1.8 V
supply (VDD_SDIO) for the module's 3.3 V flash chip. Result: random reboots/crashes
("Guru Meditation Error"), settings that do not save.

Fix: burn ESP32 eFuses XPD_SDIO_FORCE / XPD_SDIO_REG / XPD_SDIO_TIEH so VDD_SDIO is
always 3.3 V and GPIO12 is ignored for the flash supply. PERMANENT (one-time eFuse).
Only for ESP32 modules with 3.3 V flash: ESP32-WROOM-32 / -32D / -32E / -32UE.

Easiest: double-click "Fix-AnoleX-Mac.command" (Mac) or "Fix-AnoleX-Windows.bat" (PC).
Those run:  python anolex_flash_voltage_fix.py --guided

Command line (needs Python 3.8+ and:  python -m pip install -U esptool   (v5 or newer)):
    python anolex_flash_voltage_fix.py                  diagnose only, changes nothing
    python anolex_flash_voltage_fix.py --burn           diagnose, confirm, burn, verify, watch
    python anolex_flash_voltage_fix.py --guided         step-by-step with questions
Options:
    --port COM5 | /dev/cu.usbserial-210     serial port (auto-detects a single CH340 if omitted)
    --expect-mac aa:bb:cc:dd:ee:ff          refuse unless the connected chip has this MAC
    --yes                                   skip the typed BURN confirmation (--burn only)
    --force                                 allow burning even if no 1.8 V restart was seen
    --watch 120                             seconds to watch Grbl for crashes afterwards (0 = skip)
"""
import argparse, datetime, os, re, shutil, subprocess, sys, time

CHIP = "esp32"
HERE = os.path.dirname(os.path.abspath(__file__))
GUIDED = False
LOG = None


# ---------------------------------------------------------------- output helpers
class Tee:
    """Print to the screen and to a log file at the same time."""
    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()


def ask(prompt):
    try:
        ans = input(prompt)
    except EOFError:            # no keyboard (e.g. run from a script): treat as "quit"
        ans = "q"
        print()
    if LOG:
        LOG.f.write(f"[typed] {ans}\n")
    return ans.strip()


def stop(msg, changed=False, code=1):
    print(f"\nSTOPPED: {msg}")
    if not changed:
        print("Nothing was changed on the controller.")
    sys.exit(code)


def rule(title=""):
    print("\n" + "=" * 70 + (f"\n {title}\n" + "=" * 70 if title else ""))


# ---------------------------------------------------------------- esptool plumbing
def esptool_version():
    try:
        import esptool
    except ImportError:
        stop(f"esptool is not installed. Run:  {sys.executable} -m pip install -U esptool")
    ver = esptool.__version__
    if int(ver.split(".")[0]) < 5:   # v4's espefuse breaks with current 'bitstring'; v5 is tested
        stop(f"esptool {ver} is too old. Run:  {sys.executable} -m pip install -U esptool")
    return ver


def run(module, args, timeout=180):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-m", module] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return p.stdout + p.stderr


def port_busy(port):
    """macOS/Linux: detect another program (UGS) holding the port. Windows refuses busy ports itself."""
    if os.name == "nt" or not shutil.which("lsof"):
        return False
    return bool(subprocess.run(["lsof", port], capture_output=True, text=True).stdout.strip())


def candidates():
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    ch340 = [p for p in ports if p.vid == 0x1A86]          # WCH CH340/CH341 = AnoleX USB chip
    return ports, (ch340 or [p for p in ports if p.vid is not None])


def pick_port(explicit):
    if explicit:
        return explicit
    while True:
        ports, cands = candidates()
        if len(cands) == 1:
            print(f"Controller found on {cands[0].device}  ({cands[0].description})")
            return cands[0].device
        if len(cands) > 1:
            if not GUIDED:
                stop("several USB serial devices found; choose one with --port:\n"
                     + "\n".join(f"   {p.device}  {p.description}" for p in cands))
            print("More than one USB serial device is connected:")
            for i, p in enumerate(cands, 1):
                print(f"   {i}) {p.device}   {p.description}")
            a = ask("Type the number of the CNC controller and press Enter (Q = quit): ")
            if a.lower() == "q":
                stop("quit.", code=0)
            if a.isdigit() and 1 <= int(a) <= len(cands):
                return cands[int(a) - 1].device
            continue
        if not GUIDED:
            stop("no USB serial device found. Plug in the controller (and on Windows install the CH340 driver).")
        print("\nNo controller found. Check that:")
        print("  - the USB cable is plugged into the controller and this computer")
        print("  - the controller has power (machine switched on)")
        print("  - Windows only: the CH340 USB driver is installed (see README)")
        if ask("Press Enter to look again, or type Q and Enter to quit: ").lower() == "q":
            stop("quit.", code=0)


def wait_until_free(port):
    while port_busy(port):
        if not GUIDED:
            stop(f"{port} is open in another program (UGS, Candle, LightBurn...). Close it first.")
        print(f"\n{port} is being used by another program (UGS, Candle, LightBurn, gSender...).")
        print("Disconnect or quit that program.")
        if ask("Press Enter to try again, or type Q and Enter to quit: ").lower() == "q":
            stop("quit.", code=0)


def diagnose(port, samples=3):
    out = run("esptool", ["--chip", CHIP, "--port", port, "--no-stub", "read-mac"])
    m = re.search(r"MAC:\s*([0-9a-fA-F:]{17})", out)
    if not m:
        hint = ""
        if re.search(r"Access is denied|PermissionError|could not open port|Resource busy", out, re.I):
            hint = "\nThe port is busy: close UGS or any other program connected to the machine.\n"
        elif re.search(r"Wrong chip|not an ESP32|Unexpected chip", out, re.I):
            hint = "\nThis is not an original ESP32 chip - this fix does not apply.\n"
        stop(f"could not talk to the ESP32 on {port}.{hint}\nTechnical details:\n{out[-700:]}")
    mac = m.group(1).lower()
    cm = re.search(r"Chip (?:is|type:)\s*(.+)", out)
    chip = cm.group(1).strip() if cm else "?"

    summ = run("espefuse", ["--chip", CHIP, "--port", port, "summary"])
    if re.search(r"set to 3\.3V by efuse", summ, re.I):
        fuse = "3.3V"
    elif re.search(r"set to 1\.8V by efuse", summ, re.I):
        fuse = "1.8V"
    elif re.search(r"determined by GPIO12", summ, re.I):
        fuse = "GPIO12"
    else:
        stop(f"could not read the chip's eFuse settings.\nTechnical details:\n{summ[-700:]}")

    restarts, answered_at_18 = [], False
    for _ in range(samples):
        f = run("esptool", ["--chip", CHIP, "--port", port, "--no-stub", "flash-id"])
        v = re.search(r"(?:strapping pin|by eFuse)(?::| to)\s*([0-9.]+V)", f)  # v5 ': 3.3V', v4 ' to 3.3V'
        m2 = re.search(r"Manufacturer:\s*([0-9a-fA-F]+)", f)
        volt, man = (v.group(1) if v else "?"), (m2.group(1).lower() if m2 else "?")
        restarts.append(volt)
        if volt == "1.8V" and man not in ("00", "ff", "?"):
            answered_at_18 = True     # flash works at 1.8 V -> could be a genuine 1.8 V part
    return mac, chip, fuse, restarts, answered_at_18


def grbl_watch(port, seconds):
    import serial
    s = serial.Serial()
    s.port, s.baudrate, s.timeout, s.dtr, s.rts = port, 115200, 0.1, False, False
    s.open()                                   # opening the port restarts the controller once (normal)
    t0, buf, last, shown = time.time(), b"", 0.0, -1
    while time.time() - t0 < seconds:
        buf += s.read(4096)
        now = time.time()
        if now - last > 1.0:
            s.write(b"?")                      # status request only - never moves the machine
            last = now
        left = int(seconds - (now - t0))
        if left % 10 == 0 and left != shown:
            print(f"   {left:3d} s left ...")
            shown = left
    s.close()
    txt = buf.decode(errors="replace")
    return {"boots": txt.count("rst:0x"), "crashes": txt.count("Guru Meditation"),
            "csum": txt.count("csum err"), "banner": "Grbl " in txt,
            "replies": len(re.findall(r"<(?:Idle|Alarm|Run|Jog|Hold|Door|Home|Check)", txt))}


# ---------------------------------------------------------------- main flow
def main():
    global GUIDED, LOG
    ap = argparse.ArgumentParser(description="Fix ESP32 1.8 V flash supply (GPIO12 strap) by burning the 3.3 V eFuse.")
    ap.add_argument("--port")
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--guided", action="store_true")
    ap.add_argument("--expect-mac")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--watch", type=int, default=None)
    a = ap.parse_args()
    GUIDED = a.guided
    watch = a.watch if a.watch is not None else (60 if GUIDED else 120)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for folder in (HERE, os.getcwd()):
        try:
            LOG = Tee(os.path.join(folder, f"fix-log-{stamp}.txt"))
            sys.stdout = LOG
            break
        except OSError:
            continue

    rule("AnoleX controller - flash voltage check and fix")
    print("This checks whether your controller's ESP32 powers its memory chip at the wrong")
    print("voltage (1.8 V instead of 3.3 V), which causes random reboots. It never moves the machine.")
    print("Before you start: quit UGS (or any G-code sender) and plug the controller into USB.")
    if GUIDED and ask("\nPress Enter to begin (Q = quit): ").lower() == "q":
        stop("quit.", code=0)

    ver = esptool_version()
    port = pick_port(a.port)
    wait_until_free(port)
    print(f"Using esptool {ver}. Reading the controller (it will restart a few times; this is normal)...")

    mac, chip, fuse, restarts, answered_at_18 = diagnose(port)
    n18 = restarts.count("1.8V")
    rule("RESULT")
    print(f"Chip            : {chip}")
    print(f"Chip ID (MAC)   : {mac}")
    print(f"Flash supply    : " + ("locked to 3.3 V by eFuse (already fixed)" if fuse == "3.3V" else
                                  "locked to 1.8 V by eFuse" if fuse == "1.8V" else
                                  "chosen by GPIO12 at every restart (not locked)"))
    print(f"3 test restarts : " + ", ".join(restarts))

    if a.expect_mac and mac != a.expect_mac.lower():
        stop(f"this chip is {mac}, not the expected {a.expect_mac.lower()} - wrong board.")

    burned = False
    if fuse == "3.3V":
        print("\nGOOD NEWS: this controller is already fixed. Nothing to do.")
    elif fuse != "GPIO12":
        stop("the flash-voltage eFuse is already set to something else. This tool will not touch it.")
    elif answered_at_18:
        stop("the memory chip answered normally at 1.8 V, so it may be a genuine 1.8 V part.\n"
             "This tool only fixes 3.3 V flash that fails at 1.8 V, and will not change anything here.")
    else:
        if n18:
            print(f"\nPROBLEM FOUND: on {n18} of {len(restarts)} restarts the memory chip got 1.8 V instead of 3.3 V.")
            print("This is the cause of random reboots / 'Guru Meditation Error' / settings not saving.")
        else:
            print("\nNot seen right now: all restarts chose the correct 3.3 V. The fault can come and go")
            print("(it often gets worse as the board warms up).")

        want = a.burn
        if GUIDED:
            print("\nTHE FIX: set a permanent switch (eFuse) inside the ESP32 so the memory chip always")
            print("gets 3.3 V. Firmware, settings and wiring are not changed. It cannot be undone,")
            print("but there is no reason to ever undo it on a 3.3 V module.")
            if not n18:
                print("Because the fault was not seen just now, only continue if your controller has")
                print("been rebooting at random.")
            want = ask("\nApply the fix now? Type Y and Enter for yes, anything else for no: ").lower() == "y"
            if not want:
                stop("you chose not to apply the fix.", code=0)
        elif not want:
            print("\nDiagnose-only run. Run again with --burn to apply the fix.")
            return
        if not n18 and not (a.force or GUIDED):
            stop("no 1.8 V restart was seen. Add --force to burn anyway.")

        print("\nSAFETY CHECK: this is only correct for ESP32 modules with 3.3 V flash memory.")
        print("The module is the metal-covered square on the board; its name is printed on it.")
        print("OK markings: ESP32-WROOM-32, -32D, -32U, -32E, -32UE (the AnoleX A-X5.9.2 board uses -32UE).")
        print("NOT OK: ESP32-WROVER (any), ESP32-S2/S3/C3/C6 modules, or anything not listed. See README.")
        if GUIDED and ask("Does your module carry one of those markings? (Y/N): ").lower() != "y":
            stop("module not confirmed. If unsure, open the controller and read the module label.")
        if not a.yes and ask("Type BURN (capital letters) and press Enter to apply the permanent fix: ") != "BURN":
            stop("not confirmed.", code=0)

        wait_until_free(port)
        print("\nApplying fix ...")
        out = run("espefuse", ["--chip", CHIP, "--port", port, "--do-not-confirm", "set-flash-voltage", "3.3V"])
        if LOG:
            LOG.f.write(out + "\n")
        mac2, _, fuse2, _, _ = diagnose(port, samples=1)
        if mac2 != mac or fuse2 != "3.3V":
            stop(f"could not verify the fix (eFuse reads '{fuse2}'). Details:\n{out[-700:]}", changed=True)
        burned = True
        print("FIXED: the memory chip is now always powered at 3.3 V (verified).")

    if watch > 0:
        rule("HEALTH CHECK")
        print(f"Watching the controller for {watch} seconds for crashes (status requests only, no motion)...")
        r = grbl_watch(port, watch)
        print(f"Restarts: {r['boots']} (1 is normal)  |  Crashes: {r['crashes']}  |  "
              f"Grbl started: {'yes' if r['banner'] else 'NO'}  |  Status replies: {r['replies']}")
        ok = r["crashes"] == 0 and r["csum"] == 0 and r["boots"] <= 1 and r["banner"]
        print("HEALTH CHECK: PASS" if ok else
              "HEALTH CHECK: FAIL - the controller still restarted or crashed. See README 'If it still resets'.")

    rule("DONE")
    if burned:
        print("Next: unplug USB, switch the machine off and on, reconnect your sender, HOME the machine")
        print("and do an air cut (spindle off, above the work) before cutting for real.")
    if LOG:
        print(f"A log of this session was saved as: {LOG.f.name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop("cancelled with Ctrl+C. If this happened while applying the fix, run the tool again to check the result.", changed=True, code=1)
