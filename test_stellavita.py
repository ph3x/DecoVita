#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 ph3x
# SPDX-License-Identifier: GPL-3.0-or-later
#
# phdlogview_parse() is a Python port of parts of phdlogview's logparser.cpp,
# which is licensed under the GPL v3. Copyright of that code remains with the
# phdlogview authors.
"""
Test suite for stellavita.py (Version 1).

Builds synthetic, fully fictitious log files (all SSIDs, passwords, serial
numbers, IPs and coordinates below are made up), encrypts them with the
inverse cipher, runs the tool and checks every promised V1 behaviour.

Run:  python3 test_stellavita.py [path/to/stellavita.py]
"""
import os
import re
import sys
import io
import random
import shutil
import hashlib
import tempfile
import subprocess
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "stellavita.py")
spec = importlib.util.spec_from_file_location("sv", TOOL)
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if (detail and not cond) else ""))


SKIPPED = []


def skip(name, why):
    SKIPPED.append((name, why))
    print("  SKIP  " + name + "  -- " + why)


def quiet(*a, **k):
    pass


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------------------
#  Fictitious test data
# ---------------------------------------------------------------------------

FAKE = {
    "ssid_short": "FAKE_HOME",          # prefix of the long one on purpose
    "ssid_long": "FAKE_HOME_EXT",
    "password": "FAKE-PASS-ONE",
    "serial32": "FAKESERIAL0000000000000000000ABC",
    "serial12": "FAKESN123456",
    "artist": "FAKE ARTIST NAME",
    "ip_dev": "192.168.77.23",
    "ip_gw": "192.168.77.1",
    "ip_other": "192.168.88.5",
    "ip_other_gw": "192.168.88.1",
    "lat_json": "12.3456", "lon_json": "-23.4567",
    "lat_json7": "12.3456789", "lon_json7": "-23.4567891",
    "lat_indi": "12.345678", "lon_indi": "336.543210", "elev": "345.000000",
    "alt": "42.123456", "az": "123.654321", "lst": "19.876543",
    "utc": "2026-01-15T19:15:01", "spa_alt": "12.300000",
}


def guide_plain(version="2.0.37"):
    rnd = random.Random(42)
    L = []
    a = L.append
    a("Log begin at 2026-01-15_201500")
    a("Platform: RaspberryPi")
    a("Version: " + version)
    a("Version protocol: 2")
    a("2026-01-15 20:15:30: Guiding Ends")
    a("")
    a("2026-01-15 20:16:00: Calibration Begins")
    hdr_cal = [
        "Dither = both axes, Dither scale = 10.000, Image noise reduction = none",
        "Pixel scale = 5.95 arc-sec/px, Binning = 1, Focal length = 130 mm",
        "Search region = 15 px, Star mass tolerance 50.0%, Multi-star mode, list size = 8",
        "Camera = Test Camera, full size = 1280 x 960, pixel size = 3.8 um",
        "Exposure = 500.000 ms",
        "Mount = Test Mount, Calibration Step = 2500 ms, Calibration Distance = 25 px",
        "RA Guide Speed = 7.5 a-s/s, Dec Guide Speed = 7.5 a-s/s",
        "RA = 1.33 hr, Dec = 58.3 deg, LST = 19.87 hr, Pier side = West, Alt = 42.9 deg, Az = 45.1 deg",
        "Lock position = 492.254, 429.865, Star position = 492.377, 429.909, HFD = 5.62 px",
    ]
    L.extend(hdr_cal)
    a("Direction,Step,dx,dy,x,y,Dist")
    cal = [("West", 0, "0.000", "0.000", "492.706", "430.000", "0.000"),
           ("West", 1, "-2.878", "0.808", "495.584", "429.192", "2.989"),
           ("East", 1, "-1.804", "0.548", "494.000", "429.452", "1.886"),
           ("Backlash", 0, "0.000", "0.000", "488.725", "428.822", "0.000"),
           ("North", 1, "-0.379", "2.276", "489.768", "420.918", "2.308"),
           ("South", 1, "-1.837", "10.368", "491.227", "412.827", "10.529"),
           ("NudgeSouth", 1, "-1.729", "7.402", "491.119", "415.793", "7.601")]
    for i, (d, s, dx, dy, x, y, dist) in enumerate(cal):
        a("2026-01-15 20:16:%02d: Calibration Step-> Direction-%s, StepNum-%d, DX-%s, DY-%s, X-%s, Y-%s, Dist-%s"
          % (1 + 4 * i, d, s, dx, dy, x, y, dist))
    a("2026-01-15 20:16:30: Calibration Direct Complete")
    a("West calibration complete. Angle = -179.7 deg, Rate = 0.632 px/sec, Parity = Even")
    a("2026-01-15 20:16:30: Calibration Direct Complete")
    a("North calibration complete. Angle = -82.5 deg, Rate = 1.158 px/sec, Parity = Even")
    a("2026-01-15 20:16:30: Calibration Complete")
    a("Calibration complete, mount = Test Mount")
    a("")

    def session(begin_wall, start_frame, nsteps, drops_at, cross_midnight=False):
        import datetime
        a("%s: Guiding Begins" % begin_wall.strftime("%Y-%m-%d %H:%M:%S"))
        L.extend([
            "Dither = both axes, Dither scale = 5.000, Image noise reduction = none",
            "Pixel scale = 5.95 arc-sec/px, Binning = 1, Focal length = 130 mm",
            "Camera = Test Camera, full size = 1280 x 960, pixel size = 3.8 um",
            "Exposure = 500.000 ms",
            "Mount = Test Mount, connected, guiding enabled, xAngle = 0.0, xRate = 0.632, yAngle = -82.5, yRate = 1.158, parity = +/+",
            "Norm rates RA = 7.2\"/s @ dec 0, Dec = 6.9\"/s",
            "X guide algorithm = Hysteresis",
            "Y guide algorithm = Resist Switch",
            "Backlash comp = disabled, pulse = 0 ms",
            "Max RA duration = 2500, Max DEC duration = 2500, DEC guide mode = auto",
            "RA = 1.33 hr, Dec = 58.3 deg, LST = 19.93 hr, Pier side = West, Alt = 43.3 deg, Az = 45.3 deg",
            "Lock position = 492.254, 429.865, Star position = 490.198, 427.610, HFD = 5.41 px",
            "Frame,Time,mount,dx,dy,RARawDistance,DECRawDistance,RAGuideDistance,DECGuideDistance,RADuration,RADirection,DECDuration,DECDirection,XStep,YStep,StarMass,SNR,ErrorCode",
        ])
        a("%s: Settle State Changed" % begin_wall.strftime("%Y-%m-%d %H:%M:%S"))
        a("INFO: SETTLING STATE CHANGE, Settling started")
        st = 5.0
        frame = start_frame
        steps = drops = 0
        for k in range(nsteps):
            st += 1.2 + rnd.random() * 0.2
            wall = begin_wall + datetime.timedelta(seconds=st)
            ts = wall.strftime("%Y-%m-%d %H:%M:%S")
            if k in drops_at:
                err = drops_at[k]
                a("%s: Guiding Frame Dropped-> FrameNum-%d, Time-0.000, \"DROP\"   StarMass-%d, StarSNR-%.2f, StarErr-%d, \"eGuideState::GUIDING\""
                  % (ts, frame, rnd.randint(0, 90000), rnd.random() * 90, err))
                drops += 1
            else:
                rdur = rnd.choice([0, 0, 150, 300])
                ddur = rnd.choice([0, 0, 120, 480])
                rdir = rnd.choice("WE") if rdur else ""
                ddir = rnd.choice("NS") if ddur else ""
                cx, cy = rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)
                a("%s: Guiding Step-> FrameNum-%d, StepTime-%.3f, \"Mount\", CamOffsetX-%.3f, CamOffsetY-%.3f, "
                  "MountOffsetX-%.3f, MountOffsetY-%.3f, DistRa-%.3f, DistDec-%.3f, DurRa-%d (%s), DurDec-%d (%s)   "
                  "StarMass-%d, StarSNR-%.2f, StarErr-0"
                  % (ts, frame, st, cx, cy, -cx, -cy, abs(cx), abs(cy), rdur, rdir, ddur, ddir,
                     rnd.randint(500000, 900000), 120 + rnd.random() * 40))
                steps += 1
            if k == 5:
                a("%s: Settle State Changed" % ts)
                a("INFO: SETTLING STATE CHANGE, Settling complete")
            if k == 12:
                a("%s: Set Lock Position" % ts)
                a("INFO: SET LOCK POSITION, new lock pos = 498.955, 442.759")
                a("%s: Guiding Dithered" % ts)
                a("INFO: DITHER by -0.874, 2.845, new lock pos = 498.955, 442.759")
            frame += 1
        end = begin_wall + datetime.timedelta(seconds=st + 2)
        a("%s: Guiding Ends" % end.strftime("%Y-%m-%d %H:%M:%S"))
        a("")
        return steps, drops

    import datetime
    s1 = session(datetime.datetime(2026, 1, 15, 20, 16, 31), 100, 40, {8: 7, 9: 2, 20: 8})
    s2 = session(datetime.datetime(2026, 1, 15, 23, 59, 30), 200, 60, {30: 4})
    # duplicate end line as seen in real logs
    a("2026-01-16 00:01:40: Guiding Ends")
    return L, {"sessions": 2, "steps": s1[0] + s2[0], "drops": s1[1] + s2[1]}


def debug_plain():
    F = FAKE
    L = []
    a = L.append
    a("[20:15:00.100] [CoreServer] start, version 2.0.37")
    a('[20:15:00.200] [CoreServer][RES][ipv4:%s:44034] {"id":1,"code":0,"CMD_GLOBAL_GET_WIFI":{"ssid":"%s","password":"%s"}}'
      % (F["ip_dev"], F["ssid_long"], F["password"]))
    a('[20:15:00.300] [CoreServer][RES][ipv4:%s:44034] {"id":2,"code":0,"CMD_GLOBAL_GET_NETWORK":{"wifi_ssid":"%s","wifi_password":"%s",'
      '"is_bridge_wifi_on":true,"connecting_bridge_wifi_ssid":"%s","connected_bridge_wifi_ssid":"%s",'
      '"connected_bridge_wifi_ip":"%s","connected_bridge_wifi_subnet_mask":"255.255.255.0","connected_bridge_wifi_gateway":"%s"}}'
      % (F["ip_dev"], F["ssid_long"], F["password"], F["ssid_short"], F["ssid_short"], F["ip_dev"], F["ip_gw"]))
    a('[20:15:00.400] [CoreServer][RES][ipv4:%s:44034] {"id":3,"code":0,"ip":"%s","subnet_mask":"255.255.255.0","gateway":"%s"}'
      % (F["ip_dev"], F["ip_other"], F["ip_other_gw"]))
    a('[20:15:00.500] [CoreServer][RES][ipv4:%s:44034] {"id":4,"code":0,"poaefw_sdk_version":"1.2.3.4","tp_sdk_version":"60.32549.20260908","info":"ip:%s"}'
      % (F["ip_dev"], F["ip_dev"]))
    a('[20:15:00.600] [CoreServer][RES][ipv4:%s:44034] {"id":5,"code":0,"CMD_GLOBAL_GET_LOCATION":{"latitude":%s,"longitude":%s}}'
      % (F["ip_dev"], F["lat_json"], F["lon_json"]))
    a('[20:15:00.700] [CoreServer][REQ][ipv4:%s:44034] {"id":6,"CMD_GLOBAL_SET_LOCATION":{"latitude":%s,"longitude":%s}}'
      % (F["ip_dev"], F["lat_json7"], F["lon_json7"]))
    a("[20:15:00.800] [WiFi] connected to %s ok" % F["ssid_long"])
    a("[20:15:01.000] ScopeINDI::received Property")
    a("[20:15:01.001] -> Number (GEOGRAPHIC_COORD)(RW)")
    a("[20:15:01.002] --> Number#0: name = LAT, label = Lat (dd:mm:ss), value = %s, min = -90.000000, max = 90.000000, step = 0.000000" % F["lat_indi"])
    a("[20:15:01.003] --> Number#1: name = LONG, label = Lon (dd:mm:ss), value = %s, min = 0.000000, max = 360.000000, step = 0.000000" % F["lon_indi"])
    a("[20:15:01.004] --> Number#2: name = ELEV, label = Elevation (m), value = %s, min = -200.000000, max = 10000.000000, step = 0.000000" % F["elev"])
    a("[20:15:01.005] -> Number (HORIZONTAL_COORD)(RO)")
    a("[20:15:01.006] --> Number#0: name = ALT, label = Altitude, value = %s, min = -90.000000, max = 90.000000, step = 0.000000" % F["alt"])
    a("[20:15:01.007] --> Number#1: name = AZ, label = Azimuth, value = %s, min = 0.000000, max = 360.000000, step = 0.000000" % F["az"])
    a("[20:15:01.008] -> Number (TIME_LST)(RO)")
    a("[20:15:01.009] --> Number#0: name = LST, label = Local Sidereal Time, value = %s, min = 0.000000, max = 24.000000, step = 0.000000" % F["lst"])
    a("[20:15:01.010] -> Number (EQUATORIAL_EOD_COORD)(RW)")
    a("[20:15:01.011] --> Number#0: name = RA, label = RA (hh:mm:ss), value = 1.330000, min = 0.000000, max = 24.000000, step = 0.000000")
    a("[20:15:01.012] --> Number#1: name = DEC, label = DEC (dd:mm:ss), value = 58.300000, min = -90.000000, max = 90.000000, step = 0.000000")
    a("[20:15:01.013] -> Text (TIME_UTC)(RW)")
    a("[20:15:01.014] --> Text#0: name = UTC, label = UTC Time, text = %s" % F["utc"])
    a("[20:15:01.015] --> Text#1: name = OFFSET, label = UTC Offset, text = 1.00")
    a("[20:15:01.016] -> Number (SYNCPOLARALIGN)(RO)")
    a("[20:15:01.017] --> Number#0: name = SYNCPOLARALIGN_ALT, label = Mount Alt, value = %s, min = 0.000000, max = 90.000000, step = 0.000000" % F["spa_alt"])
    a("[20:15:01.019] -> Switch (CONNECTION_MODE)(RW)")
    a("[20:15:01.020] --> Switch#0: name = CONNECTION_SERIAL, label = Serial, state = on")
    a("[20:15:02.000] [gphoto] dumping config")
    for path, label, cur in (("/main/settings/ownername", "Owner Name", ""),
                             ("/main/settings/artist", "Artist", F["artist"]),
                             ("/main/status/serialnumber", "Serial Number", F["serial32"]),
                             ("/main/status/eosserialnumber", "Serial Number", F["serial12"]),
                             ("/main/imgsettings/iso", "ISO Speed", "1600")):
        a("Config: " + path)
        a("  Label      : " + label)
        a("  Readonly   : 0")
        a("  Type       : " + ("RADIO" if "iso" in path else "TEXT"))
        a("  Current    : " + cur)
        if "iso" in path:
            a("  Choices    : Auto, 100, 200, 400, 800, 1600, 3200, 6400")
    a("11111111000000000000000000")
    a("")
    # filler: many anchored lines (gives the per-file model real data)
    rnd = random.Random(7)
    h, m, s = 20, 15, 3
    for i in range(400):
        s += 7
        while s >= 60:
            s -= 60; m += 1
        while m >= 60:
            m -= 60; h += 1
        a('[%02d:%02d:%02d.%03d] [CoreServer][EVT][ipv4:%s:44034] {"event_type":"EVT_GUIDE_STEP":{"frame_number":%d,"time":%.3f,"offset_x":%.6f,"offset_y":%.6f}}'
          % (h, m, s, rnd.randint(0, 999), F["ip_dev"], i, i * 1.2, rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
    a("[23:59:59.900] [CoreServer] tick before midnight")
    a("[00:00:00.100] [CoreServer] tick after midnight")
    a("[00:00:05.000] [ASGuide] StarFindResult returns 1 (0), x=848.47, y=225.43, Mass=76731, SNR=81.5")
    return L


GLOG_PLAIN = [
    "[00:00:00.000][14616]sdk: libtoupcam.so, 60.32549.20260908, 12:29:38",
    "[00:00:00.000][14616]exe: as_core",
    "[00:00:00.000][14616]cpu: Raspberry Pi Compute Module 4 Rev 1.1",
    "[00:00:00.001][14616]time: 20260115 20:14:52",
    "[00:00:00.003][14616]EnumLibusb: libusb_get_device_list = 8",
    "[00:00:00.003][14616]EnumBottomHalf: empty",
]


def encrypt_lines(lines, seed):
    rnd = random.Random(seed)
    return b"\n".join(sv.encode_line(l, rnd.randint(0, 94)) for l in lines) + b"\n"


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def body(path):
    """Output file content without the tool's '# ' header lines."""
    lines = open(path, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines) and lines[i].startswith("# "):
        i += 1
    out = lines[i:]
    if out and out[-1] == "":
        out = out[:-1]
    return out


# ---------------------------------------------------------------------------
#  phdlogview parser port (logparser.cpp) to verify the PHD2 output contract
# ---------------------------------------------------------------------------

def phdlogview_parse(lines):
    """Faithful port of the relevant parts of phdlogview's LogParser::Parse.
    Returns (sessions, calibrations, errors)."""
    sessions, cals, errors = [], [], []
    st, s, cal = "SKIP", None, None

    def to_num(x, f=float):
        try:
            return f(x), True
        except ValueError:
            return None, False

    for ln in lines:
        ln = ln.rstrip()
        if st == "SKIP":
            if ln.startswith("Guiding Begins at "):
                s = {"start": ln[18:], "entries": [], "infos": [], "hdr": []}
                sessions.append(s); st = "GHDR"; continue
            if ln.startswith("Calibration Begins at "):
                cal = {"start": ln[22:], "entries": [], "hdr": []}
                cals.append(cal); st = "CHDR"; continue
            continue
        if st == "GHDR":
            if ln.startswith("Frame,Time,mount"):
                st = "G"; continue
            s["hdr"].append(ln); continue
        if st == "G":
            if ln == "" or ln.startswith("Guiding Ends"):
                st = "SKIP"; continue
            if ln and "1" <= ln[0] <= "9":
                f = (ln + ",,").split(",")
                fr, ok1 = to_num(f[0], int)
                dt, ok2 = to_num(f[1])
                if not (ok1 and ok2):
                    errors.append(("entry", ln)); continue
                for idx in (3, 4, 5, 6, 7, 8):
                    if f[idx] and not to_num(f[idx])[1]:
                        errors.append(("float", ln))
                for idx in (9, 11, 15):
                    if f[idx] and not to_num(f[idx], int)[1]:
                        errors.append(("int", ln))
                if f[10] and f[10][0] not in "EW":
                    errors.append(("radir", ln))
                if f[12] and f[12][0] not in "NS":
                    errors.append(("decdir", ln))
                err = int(f[17]) if f[17] else 0
                s["entries"].append((fr, dt, err, f[2]))
                continue
            if ln.startswith("INFO: "):
                s["infos"].append(ln)
            continue
        if st == "CHDR":
            if ln.startswith("Direction,Step,dx,dy,x,y,Dist"):
                st = "C"; continue
            cal["hdr"].append(ln); continue
        if st == "C":
            if ln == "" or ln.startswith("Calibration complete"):
                st = "SKIP"; continue
            if re.match(r"^(West|East|Backlash|North|South|Left|Up),", ln):
                f = ln.split(",")
                if not (to_num(f[1], int)[1] and to_num(f[2])[1] and to_num(f[3])[1]):
                    errors.append(("cal", ln))
                cal["entries"].append(f[0])
            else:
                cal["hdr"].append(ln)
    return sessions, cals, errors


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

def t_cipher():
    print("\n[1] Chiffre")
    rnd = random.Random(1)
    alpha = "".join(chr(c) for c in range(33, 126)) + " "
    ok = True
    for _ in range(3000):
        txt = "".join(rnd.choice(alpha) for _ in range(rnd.randint(0, 150)))
        t0 = rnd.randint(0, 94)
        if sv.decode_line(sv.encode_line(txt, t0), t0) != txt:
            ok = False; break
    check("Round-trip 3000 Zufallszeilen exakt", ok)
    check("'~' kollidiert erwartungsgemaess mit Leerzeichen",
          sv.decode_line(sv.encode_line("a~b", 5), 5) == "a b")
    check("Bytes ausserhalb 33..126 werden durchgereicht",
          sv.decode_line(b"\t", 3) == "\t")
    # timestamp anchoring
    ok = True
    for t0 in range(95):
        line = "[12:34:56.789] [CoreServer] x"
        d, anch, _ = sv.recover(sv.encode_line(line, t0))
        if d != line or not anch:
            ok = False
        line2 = "2026-01-15 20:16:01: Calibration Step-> Direction-West"
        d2, anch2, _ = sv.recover(sv.encode_line(line2, t0))
        if d2 != line2 or not anch2:
            ok = False
    check("Zeilen mit Zeitstempel fuer alle 95 Schluessel sicher erkannt", ok)


def t_sniff(fx):
    print("\n[2] Dateityp-Erkennung")
    check("verschluesseltes GuideLog", sv.sniff(fx["guide"]) == ("guide", False), str(sv.sniff(fx["guide"])))
    check("verschluesseltes DebugLog", sv.sniff(fx["debug"]) == ("debug", False), str(sv.sniff(fx["debug"])))
    check("Klartext-GuideLog", sv.sniff(fx["guide_plain"]) == ("guide", True), str(sv.sniff(fx["guide_plain"])))
    check("Klartext-DebugLog", sv.sniff(fx["debug_plain"]) == ("debug", True), str(sv.sniff(fx["debug_plain"])))
    check(".glog", sv.sniff(fx["glog"]) == ("glog", True), str(sv.sniff(fx["glog"])))
    check("unbekannte Datei", sv.sniff(fx["unknown"])[0] == "unknown", str(sv.sniff(fx["unknown"])))


def t_decode_exact(fx, tmp):
    print("\n[3] Dekodierung (ohne Schwaerzen) gleich Klartext")
    out = os.path.join(tmp, "o_dec")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=(), make_phd2=False, log=quiet)
    got = body(r["outputs"][0])
    exp = fx["guide_lines"]
    bad = [i for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    check("GuideLog: alle %d Zeilen exakt" % len(exp), len(got) == len(exp) and not bad,
          "Abweichungen bei %s" % bad[:5])
    check("GuideLog: keine unsicheren Zeilen", r["uncertain"] == 0, str(r["uncertain"]))
    r = sv.process_file(fx["debug"], out_dir=out, enabled=(), full_date=False, log=quiet)
    got = body(r["outputs"][0])
    exp = fx["debug_lines"]
    bad = [i for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    check("DebugLog: alle %d Zeilen exakt (inkl. Kamera-Einstellungsliste)" % len(exp),
          len(got) == len(exp) and not bad, "Abweichungen bei %s" % bad[:5])
    # the bit-string line '1111...000' is inherently ambiguous (a shifted key gives
    # another all-digit string), so exactly that one line must be flagged uncertain
    check("DebugLog: genau die mehrdeutige Ziffernzeile als unsicher markiert",
          r["uncertain"] == 1, str(r["uncertain"]))
    _, anch, mg = sv.recover(sv.encode_line("  Label      : ISO Speed", 40), sv.train_model(fx["debug"]))
    check("eindeutige Textzeile ohne Anker: hoher Abstand", not anch and mg >= sv.UNCERTAIN_MARGIN, "%.1f" % mg)


def _debug_out(fx, tmp, name, enabled, full_date=False):
    out = os.path.join(tmp, name)
    os.makedirs(out)
    r = sv.process_file(fx["debug"], out_dir=out, enabled=enabled, full_date=full_date, log=quiet)
    return r, "\n".join(body(r["outputs"][0]))


def t_redact(fx, tmp):
    print("\n[4] Schwaerzen (alle Kategorien an)")
    F = FAKE
    r, txt = _debug_out(fx, tmp, "o_red", sv.CATEGORIES)
    # hotspot
    for k in ("ssid_short", "ssid_long", "password"):
        check("Hotspot: '%s' nirgends mehr enthalten" % k, F[k] not in txt)
    check("Hotspot: SSIDs nummeriert (<SSID_1>, <SSID_2>)", "<SSID_1>" in txt and "<SSID_2>" in txt)
    check("Hotspot: kein Rest '_EXT' (laengere SSID zuerst ersetzt)", "_EXT" not in txt)
    long_tok = re.search(r'"ssid":"(<SSID_\d>)"', txt).group(1)
    check("Hotspot: Freitext-Vorkommen mit gleichem Platzhalter ersetzt",
          ("connected to %s ok" % long_tok) in txt)
    check("Hotspot: Passwortfelder -> <REDACTED>",
          '"password":"<REDACTED>"' in txt and '"wifi_password":"<REDACTED>"' in txt)
    # network
    check("Netz: 3. Oktett maskiert, Geraet bleibt erkennbar (192.168.<N1>.23)",
          "ipv4:192.168.<N1>.23:44034" in txt)
    check("Netz: Gateway im selben Netz gleicher Platzhalter (192.168.<N1>.1)",
          '"connected_bridge_wifi_gateway":"192.168.<N1>.1"' in txt)
    check("Netz: zweites Netz eigener Platzhalter (192.168.<N2>.5)", '"ip":"192.168.<N2>.5"' in txt)
    check("Netz: 'ip:'-Info maskiert", '"info":"ip:192.168.<N1>.23"' in txt)
    check("Netz: Subnetzmasken unveraendert", txt.count('255.255.255.0') == 2)
    check("Netz: Versionsnummern unveraendert (1.2.3.4, 60.32549.20260908)",
          '"poaefw_sdk_version":"1.2.3.4"' in txt and "60.32549.20260908" in txt)
    for ip in ("192.168.77.", "192.168.88."):
        check("Netz: '%s' nirgends mehr" % ip, ip not in txt)
    # location
    for k in ("lat_json", "lon_json", "lat_json7", "lon_json7", "lat_indi", "lon_indi",
              "elev", "alt", "az", "lst", "utc", "spa_alt"):
        check("Standort: Originalwert %s weg" % k, F[k] not in txt)
    check("Standort: JSON-Koordinaten auf 1 Nachkommastelle",
          '"latitude":12.3,"longitude":-23.5' in txt)
    check("Standort: INDI LAT/LONG gerundet",
          "name = LAT, label = Lat (dd:mm:ss), value = 12.3," in txt and
          "name = LONG, label = Lon (dd:mm:ss), value = 336.5," in txt)
    for nm in ("ELEV", "ALT", "AZ", "LST", "SYNCPOLARALIGN_ALT"):
        check("Standort: %s-Wert -> <REDACTED>" % nm,
              re.search(r"name = %s, .*value = <REDACTED>" % nm, txt) is not None)
    check("Standort: UTC-Zeit -> <REDACTED>", "name = UTC, label = UTC Time, text = <REDACTED>" in txt)
    check("Standort: RA/DEC bleiben", "value = 1.330000" in txt and "value = 58.300000" in txt)
    # serial
    for k in ("serial32", "serial12", "artist"):
        check("Seriennr.: '%s' weg" % k, F[k] not in txt)
    check("Seriennr.: leeres Besitzerfeld bleibt leer",
          re.search(r"Config: /main/settings/ownername\n(?:.*\n){3}  Current    : \n", txt + "\n") is not None)
    check("Seriennr.: ISO-Wert (nicht sensibel) bleibt", "  Current    : 1600" in txt)
    check("Seriennr.: CONNECTION_SERIAL-Schalter bleibt",
          "name = CONNECTION_SERIAL, label = Serial, state = on" in txt)
    check("Zaehler je Kategorie > 0", all(r["redactions"][c] > 0 for c in sv.CATEGORIES),
          str(r["redactions"]))


def t_redact_doubt():
    print("\n[5] Schwaerzen im Zweifel (fehlerhaft dekodierte Zeile im Seriennr.-Block)")
    red = sv.Redactor(sv.CATEGORIES)
    seq = ["Config: /main/status/serialnumber", "  Label      : Serial Number",
           "mm2daaT]cmmmm)m }}FAKEGARBLE", "[20:00:00.000] next", "Config: /main/imgsettings/iso",
           "zz garbled but not sensitive"]
    out = [red.feed(l) for l in seq]
    check("unbekannte Zeile im sensiblen Block -> ganze Zeile <REDACTED>", out[2] == sv.REDACTED, out[2])
    check("Label-Zeile bleibt", out[1] == seq[1])
    check("Block endet bei Zeitstempel-Zeile", out[3] == seq[3])
    check("nicht sensibler Block bleibt unangetastet", out[5] == seq[5])


def t_toggles(fx, tmp):
    print("\n[6] Kategorien einzeln abschaltbar")
    F = FAKE
    probes = {"hotspot": F["ssid_long"], "network": F["ip_dev"],
              "location": F["lat_indi"], "serial": F["serial32"]}
    for off in sv.CATEGORIES:
        en = tuple(c for c in sv.CATEGORIES if c != off)
        _, txt = _debug_out(fx, tmp, "o_tog_" + off, en)
        ok_off = probes[off] in txt
        ok_on = all(probes[c] not in txt for c in en)
        check("ohne '%s': deren Daten bleiben, Rest geschwaerzt" % off, ok_off and ok_on)
    _, txt = _debug_out(fx, tmp, "o_tog_none", ())
    check("--no-redact: alles bleibt", all(v in txt for v in probes.values()))


def t_header(fx, tmp):
    print("\n[7] Kennzeichnung in der Ausgabe")
    out = os.path.join(tmp, "o_hdr")
    os.makedirs(out)
    r = sv.process_file(fx["debug"], out_dir=out, enabled=("hotspot", "serial"),
                        full_date=False, lang="de", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("Kopfzeile DE nennt nur aktive Kategorien",
          "# Geschwärzt: Hotspot/WLAN, Seriennummern" in head, str(head))
    check("Kopfzeile DE warnt vor nicht geschwaerzten Kategorien",
          any(l.startswith("# ACHTUNG nicht geschwärzt") and "Netzwerkadressen, Standort" in l for l in head), str(head))
    check("Kopfzeile: Hinweis 'inoffiziell' und Originale",
          "Inoffiziell" in head[0] and any("Originaldateien" in l for l in head))
    out3 = os.path.join(tmp, "o_hdr_all")
    os.makedirs(out3)
    r = sv.process_file(fx["debug"], out_dir=out3, enabled=sv.CATEGORIES, full_date=False, lang="de", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("alles geschwaerzt: keine ACHTUNG-Zeile", not any("ACHTUNG" in l for l in head), str(head))
    out2 = os.path.join(tmp, "o_hdr_en")
    os.makedirs(out2)
    r = sv.process_file(fx["debug"], out_dir=out2, enabled=(), full_date=False, lang="en", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("Kopfzeile EN 'Redacted: nothing'", "# Redacted: nothing" in head, str(head))
    check("Kopfzeile EN warnt (WARNING not redacted)", any(l.startswith("# WARNING not redacted") for l in head), str(head))


def t_guide_location_kept(fx, tmp):
    print("\n[8] GuideLog-Standort bleibt (Entscheidung: ~10 km reicht)")
    out = os.path.join(tmp, "o_gloc")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=sv.CATEGORIES, log=quiet)
    got = body(r["outputs"][0])
    check("GuideLog mit allen Kategorien == Klartext", got == fx["guide_lines"])


def t_date(fx, tmp):
    print("\n[9] Volles Datum im DebugLog")
    r, txt = _debug_out(fx, tmp, "o_date", (), full_date=True)
    lines = txt.split("\n")
    check("Zeilen vor Mitternacht mit 2026-01-15",
          "[2026-01-15 23:59:59.900] [CoreServer] tick before midnight" in lines)
    check("Zeilen nach Mitternacht mit 2026-01-16",
          "[2026-01-16 00:00:00.100] [CoreServer] tick after midnight" in lines)
    check("Zeilen ohne Zeitstempel unveraendert", "Config: /main/status/serialnumber" in lines)
    _, txt2 = _debug_out(fx, tmp, "o_nodate", (), full_date=False)
    check("--no-full-date: Originalformat", "[23:59:59.900] [CoreServer] tick before midnight" in txt2)
    out = os.path.join(tmp, "o_noname")
    os.makedirs(out)
    msgs = []
    r = sv.process_file(fx["debug_nodate"], out_dir=out, enabled=(), full_date=True, log=msgs.append)
    check("kein Datum im Dateinamen: Warnung", "no_date" in r["warnings"])
    check("kein Datum im Dateinamen: keine Datums-Praefixe",
          "[20:15:00.100]" in "\n".join(body(r["outputs"][0])))
    d = sv.DebugDater((2026, 1, 15))
    seq = ["[23:00:00.000] a", "[22:59:00.000] b (kleiner Ruecksprung)", "[00:00:01.000] c"]
    out = [d.feed(x) for x in seq]
    check("kleiner Ruecksprung zaehlt nicht als neuer Tag", out[1].startswith("[2026-01-15 22:59"))
    check("Ruecksprung > 12 h = neuer Tag", out[2].startswith("[2026-01-16 00:00"))


def t_phd2(fx, tmp):
    print("\n[10] PHD2-Umwandlung")
    out = os.path.join(tmp, "o_phd2")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=sv.CATEGORIES, log=quiet)
    phd = [p for p in r["outputs"] if p.endswith("_phd2.txt")]
    check("PHD2-Datei erzeugt", len(phd) == 1)
    lines = body(phd[0])
    exp = fx["guide_stats"]
    check("Statistik Sessions/Schritte/Ausfaelle korrekt",
          r["guide"] == exp, "%s vs %s" % (r["guide"], exp))
    check("erste Zeile: PHD2-Versionszeile",
          lines[0] == "PHD2 version StellaVita-2.0.37, Log version 2.5. Log enabled at 2026-01-15 20:15:00", lines[0])
    sessions, cals, errors = phdlogview_parse(lines)
    check("phdlogview-Parser: keine Fehler", not errors, str(errors[:3]))
    check("phdlogview-Parser: 1 Kalibrierung, 2 Sessions", len(cals) == 1 and len(sessions) == 2,
          "%d/%d" % (len(cals), len(sessions)))
    n_entries = sum(len(s["entries"]) for s in sessions)
    check("phdlogview-Parser: alle Schritte+Ausfaelle als Eintraege",
          n_entries == exp["steps"] + exp["drops"], "%d" % n_entries)
    drops = [e for s in sessions for e in s["entries"] if e[3] == '"DROP"']
    check("Ausfaelle mit Fehlercode != 0", len(drops) == exp["drops"] and all(e[2] != 0 for e in drops))
    txt = "\n".join(lines)
    for code, desc in ((7, "Star lost - mass changed"), (2, "Star lost - low SNR / not found"),
                       (8, "Star lost - moved too far"), (4, "Star lost - too near edge")):
        check("Ausfall-Text fuer StarErr %d" % code, ',%d,"%s"' % (code, desc) in txt)
    mono = all(all(b[1] > a[1] for a, b in zip(s["entries"], s["entries"][1:])) for s in sessions)
    check("Zeitachse je Session streng steigend (auch mit geschaetzten Ausfallzeiten)", mono)
    check("Kalibrierrichtungen W/E/Backlash/N/S erkannt",
          cals[0]["entries"] == ["West", "West", "East", "Backlash", "North", "South"], str(cals[0]["entries"]))
    check("NudgeSouth als Kopftext (wie phdlogview es behandelt)",
          any(h.startswith("NudgeSouth,") for h in cals[0]["hdr"]))
    infos = [i for s in sessions for i in s["infos"]]
    check("INFO-Zeilen erhalten (Settling/Dither/Lock)",
          any("DITHER by" in i for i in infos) and any("SET LOCK POSITION" in i for i in infos)
          and any("Settling complete" in i for i in infos))
    check("einzelnes 'Guiding Ends' vor der Kalibrierung nicht uebernommen",
          txt.count("Guiding Ends at") == 2)
    check("Session ueber Mitternacht: Startzeit korrekt",
          sessions[1]["start"] == "2026-01-15 23:59:30")
    out2 = os.path.join(tmp, "o_nophd2")
    os.makedirs(out2)
    r = sv.process_file(fx["guide"], out_dir=out2, make_phd2=False, log=quiet)
    check("--no-phd2: keine PHD2-Datei", not any(p.endswith("_phd2.txt") for p in r["outputs"]))


def t_files(fx, tmp):
    print("\n[11] Dateien")
    before = {k: sha(fx[k]) for k in ("guide", "debug", "glog")}
    out = os.path.join(tmp, "o_files")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, log=quiet)
    names = sorted(os.path.basename(p) for p in r["outputs"])
    check("Namen: _decoded.txt und _phd2.txt",
          names == ["GuideLog_2026-01-15_201500_decoded.txt", "GuideLog_2026-01-15_201500_phd2.txt"], str(names))
    check("Ausgabeordner wird verwendet", all(os.path.dirname(p) == out for p in r["outputs"]))
    p0 = r["outputs"][0]
    m0, s0 = os.path.getmtime(p0), sha(p0)
    msgs = []
    r2 = sv.process_file(fx["guide"], out_dir=out, enabled=(), log=msgs.append)
    check("ohne --force nichts ueberschrieben", sha(p0) == s0 and not r2["outputs"])
    check("Meldung beim Ueberspringen", any("force" in m for m in msgs))
    r3 = sv.process_file(fx["guide"], out_dir=out, enabled=(), force=True, log=quiet)
    check("mit --force ueberschrieben", sha(p0) != s0)
    rg = sv.process_file(fx["glog"], out_dir=out, log=quiet)
    check(".glog -> _redacted.glog", [os.path.basename(p) for p in rg["outputs"]] == ["libtoupcam_latest_redacted.glog"])
    check(".glog: Inhalt bleibt (nichts zu schwaerzen)", body(rg["outputs"][0]) == GLOG_PLAIN)
    check(".glog: Kopfzeile mit Schwaerz-Kennzeichnung",
          open(rg["outputs"][0], encoding="utf-8").readline().startswith("# "))
    for o in r["outputs"]:
        check("Kopfzeile in %s" % os.path.basename(o), open(o, encoding="utf-8").readline().startswith("# "))
    after = {k: sha(fx[k]) for k in ("guide", "debug", "glog")}
    check("Originale unveraendert", before == after)
    # folder gathering
    files = sv.gather([fx["dir"]], recursive=False)
    base = sorted(os.path.basename(f) for f in files)
    check("Ordner: eigene Ausgaben und .fits werden ausgelassen",
          not any(b.endswith(("_decoded.txt", "_phd2.txt")) for b in base) and "image.fits" not in base, str(base))
    check("Ordner ohne -r: Unterordner nicht", not any("sub" in f for f in files))
    files_r = sv.gather([fx["dir"]], recursive=True)
    check("Ordner mit -r: Unterordner dabei", any(os.sep + "sub" + os.sep in f for f in files_r))
    msgs = []
    ru = sv.process_file(fx["unknown"], out_dir=out, log=msgs.append)
    check("unbekannte Datei: uebersprungen mit Meldung", ru["skipped"] == "unknown" and msgs)
    rp = sv.process_file(fx["guide_plain"], out_dir=out, log=quiet)
    check("schon dekodiertes GuideLog: verarbeitet ohne erneutes Dekodieren",
          body(rp["outputs"][0]) == fx["guide_lines"])
    # re-feeding our own output as plain input must strip the old header
    own = os.path.join(tmp, "own_copy.txt")
    shutil.copy(r3["outputs"][0], own)
    out3 = os.path.join(tmp, "o_own")
    os.makedirs(out3)
    ro = sv.process_file(own, out_dir=out3, enabled=(), log=quiet)
    hdr = [l for l in open(ro["outputs"][0], encoding="utf-8") if l.startswith("# ")]
    ref_hdr = [l for l in sv._redaction_header((), "en").split("\n") if l]
    check("eigene Ausgabe als Eingabe: alte Kopfzeilen nicht verdoppelt",
          len(hdr) == len(ref_hdr), "%d vs %d" % (len(hdr), len(ref_hdr)))


def t_report(fx, tmp):
    print("\n[12] Probelauf")
    out = os.path.join(tmp, "o_rep")
    os.makedirs(out)
    msgs = []
    r = sv.process_file(fx["debug"], out_dir=out, report=True, full_date=False, log=msgs.append)
    check("Probelauf schreibt nichts", os.listdir(out) == [])
    check("Probelauf meldet Kategorien", any("Hotspot" in m for m in msgs), str(msgs))
    r2, _ = _debug_out(fx, tmp, "o_rep_real", sv.CATEGORIES)
    check("Probelauf-Zaehler == echter Lauf", r["redactions"] == r2["redactions"],
          "%s vs %s" % (r["redactions"], r2["redactions"]))
    rg = sv.process_file(fx["guide"], out_dir=out, report=True, log=quiet)
    check("Probelauf GuideLog schreibt nichts", os.listdir(out) == [])


def t_version(fx, tmp):
    print("\n[13] Versionspruefung")
    out = os.path.join(tmp, "o_ver")
    os.makedirs(out)
    r = sv.process_file(fx["guide_v9"], out_dir=out, log=quiet)
    check("unbekannte Logversion -> Warnung", any(w.startswith("version:9.9.9") for w in r["warnings"]),
          str(r["warnings"]))
    r = sv.process_file(fx["guide"], out_dir=out, force=True, log=quiet)
    check("bekannte Version -> keine Warnung", not r["warnings"], str(r["warnings"]))


def t_cli(fx, tmp):
    print("\n[14] Kommandozeile")
    py = sys.executable
    p = subprocess.run([py, TOOL, "--help"], capture_output=True, text=True)
    check("--help", p.returncode == 0 and "--no-redact-location" in p.stdout)
    out = os.path.join(tmp, "o_cli")
    p = subprocess.run([py, TOOL, fx["dir"], "-o", out, "--lang", "de"], capture_output=True, text=True)
    check("Ordnerlauf Exitcode 0", p.returncode == 0, p.stderr[-300:])
    check("deutsche Meldungen", "Fertig:" in p.stdout, p.stdout[:200])
    made = sorted(os.listdir(out))
    check("alle Ausgaben erzeugt",
          {"GuideLog_2026-01-15_201500_decoded.txt", "GuideLog_2026-01-15_201500_phd2.txt",
           "DebugLog_2026-01-15_201500_decoded.txt", "libtoupcam_latest_redacted.glog"} <= set(made), str(made))
    check("unbekannte Datei gemeldet", "notes.txt" in p.stdout)
    p = subprocess.run([py, TOOL, fx["debug"], "-o", out, "--lang", "en", "--force",
                        "--no-redact-network"], capture_output=True, text=True)
    txt = open(os.path.join(out, "DebugLog_2026-01-15_201500_decoded.txt"), encoding="utf-8").read()
    check("--no-redact-network wirkt", FAKE["ip_dev"] in txt and FAKE["ssid_long"] not in txt)
    check("englische Meldungen", "Done:" in p.stdout, p.stdout[:200])
    check("Einzahl bei einer Datei ('1 file')", "(1 file," in p.stdout, p.stdout[-80:])
    p = subprocess.run([py, TOOL, fx["glog"], "-o", os.path.join(tmp, "o_cli_nr"), "--lang", "de", "--no-redact"],
                       capture_output=True, text=True)
    check("--no-redact: Warnung beim Lauf", "ACHTUNG: nicht geschwärzt" in p.stdout, p.stdout[:200])
    p = subprocess.run([py, TOOL, fx["glog"], "-o", os.path.join(tmp, "o_cli_all"), "--lang", "de"],
                       capture_output=True, text=True)
    check("Standardlauf: keine Warnung", "ACHTUNG" not in p.stdout, p.stdout[:200])
    out2 = os.path.join(tmp, "o_cli_rep")
    p = subprocess.run([py, TOOL, fx["debug"], "-o", out2, "--report"], capture_output=True, text=True)
    check("--report schreibt nichts", not os.path.exists(out2) or os.listdir(out2) == [])


def t_progress_i18n(fx, tmp):
    print("\n[14b] Fortschritt und Meldungen in beiden Sprachen")
    for lang, word in (("de", "Zeilen"), ("en", "lines")):
        buf = io.StringIO()
        old = sys.stderr
        sys.stderr = buf
        try:
            sv.make_progress(lang)(50, 100, 1234)
        finally:
            sys.stderr = old
        check("Fortschrittszeile %s: '%s'" % (lang.upper(), word), ("1234 " + word) in buf.getvalue(), buf.getvalue())
    empty = os.path.join(tmp, "empty_dir")
    os.makedirs(empty)
    p = subprocess.run([sys.executable, TOOL, empty, "--lang", "de"], capture_output=True, text=True)
    check("leerer Ordner: deutsche Meldung", "Keine Logdateien gefunden." in p.stdout and p.returncode == 1,
          p.stdout[:200])


def t_menu(fx, tmp):
    print("\n[15] Textmenue (Fallback ohne tkinter)")
    env = dict(os.environ, LANG="en_US.UTF-8")
    # make tkinter unimportable for this run
    stub = os.path.join(tmp, "notk")
    os.makedirs(stub, exist_ok=True)
    with open(os.path.join(stub, "tkinter.py"), "w") as f:
        f.write("raise ImportError('no tk (test stub)')\n")
    env["PYTHONPATH"] = stub
    work = os.path.join(tmp, "menu_in")
    os.makedirs(work)
    shutil.copy(fx["guide"], work)
    feed = work + "\n" + "n\n" + "\n" + "\n"           # folder, no recurse, redact all, PHD2 yes
    p = subprocess.run([sys.executable, TOOL], input=feed, capture_output=True, text=True, env=env)
    made = sorted(os.listdir(work))
    check("Menue laeuft ohne tkinter", p.returncode == 0, p.stderr[-300:])
    check("Menue erzeugt Ausgaben", any(m.endswith("_phd2.txt") for m in made), str(made))
    check("Menue: Grund fuer fehlendes Fenster wird angezeigt (Python-Pfad + Fehler)",
          "No window: tkinter missing in" in p.stdout and sys.executable in p.stdout, p.stdout[:300])
    check("Menue: klare Eingabeaufforderung fuer Kategorien", "Selection (e.g. 3 or 2,3)" in p.stdout, p.stdout[-300:])
    check("Menue: Schlusszeile mit Dateianzahl und Dauer", re.search(r"\(1 file, [\d.]+s\)", p.stdout) is not None,
          p.stdout[-200:])
    # tkinter installed but no display (SSH / console): must fall back to the menu
    try:
        import tkinter  # noqa
        have_tk = True
    except Exception:
        have_tk = False
    if not have_tk:
        skip("tkinter ohne Bildschirm -> Menue", "tkinter in diesem Python nicht installiert")
    else:
        env2 = dict(os.environ, LANG="de_AT.UTF-8")
        env2.pop("DISPLAY", None)
        work2 = os.path.join(tmp, "menu_nodisp")
        os.makedirs(work2)
        shutil.copy(fx["glog"], work2)
        p = subprocess.run([sys.executable, TOOL], input=work2 + "\nn\n\n\n", capture_output=True,
                           text=True, env=env2)
        check("tkinter ohne Bildschirm: Grund angezeigt", "kein Bildschirm" in p.stdout, p.stdout[:300])
        check("tkinter ohne Bildschirm: kein Absturz, Menue statt Fenster",
              p.returncode == 0 and "Datei oder Ordner" in p.stdout, (p.stderr or p.stdout)[-300:])
        check("tkinter ohne Bildschirm: Ausgabe erzeugt",
              any(m.endswith("_redacted.glog") for m in os.listdir(work2)), str(os.listdir(work2)))


def t_gui(fx, tmp):
    print("\n[16] Fenster (tkinter)")
    try:
        import tkinter  # noqa
    except Exception:
        skip("Fenster-Tests", "tkinter in diesem Python nicht installiert")
        return
    if not shutil.which("Xvfb"):
        skip("Fenster-Tests", "Xvfb nicht vorhanden")
        return
    disp = ":97"
    xv = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1024x768x24"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        time.sleep(1)
        env = dict(os.environ, DISPLAY=disp, SV_GUI_AUTOCLOSE="1500")
        p = subprocess.run([sys.executable, TOOL], capture_output=True, text=True, env=env, timeout=60)
        check("Fenster startet und schliesst sauber", p.returncode == 0, p.stderr[-300:])
        work = os.path.join(tmp, "gui_in")
        os.makedirs(work)
        shutil.copy(fx["guide"], work)
        env = dict(env, SV_GUI_AUTORUN=work, SV_GUI_AUTOCLOSE="6000")
        p = subprocess.run([sys.executable, TOOL], capture_output=True, text=True, env=env, timeout=60)
        made = sorted(os.listdir(work))
        check("Fenster-Lauf erzeugt Ausgaben", any(m.endswith("_phd2.txt") for m in made), str(made) + p.stderr[-200:])
        _gui_layout_and_outdir(fx, tmp, env)
    finally:
        xv.terminate()


# Runs inside a subprocess on the Xvfb display; prints one JSON object.
_GUI_PROBE = r'''
import json, os, sys, importlib.util
spec = importlib.util.spec_from_file_location("sv", sys.argv[1])
sv = importlib.util.module_from_spec(spec); spec.loader.exec_module(sv)
import tkinter as tk
src, out_new, out_file, lang = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
res = {}

def visible(root, w):
    """Mapped and fully inside the window's client area."""
    if not w.winfo_ismapped():
        return False
    top = w.winfo_rooty() - root.winfo_rooty()
    left = w.winfo_rootx() - root.winfo_rootx()
    return (top >= 0 and left >= 0 and top + w.winfo_height() <= root.winfo_height()
            and left + w.winfo_width() <= root.winfo_width())

# layout at normal and enlarged display scaling (1.0x, 1.25x, 1.5x of 96 dpi)
for scale in (1.3333, 1.6667, 2.0):
    root = tk.Tk()
    root.tk.call("tk", "scaling", scale)
    g = sv.build_gui(root, lang)
    for name, geo in (("default", None), ("min", "%dx%d" % root.minsize()), ("tiny", "200x120")):
        if geo:
            root.geometry(geo)
        root.update()
        res["%s@%s" % (name, scale)] = {
            "size": [root.winfo_width(), root.winfo_height()],
            "req": [root.winfo_reqwidth(), root.winfo_reqheight()],
            "widgets": all(visible(root, w) for w in g.all_widgets())}
    root.destroy()
root = tk.Tk()
g = sv.build_gui(root, lang)
root.update()
# dry run with an output folder must not create it
g.sel.set(src); g.out.set(out_new)
g.go(report=True); root.update()
res["dry_created"] = os.path.exists(out_new)
# real run into a not yet existing output folder
g.go(report=False); root.update()
res["out_files"] = sorted(os.listdir(out_new)) if os.path.isdir(out_new) else None
res["src_files"] = sorted(os.listdir(os.path.dirname(src)))
# output folder that is a file -> message, nothing written
g.out.set(out_file); g.go(report=False); root.update()
res["file_msg"] = g.text.get("1.0", "end").strip()
root.destroy()
print(json.dumps(res))
'''


def _gui_layout_and_outdir(fx, tmp, env):
    import json
    work = os.path.join(tmp, "gui_probe_in")
    os.makedirs(work)
    shutil.copy(fx["guide"], work)
    src = os.path.join(work, os.path.basename(fx["guide"]))
    out_new = os.path.join(tmp, "gui_probe_out", "nested")
    out_file = os.path.join(tmp, "gui_probe_isfile")
    write(out_file, "x")
    env = {k: v for k, v in env.items() if not k.startswith("SV_GUI_")}
    p = subprocess.run([sys.executable, "-c", _GUI_PROBE, TOOL, src, out_new, out_file, "de"],
                       capture_output=True, text=True, env=env, timeout=60)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        check("Fenster-Probe laeuft", False, (p.stderr or p.stdout)[-400:])
        return
    for scale, label in (("1.3333", "1.0x"), ("1.6667", "1.25x"), ("2.0", "1.5x")):
        for name, what in (("default", "Startgroesse"), ("min", "Mindestgroesse"),
                           ("tiny", "200x120 angefordert")):
            k = "%s@%s" % (name, scale)
            check("Skalierung %s, %s: alle Bedienelemente sichtbar (inkl. Probelauf/Start)"
                  % (label, what), r[k]["widgets"], str(r[k]))
    check("Zielordner: Probelauf legt ihn nicht an", r["dry_created"] is False)
    check("Zielordner: wird angelegt und enthaelt die Ausgaben",
          r["out_files"] == ["GuideLog_2026-01-15_201500_decoded.txt",
                             "GuideLog_2026-01-15_201500_phd2.txt"], str(r["out_files"]))
    check("Zielordner: nichts neben der Eingabe geschrieben",
          r["src_files"] == [os.path.basename(src)], str(r["src_files"]))
    check("Zielordner ist eine Datei: Meldung, kein Lauf",
          r["file_msg"].startswith("Zielordner ist eine Datei:"), r["file_msg"][:200])


# ---------------------------------------------------------------------------

def build_fixtures(tmp):
    d = os.path.join(tmp, "fix")
    fx = {"dir": d}
    gl, gstats = guide_plain()
    dl = debug_plain()
    fx["guide_lines"], fx["guide_stats"], fx["debug_lines"] = gl, gstats, dl
    fx["guide"] = os.path.join(d, "GuideLog_2026-01-15_201500.txt")
    fx["debug"] = os.path.join(d, "DebugLog_2026-01-15_201500.txt")
    fx["glog"] = os.path.join(d, "libtoupcam_latest.glog")
    fx["unknown"] = os.path.join(d, "notes.txt")
    write(fx["guide"], encrypt_lines(gl, 11))
    write(fx["debug"], encrypt_lines(dl, 12))
    write(fx["glog"], "\n".join(GLOG_PLAIN) + "\n")
    write(fx["unknown"], "shopping list\nmilk\nbread\n")
    write(os.path.join(d, "image.fits"), b"SIMPLE  =                    T")
    write(os.path.join(d, "sub", "DebugLog_2026-01-16_010000.txt"), encrypt_lines(dl[:50], 13))
    # extra inputs kept outside the main folder
    e = os.path.join(tmp, "extra")
    fx["guide_plain"] = os.path.join(e, "GuideLog_plain.txt")
    write(fx["guide_plain"], "\n".join(gl) + "\n")
    fx["debug_plain"] = os.path.join(e, "DebugLog_plain.txt")
    write(fx["debug_plain"], "\n".join(dl) + "\n")
    fx["debug_nodate"] = os.path.join(e, "DebugLog_nodate.txt")
    write(fx["debug_nodate"], encrypt_lines(dl, 14))
    gv9, _ = guide_plain(version="9.9.9")
    fx["guide_v9"] = os.path.join(e, "GuideLog_2026-01-15_201501.txt")
    write(fx["guide_v9"], encrypt_lines(gv9, 15))
    return fx


def main():
    tmp = tempfile.mkdtemp(prefix="svtest_")
    try:
        fx = build_fixtures(tmp)
        t_cipher()
        t_sniff(fx)
        t_decode_exact(fx, tmp)
        t_redact(fx, tmp)
        t_redact_doubt()
        t_toggles(fx, tmp)
        t_header(fx, tmp)
        t_guide_location_kept(fx, tmp)
        t_date(fx, tmp)
        t_phd2(fx, tmp)
        t_files(fx, tmp)
        t_report(fx, tmp)
        t_version(fx, tmp)
        t_cli(fx, tmp)
        t_progress_i18n(fx, tmp)
        t_menu(fx, tmp)
        t_gui(fx, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d Tests, %d bestanden, %d fehlgeschlagen, %d uebersprungen"
          % (len(RESULTS), len(RESULTS) - len(failed), len(failed), len(SKIPPED)))
    for n, why in SKIPPED:
        print("  SKIP:", n, "--", why)
    for n, _, d in failed:
        print("  FAIL:", n, ("-- " + d) if d else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
