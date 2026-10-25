#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 ph3x
# SPDX-License-Identifier: GPL-3.0-or-later
#
# phdlogview_parse() is a Python port of parts of phdlogview's logparser.cpp,
# which is licensed under the GPL v3. Copyright of that code remains with the
# phdlogview authors.
"""
Test suite for decovita.py.

Builds synthetic, fully fictitious log files (all SSIDs, passwords, serial
numbers, IPs and coordinates below are made up), encrypts them with the
inverse cipher, runs the tool and checks every documented behaviour.

Run:  python3 test_decovita.py [path/to/decovita.py]
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
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "decovita.py")
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


# Phone app log (Logs_App_*.txt, #18).  Every line mirrors a real app-log line
# format; all values are invented.
APP_FAKE = {
    "mac": "de:ad:be:ef:00:01", "ip_phone": "192.168.77.105", "ip_box": "10.0.42.1",
    "lat7": "12.3456789", "lon7": "23.4567891", "alt": "345.67890123", "msl": "298.7654321",
    "model": "FAKE-MODEL1",
}


def app_plain():
    F, A = FAKE, APP_FAKE
    L = []

    def a(text, ts="2026-01-15 20:15:%02d"):
        L.append((ts % (len(L) % 60)) + " | " + text if ts else text)
    a("SplashActivity onCreate, isAppRestart=true, isSplashActivity=true, localeBeforeSuper=eLanguage_DE")
    a("BoxConnectionService loadBridgeHost" + F["ip_dev"])
    a("BoxDeviceManager Bridge IP: " + F["ip_dev"])
    a("tryConnectNew: trying cached discovery address " + F["ip_dev"])
    a("logCallback: [CoreClient] connect %s:4700 failed" % F["ip_other"])
    a('logCallback: [CoreClient][RES] {"id":5,"command_type":"CMD_GLOBAL_GET_BRIDGE_WIFI_STATUS":{"is_connected":true,'
      '"ssid":"%s","ip":"%s","subnet_mask":"255.255.255.0","gateway":"%s"}}' % (F["ssid_short"], F["ip_dev"], F["ip_gw"]))
    a('logCallback: [CoreClient][RES] {"id":6,"command_type":"CMD_GLOBAL_GET_WIFI":{"ssid":"%s","password":"%s"}}'
      % (F["ssid_long"], F["password"]))
    a("RecordWifiTrace wifi connected ssid=%s, bssid=%s, previousBssid=%s, frequency=5180"
      % (F["ssid_short"], A["mac"], A["mac"]))
    a("RecordWifiTrace NETWORK_STATE_CHANGED state=CONNECTED, previousSsid=%s, previousBssid=%s"
      % (F["ssid_short"], A["mac"]))
    a("RecordWifiTrace networkCallback onCapabilitiesChanged network=123, capabilities=[ Transports: WIFI "
      "Capabilities: NOT_METERED&INTERNET&NOT_RESTRICTED LinkUpBandwidth>=12000Kbps LinkDnBandwidth>=30000Kbps "
      "TransportInfo: <SSID: <unknown ssid>, BSSID: 02:00:00:00:00:00, MAC: 02:00:00:00:00:00, IP: /%s, "
      "Security type: 2, Supplicant state: COMPLETED, Wi-Fi standard: 11ax, RSSI: -55, Link speed: 573Mbps]"
      % A["ip_phone"])
    a("lastWifiName:--curWifi:%s--curBoxWifi:%s" % (F["ssid_short"], F["ssid_long"]))
    a("lastWifiName:--curWifi:--curBoxWifi:" + F["ssid_long"])
    a("StellaVitaFragment Wi-Fi bridge=====%s-true--true-----false" % F["ssid_short"])
    a("StellaVitaFragment Wi-Fi bridge=====-false--false-----false")
    a("StellaVitaFragment Wi-Fi bridge=====null-false--false-----false")
    a("Update Wi-Fi name: %s mIsBoxConnected:true" % F["ssid_short"])
    a("Update Wi-Fi name:  mIsBoxConnected:false")
    a("Mount test switch enable state, mIsBoxConnected:true selected device:EQMod Mount")
    a("RecordWifiTrace wifi connected ssid=FAKE_CAFE_NET, bssid=02:00:00:00:00:00, previousBssid=, frequency=2412")
    a("LegacyProtocolConnection socket error and connect lost: failed to connect to /%s (port 4700) "
      "from /%s (port 41234) after 3000ms" % (A["ip_box"], A["ip_phone"]))
    a("OTA server final address: http://203.0.113.10:8080/firmware/  local path: "
      "/data/user/0/com.touptek.astrostation/files")
    a('logCallback: [CoreClient][RES] {"id":7,"command_type":"CMD_GLOBAL_GET_DATA_BUNDLE":{"tp_sdk_version":'
      '"60.32549.20260908","poaefw_sdk_version":"1.2.3.0","wifi_ssid":"%s","wifi_password":"%s"}}'
      % (F["ssid_long"], F["password"]))
    a('logCallback: [CoreClient][REQ] {"id":8,"command_type":"CMD_GLOBAL_REPORT_INFO":{"info":"ip:%s AppInfo : '
      'versionName1.2.34 versionCode:56  DeviceInfo : brand:FAKEBRAND manufacturer:FAKEBRAND model:%s '
      'device:FAKEDEV product:FAKEPROD hardware:qcom board:FAKEB androidVersion:15 apiLevel:35 '
      'securityPatch:2026-01-01 pid:12345 builddate: 1.0.12.20260101"}}' % (A["ip_phone"], A["model"]))
    a('logCallback: [CoreClient][RES] {"id":123,"command_type":"CMD_MOUNT_GET_LOCATION":{"longitude":%s,"latitude":%s}}'
      % (F["lon_json"], F["lat_json"]))
    a("Data1 longitude-time1 0-----%s latitude %s-=---5.21----17.8" % (A["lon7"], A["lat7"]))
    a("BrokenLineView drawTwilightBackgroundutcTimeZoneHourOffset [2026, 1, 15, 20, 15, 30]   1.0---%s---%s"
      % (A["lat7"], A["lon7"]))
    a("BrokenLineView drawTwilightBackground low-frequency: 0+++0+++0+++0")
    a("BrokenLineView drawTwilightBackground low-frequency details 0---TwilightData{mYears=2026, mMonths=1, "
      "mDays=16, mHours=5, mMinutes=12, mSeconds=33.123456789012345, mGmtoff=-1234567890123456789}---"
      "TwilightData{mYears=2026, mMonths=1, mDays=15, mHours=17, mMinutes=48, mSeconds=7.987654321098765, mGmtoff=0}")
    a("Data1 UT time 2026 1 15 19 15 30 offset 1.0")
    for deg, kind, t in (("-18", "rise", "16 5 12 33.123456789012345"), ("-18", "down", "15 17 48 7.987654321098765"),
                         ("-0.833", "sunrise", "16 6 41 2.5"), ("-0.833", "sunset", "15 16 19 38.25")):
        a("Data1 %s deg %s time %s" % (deg, kind, t))
    a("Update longitude and latitude: %s,%s" % (A["lon7"], A["lat7"]))
    a("bestLocation Location[gps 12******,23****** hAcc=12.345 et=+1d2h3m4s567ms alt=%s vAcc=1.5 mslAlt=%s "
      "mslAltAcc=2.0 vel=0.0 bear=0.0 {Bundle[{satellites=0, maxCn0=0, QUICKGPS=true, HDACC=0.0, "
      "SourceType=128, meanCn0=0, loc_type=1}]}]gps:[passive, network, fused, gps]" % (A["alt"], A["msl"]))
    a("bestLocation 12.345nullprovider:network")
    a("相机温度初始：-5,0℃")
    a("相机温度替换后：-5.0℃")
    a("latestToupSdkKey：1.2.34 version:60.32549.20260908")
    a("MainCameraActivity 相机 connected, temperature -5.0℃ ok")
    a("generateKey ToupTek#Server#sd#sequence 1")
    a("java.lang.NullPointerException: Attempt to invoke virtual method 'int android.graphics.Bitmap.getWidth()' "
      "on a null object reference")
    a("\tat com.touptek.astrostation.ui.FakeView.onDraw(FakeView.java:123)", ts=None)
    a("\tat android.view.View.draw(View.java:24512)", ts=None)
    a("patch version:1", ts=None)
    a("poaeFw version:1.2.3.0", ts=None)
    a("")
    rnd = random.Random(8)
    for i in range(300):
        a('logCallback: [CoreClient][EVT] {"event_type":"EVT_GUIDE_GRAPH":{"rms_ra":%.6f,"rms_dec":%.6f}}'
          % (rnd.uniform(0, 2), rnd.uniform(0, 2)))
        if i % 3 == 0:
            a("SkyMapActivity onSensorChanged azimuth view update %d" % i)
    return L


def encrypt_app_lines(lines, seed):
    rnd = random.Random(seed)
    return b"\n".join(sv.encode_app_line(l, rnd.randint(0, 94)) for l in lines) + b"\n"


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
    print("\n[1] Cipher")
    rnd = random.Random(1)
    alpha = "".join(chr(c) for c in range(33, 126)) + " "
    ok = True
    for _ in range(3000):
        txt = "".join(rnd.choice(alpha) for _ in range(rnd.randint(0, 150)))
        t0 = rnd.randint(0, 94)
        if sv.decode_line(sv.encode_line(txt, t0), t0) != txt:
            ok = False; break
    check("Round trip of 3000 random lines is exact", ok)
    check("'~' collides with space as expected",
          sv.decode_line(sv.encode_line("a~b", 5), 5) == "a b")
    check("Bytes outside 33..126 pass through unchanged",
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
    check("Timestamped lines recovered with certainty for all 95 keys", ok)


def t_sniff(fx):
    print("\n[2] File type detection")
    check("encrypted GuideLog", sv.sniff(fx["guide"]) == ("guide", False), str(sv.sniff(fx["guide"])))
    check("encrypted DebugLog", sv.sniff(fx["debug"]) == ("debug", False), str(sv.sniff(fx["debug"])))
    check("plain-text GuideLog", sv.sniff(fx["guide_plain"]) == ("guide", True), str(sv.sniff(fx["guide_plain"])))
    check("plain-text DebugLog", sv.sniff(fx["debug_plain"]) == ("debug", True), str(sv.sniff(fx["debug_plain"])))
    check(".glog", sv.sniff(fx["glog"]) == ("glog", True), str(sv.sniff(fx["glog"])))
    check("unknown file", sv.sniff(fx["unknown"])[0] == "unknown", str(sv.sniff(fx["unknown"])))


def t_decode_exact(fx, tmp):
    print("\n[3] Decoding (without redaction) equals plain text")
    out = os.path.join(tmp, "o_dec")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=(), make_phd2=False, log=quiet)
    got = body(r["outputs"][0])
    exp = fx["guide_lines"]
    bad = [i for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    check("GuideLog: all %d lines exact" % len(exp), len(got) == len(exp) and not bad,
          "mismatches at %s" % bad[:5])
    check("GuideLog: no uncertain lines", r["uncertain"] == 0, str(r["uncertain"]))
    r = sv.process_file(fx["debug"], out_dir=out, enabled=(), full_date=False, log=quiet)
    got = body(r["outputs"][0])
    exp = fx["debug_lines"]
    bad = [i for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    check("DebugLog: all %d lines exact (incl. camera config dump)" % len(exp),
          len(got) == len(exp) and not bad, "mismatches at %s" % bad[:5])
    # the bit-string line '1111...000' is inherently ambiguous (a shifted key gives
    # another all-digit string), so exactly that one line must be flagged uncertain
    check("DebugLog: exactly the ambiguous digit line is flagged uncertain",
          r["uncertain"] == 1, str(r["uncertain"]))
    _, anch, mg = sv.recover(sv.encode_line("  Label      : ISO Speed", 40), sv.train_model(fx["debug"]))
    check("unambiguous text line without anchor: large margin", not anch and mg >= sv.UNCERTAIN_MARGIN, "%.1f" % mg)


def _debug_out(fx, tmp, name, enabled, full_date=False):
    out = os.path.join(tmp, name)
    os.makedirs(out)
    r = sv.process_file(fx["debug"], out_dir=out, enabled=enabled, full_date=full_date, log=quiet)
    return r, "\n".join(body(r["outputs"][0]))


def t_redact(fx, tmp):
    print("\n[4] Redaction (all categories on)")
    F = FAKE
    r, txt = _debug_out(fx, tmp, "o_red", sv.CATEGORIES)
    # hotspot
    for k in ("ssid_short", "ssid_long", "password"):
        check("Hotspot: '%s' gone everywhere" % k, F[k] not in txt)
    check("Hotspot: SSIDs numbered (<SSID_1>, <SSID_2>)", "<SSID_1>" in txt and "<SSID_2>" in txt)
    check("Hotspot: no leftover '_EXT' (longer SSID replaced first)", "_EXT" not in txt)
    long_tok = re.search(r'"ssid":"(<SSID_\d>)"', txt).group(1)
    check("Hotspot: free-text occurrence replaced with the same placeholder",
          ("connected to %s ok" % long_tok) in txt)
    check("Hotspot: password fields -> <REDACTED>",
          '"password":"<REDACTED>"' in txt and '"wifi_password":"<REDACTED>"' in txt)
    # network
    check("Network: 3rd octet masked, device stays distinguishable (192.168.<N1>.23)",
          "ipv4:192.168.<N1>.23:44034" in txt)
    check("Network: gateway in the same subnet gets the same token (192.168.<N1>.1)",
          '"connected_bridge_wifi_gateway":"192.168.<N1>.1"' in txt)
    check("Network: second subnet gets its own token (192.168.<N2>.5)", '"ip":"192.168.<N2>.5"' in txt)
    check("Network: 'ip:' info masked", '"info":"ip:192.168.<N1>.23"' in txt)
    check("Network: subnet masks unchanged", txt.count('255.255.255.0') == 2)
    check("Network: version strings unchanged (1.2.3.4, 60.32549.20260908)",
          '"poaefw_sdk_version":"1.2.3.4"' in txt and "60.32549.20260908" in txt)
    for ip in ("192.168.77.", "192.168.88."):
        check("Network: '%s' gone everywhere" % ip, ip not in txt)
    # location
    for k in ("lat_json", "lon_json", "lat_json7", "lon_json7", "lat_indi", "lon_indi",
              "elev", "alt", "az", "lst", "utc", "spa_alt"):
        check("Location: original value %s gone" % k, F[k] not in txt)
    check("Location: JSON coordinates rounded to 1 decimal",
          '"latitude":12.3,"longitude":-23.5' in txt)
    check("Location: INDI LAT/LONG rounded",
          "name = LAT, label = Lat (dd:mm:ss), value = 12.3," in txt and
          "name = LONG, label = Lon (dd:mm:ss), value = 336.5," in txt)
    for nm in ("ELEV", "ALT", "AZ", "LST", "SYNCPOLARALIGN_ALT"):
        check("Location: %s value -> <REDACTED>" % nm,
              re.search(r"name = %s, .*value = <REDACTED>" % nm, txt) is not None)
    check("Location: UTC time -> <REDACTED>", "name = UTC, label = UTC Time, text = <REDACTED>" in txt)
    check("Location: RA/DEC kept", "value = 1.330000" in txt and "value = 58.300000" in txt)
    # serial
    for k in ("serial32", "serial12", "artist"):
        check("Serial: '%s' gone" % k, F[k] not in txt)
    check("Serial: empty owner field stays empty",
          re.search(r"Config: /main/settings/ownername\n(?:.*\n){3}  Current    : \n", txt + "\n") is not None)
    check("Serial: ISO value (not sensitive) kept", "  Current    : 1600" in txt)
    check("Serial: CONNECTION_SERIAL switch kept",
          "name = CONNECTION_SERIAL, label = Serial, state = on" in txt)
    check("Counter per category > 0", all(r["redactions"][c] > 0 for c in sv.CATEGORIES),
          str(r["redactions"]))


def t_redact_doubt():
    print("\n[5] Redaction when in doubt (mis-decoded line in a serial block)")
    red = sv.Redactor(sv.CATEGORIES)
    seq = ["Config: /main/status/serialnumber", "  Label      : Serial Number",
           "mm2daaT]cmmmm)m }}FAKEGARBLE", "[20:00:00.000] next", "Config: /main/imgsettings/iso",
           "zz garbled but not sensitive"]
    out = [red.feed(l) for l in seq]
    check("unknown line in a sensitive block -> whole line <REDACTED>", out[2] == sv.REDACTED, out[2])
    check("Label line kept", out[1] == seq[1])
    check("Block ends at a timestamped line", out[3] == seq[3])
    check("non-sensitive block left untouched", out[5] == seq[5])


def t_toggles(fx, tmp):
    print("\n[6] Categories can be switched off individually")
    F = FAKE
    probes = {"hotspot": F["ssid_long"], "network": F["ip_dev"],
              "location": F["lat_indi"], "serial": F["serial32"]}
    for off in sv.CATEGORIES:
        en = tuple(c for c in sv.CATEGORIES if c != off)
        _, txt = _debug_out(fx, tmp, "o_tog_" + off, en)
        ok_off = probes[off] in txt
        ok_on = all(probes[c] not in txt for c in en)
        check("without '%s': its data kept, rest redacted" % off, ok_off and ok_on)
    _, txt = _debug_out(fx, tmp, "o_tog_none", ())
    check("--no-redact: everything kept", all(v in txt for v in probes.values()))


def t_header(fx, tmp):
    print("\n[7] Output header")
    out = os.path.join(tmp, "o_hdr")
    os.makedirs(out)
    r = sv.process_file(fx["debug"], out_dir=out, enabled=("hotspot", "serial"),
                        full_date=False, lang="de", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("Header DE lists only active categories",
          "# Geschwärzt: Hotspot/WLAN, Seriennummern" in head, str(head))
    check("Header DE warns about categories not redacted",
          any(l.startswith("# ACHTUNG nicht geschwärzt") and "Netzwerkadressen, Standort" in l for l in head), str(head))
    check("Header DE names the tool DecoVita",
          head[0].startswith("# Mit DecoVita v%s entschlüsselt." % sv.TOOL_VERSION), head[0])
    src = open(TOOL, encoding="utf-8").read()
    check("tool is not called 'StellaVita Log Tool' anywhere (trademark, #16)",
          "StellaVita Log Tool" not in src)
    check("Header: 'unofficial' and originals note",
          "Inoffiziell" in head[0] and any("Originaldateien" in l for l in head))
    out3 = os.path.join(tmp, "o_hdr_all")
    os.makedirs(out3)
    r = sv.process_file(fx["debug"], out_dir=out3, enabled=sv.CATEGORIES, full_date=False, lang="de", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("everything redacted: no ACHTUNG line", not any("ACHTUNG" in l for l in head), str(head))
    out2 = os.path.join(tmp, "o_hdr_en")
    os.makedirs(out2)
    r = sv.process_file(fx["debug"], out_dir=out2, enabled=(), full_date=False, lang="en", log=quiet)
    head = [l for l in open(r["outputs"][0], encoding="utf-8").read().split("\n") if l.startswith("# ")]
    check("Header EN names the tool DecoVita",
          head[0].startswith("# Decoded with DecoVita v%s." % sv.TOOL_VERSION), head[0])
    check("Header EN 'Redacted: nothing'", "# Redacted: nothing" in head, str(head))
    check("Header EN warns (WARNING not redacted)", any(l.startswith("# WARNING not redacted") for l in head), str(head))


def t_guide_location_kept(fx, tmp):
    print("\n[8] GuideLog location kept (decision: ~10 km is acceptable)")
    out = os.path.join(tmp, "o_gloc")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=sv.CATEGORIES, log=quiet)
    got = body(r["outputs"][0])
    check("GuideLog with all categories == plain text", got == fx["guide_lines"])


def t_date(fx, tmp):
    print("\n[9] Full date in the DebugLog")
    r, txt = _debug_out(fx, tmp, "o_date", (), full_date=True)
    lines = txt.split("\n")
    check("lines before midnight dated 2026-01-15",
          "[2026-01-15 23:59:59.900] [CoreServer] tick before midnight" in lines)
    check("lines after midnight dated 2026-01-16",
          "[2026-01-16 00:00:00.100] [CoreServer] tick after midnight" in lines)
    check("lines without timestamp unchanged", "Config: /main/status/serialnumber" in lines)
    _, txt2 = _debug_out(fx, tmp, "o_nodate", (), full_date=False)
    check("--no-full-date: original format", "[23:59:59.900] [CoreServer] tick before midnight" in txt2)
    out = os.path.join(tmp, "o_noname")
    os.makedirs(out)
    msgs = []
    r = sv.process_file(fx["debug_nodate"], out_dir=out, enabled=(), full_date=True, log=msgs.append)
    check("no date in the file name: warning", "no_date" in r["warnings"])
    check("no date in the file name: no date prefixes",
          "[20:15:00.100]" in "\n".join(body(r["outputs"][0])))
    d = sv.DebugDater((2026, 1, 15))
    seq = ["[23:00:00.000] a", "[22:59:00.000] b (small backward jump)", "[00:00:01.000] c"]
    out = [d.feed(x) for x in seq]
    check("small backward jump does not count as a new day", out[1].startswith("[2026-01-15 22:59"))
    check("backward jump > 12 h = new day", out[2].startswith("[2026-01-16 00:00"))


def t_phd2(fx, tmp):
    print("\n[10] PHD2 conversion")
    out = os.path.join(tmp, "o_phd2")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, enabled=sv.CATEGORIES, log=quiet)
    phd = [p for p in r["outputs"] if p.endswith("_phd2.txt")]
    check("PHD2 file written", len(phd) == 1)
    lines = body(phd[0])
    exp = fx["guide_stats"]
    check("statistics sessions/steps/drops correct",
          r["guide"] == exp, "%s vs %s" % (r["guide"], exp))
    check("first line: PHD2 version line",
          lines[0] == "PHD2 version StellaVita-2.0.37, Log version 2.5. Log enabled at 2026-01-15 20:15:00", lines[0])
    sessions, cals, errors = phdlogview_parse(lines)
    check("phdlogview parser: no errors", not errors, str(errors[:3]))
    check("phdlogview parser: 1 calibration, 2 sessions", len(cals) == 1 and len(sessions) == 2,
          "%d/%d" % (len(cals), len(sessions)))
    n_entries = sum(len(s["entries"]) for s in sessions)
    check("phdlogview parser: all steps + drops as entries",
          n_entries == exp["steps"] + exp["drops"], "%d" % n_entries)
    drops = [e for s in sessions for e in s["entries"] if e[3] == '"DROP"']
    check("drops with error code != 0", len(drops) == exp["drops"] and all(e[2] != 0 for e in drops))
    txt = "\n".join(lines)
    for code, desc in ((7, "Star lost - mass changed"), (2, "Star lost - low SNR / not found"),
                       (8, "Star lost - moved too far"), (4, "Star lost - too near edge")):
        check("drop description for StarErr %d" % code, ',%d,"%s"' % (code, desc) in txt)
    mono = all(all(b[1] > a[1] for a, b in zip(s["entries"], s["entries"][1:])) for s in sessions)
    check("time axis strictly increasing per session (incl. estimated drop times)", mono)
    check("calibration directions W/E/Backlash/N/S recognised",
          cals[0]["entries"] == ["West", "West", "East", "Backlash", "North", "South"], str(cals[0]["entries"]))
    check("NudgeSouth as header text (as phdlogview treats it)",
          any(h.startswith("NudgeSouth,") for h in cals[0]["hdr"]))
    infos = [i for s in sessions for i in s["infos"]]
    check("INFO lines kept (settling/dither/lock)",
          any("DITHER by" in i for i in infos) and any("SET LOCK POSITION" in i for i in infos)
          and any("Settling complete" in i for i in infos))
    check("stray 'Guiding Ends' before calibration dropped",
          txt.count("Guiding Ends at") == 2)
    check("session across midnight: start time correct",
          sessions[1]["start"] == "2026-01-15 23:59:30")
    out2 = os.path.join(tmp, "o_nophd2")
    os.makedirs(out2)
    r = sv.process_file(fx["guide"], out_dir=out2, make_phd2=False, log=quiet)
    check("--no-phd2: no PHD2 file", not any(p.endswith("_phd2.txt") for p in r["outputs"]))


def t_files(fx, tmp):
    print("\n[11] Files")
    before = {k: sha(fx[k]) for k in ("guide", "debug", "glog")}
    out = os.path.join(tmp, "o_files")
    os.makedirs(out)
    r = sv.process_file(fx["guide"], out_dir=out, log=quiet)
    names = sorted(os.path.basename(p) for p in r["outputs"])
    check("names: _decoded.txt and _phd2.txt",
          names == ["GuideLog_2026-01-15_201500_decoded.txt", "GuideLog_2026-01-15_201500_phd2.txt"], str(names))
    check("output folder is used", all(os.path.dirname(p) == out for p in r["outputs"]))
    p0 = r["outputs"][0]
    m0, s0 = os.path.getmtime(p0), sha(p0)
    msgs = []
    r2 = sv.process_file(fx["guide"], out_dir=out, enabled=(), log=msgs.append)
    check("without --force nothing is overwritten", sha(p0) == s0 and not r2["outputs"])
    check("message when skipping", any("force" in m for m in msgs))
    r3 = sv.process_file(fx["guide"], out_dir=out, enabled=(), force=True, log=quiet)
    check("with --force overwritten", sha(p0) != s0)
    rg = sv.process_file(fx["glog"], out_dir=out, log=quiet)
    check(".glog -> _redacted.glog", [os.path.basename(p) for p in rg["outputs"]] == ["libtoupcam_latest_redacted.glog"])
    check(".glog: content kept (nothing to redact)", body(rg["outputs"][0]) == GLOG_PLAIN)
    check(".glog: header with redaction note",
          open(rg["outputs"][0], encoding="utf-8").readline().startswith("# "))
    # #17: without redaction the .glog must not be called _redacted
    out_nr = os.path.join(tmp, "o_glog_nr")
    rn = sv.process_file(fx["glog"], out_dir=out_nr, enabled=(), log=quiet)
    check(".glog with --no-redact -> _plain.glog",
          [os.path.basename(p) for p in rn["outputs"]] == ["libtoupcam_latest_plain.glog"],
          str([os.path.basename(p) for p in rn["outputs"]]))
    check(".glog with --no-redact: content unchanged", body(rn["outputs"][0]) == GLOG_PLAIN)
    rpart = sv.process_file(fx["glog"], out_dir=os.path.join(tmp, "o_glog_part"),
                            enabled=("network",), log=quiet)
    check(".glog with some categories -> still _redacted.glog",
          [os.path.basename(p) for p in rpart["outputs"]] == ["libtoupcam_latest_redacted.glog"])
    check("_plain.glog counts as our own output", sv.is_our_output(rn["outputs"][0]))
    # folder mode must not read the _plain output back in as input
    fold = os.path.join(tmp, "glog_fold")
    os.makedirs(fold)
    shutil.copy(fx["glog"], fold)
    shutil.copy(rn["outputs"][0], fold)
    got = sorted(os.path.basename(f) for f in sv.gather([fold], recursive=False))
    check("folder: _plain.glog output is skipped", got == ["libtoupcam_latest.glog"], str(got))
    sv.process_all(sv.gather([fold], recursive=False), enabled=(), log=quiet)
    check("folder run: no _plain_plain.glog", sorted(os.listdir(fold)) ==
          ["libtoupcam_latest.glog", "libtoupcam_latest_plain.glog"], str(sorted(os.listdir(fold))))
    gi = open(os.path.join(HERE, ".gitignore"), encoding="utf-8").read().split()
    check(".gitignore covers every output suffix",
          all(("*%s*" % s) in gi or ("*%s.txt" % s) in gi for s in sv.OUT_SUFFIXES), str(gi))
    for rd in ("README.md", "README.de.md"):
        txt = open(os.path.join(HERE, rd), encoding="utf-8").read()
        check("%s names the _plain.glog output" % rd, "_plain.glog" in txt)
    for o in r["outputs"]:
        check("header in %s" % os.path.basename(o), open(o, encoding="utf-8").readline().startswith("# "))
    after = {k: sha(fx[k]) for k in ("guide", "debug", "glog")}
    check("originals unchanged", before == after)
    # folder gathering
    files = sv.gather([fx["dir"]], recursive=False)
    base = sorted(os.path.basename(f) for f in files)
    check("folder: own outputs and .fits are skipped",
          not any(b.endswith(("_decoded.txt", "_phd2.txt")) for b in base) and "image.fits" not in base, str(base))
    check("folder without -r: no subfolders", not any("sub" in f for f in files))
    files_r = sv.gather([fx["dir"]], recursive=True)
    check("folder with -r: subfolders included", any(os.sep + "sub" + os.sep in f for f in files_r))
    msgs = []
    ru = sv.process_file(fx["unknown"], out_dir=out, log=msgs.append)
    check("unknown file: skipped with a message", ru["skipped"] == "unknown" and msgs)
    rp = sv.process_file(fx["guide_plain"], out_dir=out, log=quiet)
    check("already decoded GuideLog: processed without decoding again",
          body(rp["outputs"][0]) == fx["guide_lines"])
    # re-feeding our own output as plain input must strip the old header
    own = os.path.join(tmp, "own_copy.txt")
    shutil.copy(r3["outputs"][0], own)
    out3 = os.path.join(tmp, "o_own")
    os.makedirs(out3)
    ro = sv.process_file(own, out_dir=out3, enabled=(), log=quiet)
    hdr = [l for l in open(ro["outputs"][0], encoding="utf-8") if l.startswith("# ")]
    ref_hdr = [l for l in sv._redaction_header((), "en").split("\n") if l]
    check("own output as input: old header not duplicated",
          len(hdr) == len(ref_hdr), "%d vs %d" % (len(hdr), len(ref_hdr)))


def t_report(fx, tmp):
    print("\n[12] Dry run")
    out = os.path.join(tmp, "o_rep")
    os.makedirs(out)
    msgs = []
    r = sv.process_file(fx["debug"], out_dir=out, report=True, full_date=False, log=msgs.append)
    check("dry run writes nothing", os.listdir(out) == [])
    check("dry run reports categories", any("Hotspot" in m for m in msgs), str(msgs))
    r2, _ = _debug_out(fx, tmp, "o_rep_real", sv.CATEGORIES)
    check("dry run counters == real run", r["redactions"] == r2["redactions"],
          "%s vs %s" % (r["redactions"], r2["redactions"]))
    rg = sv.process_file(fx["guide"], out_dir=out, report=True, log=quiet)
    check("dry run GuideLog writes nothing", os.listdir(out) == [])


def t_version(fx, tmp):
    print("\n[13] Version check")
    out = os.path.join(tmp, "o_ver")
    os.makedirs(out)
    r = sv.process_file(fx["guide_v9"], out_dir=out, log=quiet)
    check("unknown log version -> warning", any(w.startswith("version:9.9.9") for w in r["warnings"]),
          str(r["warnings"]))
    r = sv.process_file(fx["guide"], out_dir=out, force=True, log=quiet)
    check("known version -> no warning", not r["warnings"], str(r["warnings"]))


def t_cli(fx, tmp):
    print("\n[14] Command line")
    py = sys.executable
    p = subprocess.run([py, TOOL, "--help"], capture_output=True, text=True)
    check("--help", p.returncode == 0 and "--no-redact-location" in p.stdout)
    check("--help: license notice", "GPL-3.0-or-later" in p.stdout and "NO WARRANTY" in p.stdout)
    check("--help: -o creates the folder if missing", "created if missing" in " ".join(p.stdout.split()))
    out = os.path.join(tmp, "o_cli")
    nested = os.path.join(tmp, "o_cli_new", "a", "b")
    p = subprocess.run([py, TOOL, fx["glog"], "-o", nested], capture_output=True, text=True)
    check("-o: missing (nested) folder is created",
          p.returncode == 0 and os.listdir(nested) == ["libtoupcam_latest_redacted.glog"],
          (p.stderr or p.stdout)[-300:])
    nested_rep = os.path.join(tmp, "o_cli_rep_new", "a")
    subprocess.run([py, TOOL, fx["glog"], "-o", nested_rep, "--report"], capture_output=True, text=True)
    check("-o with --report: folder is not created", not os.path.exists(os.path.dirname(nested_rep)))
    p = subprocess.run([py, TOOL, fx["dir"], "-o", out, "--lang", "de"], capture_output=True, text=True)
    check("folder run exit code 0", p.returncode == 0, p.stderr[-300:])
    check("German messages", "Fertig:" in p.stdout, p.stdout[:200])
    made = sorted(os.listdir(out))
    check("all outputs written",
          {"GuideLog_2026-01-15_201500_decoded.txt", "GuideLog_2026-01-15_201500_phd2.txt",
           "DebugLog_2026-01-15_201500_decoded.txt", "libtoupcam_latest_redacted.glog"} <= set(made), str(made))
    check("unknown file reported", "notes.txt" in p.stdout)
    p = subprocess.run([py, TOOL, fx["debug"], "-o", out, "--lang", "en", "--force",
                        "--no-redact-network"], capture_output=True, text=True)
    txt = open(os.path.join(out, "DebugLog_2026-01-15_201500_decoded.txt"), encoding="utf-8").read()
    check("--no-redact-network works", FAKE["ip_dev"] in txt and FAKE["ssid_long"] not in txt)
    check("English messages", "Done:" in p.stdout, p.stdout[:200])
    check("CLI: status line and summary table",
          "[1/1] DebugLog 1/1: DebugLog_2026-01-15_201500.txt" in p.stdout
          and re.search(r"^#\s+Type\s+File\s+Lines", p.stdout, re.M) is not None, p.stdout[-600:])
    check("CLI: stdout free of control characters (redirect-safe)",
          all(ch.isprintable() or ch == "\n" for ch in p.stdout))
    check("singular for one file ('1 file')", "(1 file," in p.stdout, p.stdout[-80:])
    p = subprocess.run([py, TOOL, fx["glog"], "-o", os.path.join(tmp, "o_cli_nr"), "--lang", "de", "--no-redact"],
                       capture_output=True, text=True)
    check("--no-redact: warning during the run", "ACHTUNG: nicht geschwärzt" in p.stdout, p.stdout[:200])
    p = subprocess.run([py, TOOL, fx["glog"], "-o", os.path.join(tmp, "o_cli_all"), "--lang", "de"],
                       capture_output=True, text=True)
    check("default run: no warning", "ACHTUNG" not in p.stdout, p.stdout[:200])
    out2 = os.path.join(tmp, "o_cli_rep")
    p = subprocess.run([py, TOOL, fx["debug"], "-o", out2, "--report"], capture_output=True, text=True)
    check("--report writes nothing", not os.path.exists(out2) or os.listdir(out2) == [])


def t_status_table(fx, tmp):
    print("\n[14c] Status per file and summary table (#14, #15)")
    files = sv.gather([fx["dir"]], recursive=True)
    calls = []
    orig = sv.sniff
    sv.sniff = lambda path, *a, **k: (calls.append(path), orig(path, *a, **k))[1]
    try:
        stats = []
        res = sv.process_all(files, lang="en", log=quiet, status=stats.append, report=True)
    finally:
        sv.sniff = orig
    check("one status line per file", len(stats) == len(files) == len(res), str(stats))
    check("status lines numbered [i/n]",
          all(st.startswith("[%d/%d] " % (i, len(files))) for i, st in enumerate(stats, 1)), str(stats))
    check("status counts per type (DebugLog 1/2, DebugLog 2/2)",
          any(" DebugLog 1/2: " in st for st in stats) and any(" DebugLog 2/2: " in st for st in stats)
          and any(" GuideLog 1/1: " in st for st in stats), str(stats))
    check("each file is sniffed only once", len(calls) == len(files), "%d vs %d" % (len(calls), len(files)))
    tab = sv.results_table(res, "en")
    head = tab[0]
    check("table: header + rule + one row per file", len(tab) == 2 + len(files), "\n".join(tab))
    col = head.index("File")
    check("table: file names aligned under 'File'",
          all(row[col:].startswith(os.path.basename(r["path"])) for row, r in zip(tab[2:], res)), "\n".join(tab))
    end = head.index("Lines") + len("Lines")
    check("table: numbers right-aligned under 'Lines'",
          all(row[:end].rstrip() == row[:end] for row in tab[2:]), "\n".join(tab))
    check("table: dry run rows marked", sum(row.endswith("dry run") for row in tab) == len(files) - 1,
          "\n".join(tab))
    unk = [row for row in tab[2:] if "notes.txt" in row][0]
    check("table: unknown file without numbers", unk.split()[3:5] == ["-", "-"] and unk.endswith("unknown"), unk)
    check("table: plain text only", all(ch.isprintable() for row in tab for ch in row))
    out = os.path.join(tmp, "o_tab")
    os.makedirs(out)
    sv.process_all([fx["guide"]], log=quiet, status=quiet, out_dir=out)
    again = sv.process_all([fx["guide"]], log=quiet, status=quiet, out_dir=out)
    row = sv.results_table(again, "de")[2]
    check("table DE: existing outputs -> 'existiert', no numbers",
          row.endswith("existiert") and " 180 " not in row, row)
    check("table DE: German headers", sv.results_table(again, "de")[0].split()[:4] == ["#", "Typ", "Datei", "Zeilen"],
          sv.results_table(again, "de")[0])


def t_progress_i18n(fx, tmp):
    print("\n[14b] Progress and messages in both languages")
    for lang, word in (("de", "Zeilen"), ("en", "lines")):
        buf = io.StringIO()
        old = sys.stderr
        sys.stderr = buf
        try:
            sv.make_progress(lang)(50, 100, 1234)
        finally:
            sys.stderr = old
        check("progress line %s: '%s'" % (lang.upper(), word), ("1234 " + word) in buf.getvalue(), buf.getvalue())
    empty = os.path.join(tmp, "empty_dir")
    os.makedirs(empty)
    p = subprocess.run([sys.executable, TOOL, empty, "--lang", "de"], capture_output=True, text=True)
    check("empty folder: German message", "Keine Logdateien gefunden." in p.stdout and p.returncode == 1,
          p.stdout[:200])


def t_menu(fx, tmp):
    print("\n[15] Text menu (fallback without tkinter)")
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
    check("menu runs without tkinter", p.returncode == 0, p.stderr[-300:])
    check("menu writes outputs", any(m.endswith("_phd2.txt") for m in made), str(made))
    check("menu: reason for missing window shown (Python path + error)",
          "No window: tkinter missing in" in p.stdout and sys.executable in p.stdout, p.stdout[:300])
    check("menu: GPL notice at start (EN)",
          "ABSOLUTELY NO WARRANTY" in p.stdout and sv.COPYRIGHT in p.stdout, p.stdout[:300])
    check("menu: status line and summary table",
          "[1/1] GuideLog 1/1:" in p.stdout and re.search(r"^#\s+Type\s+File", p.stdout, re.M) is not None,
          p.stdout[-600:])
    check("menu: clear prompt for categories", "Selection (e.g. 3 or 2,3)" in p.stdout, p.stdout[-300:])
    check("menu: final line with file count and duration", re.search(r"\(1 file, [\d.]+s\)", p.stdout) is not None,
          p.stdout[-200:])
    # tkinter installed but no display (SSH / console): must fall back to the menu
    try:
        import tkinter  # noqa
        have_tk = True
    except Exception:
        have_tk = False
    if not have_tk:
        skip("tkinter without display -> menu", "tkinter not installed in this Python")
    else:
        env2 = dict(os.environ, LANG="de_AT.UTF-8")
        env2.pop("DISPLAY", None)
        work2 = os.path.join(tmp, "menu_nodisp")
        os.makedirs(work2)
        shutil.copy(fx["glog"], work2)
        p = subprocess.run([sys.executable, TOOL], input=work2 + "\nn\n\n\n", capture_output=True,
                           text=True, env=env2)
        check("tkinter without display: GPL notice at start (DE)",
              "OHNE JEDE GEWÄHRLEISTUNG" in p.stdout, p.stdout[:300])
        check("tkinter without display: reason shown", "kein Bildschirm" in p.stdout, p.stdout[:300])
        check("tkinter without display: no crash, menu instead of window",
              p.returncode == 0 and "Datei oder Ordner" in p.stdout, (p.stderr or p.stdout)[-300:])
        check("tkinter without display: output written",
              any(m.endswith("_redacted.glog") for m in os.listdir(work2)), str(os.listdir(work2)))


def t_gui(fx, tmp):
    print("\n[16] Window (tkinter)")
    try:
        import tkinter  # noqa
    except Exception:
        skip("window tests", "tkinter not installed in this Python")
        return
    if not shutil.which("Xvfb"):
        skip("window tests", "Xvfb not available")
        return
    disp = ":97"
    xv = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1024x768x24"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import time
        time.sleep(1)
        env = dict(os.environ, DISPLAY=disp, DV_GUI_AUTOCLOSE="1500")
        p = subprocess.run([sys.executable, TOOL], capture_output=True, text=True, env=env, timeout=60)
        check("window starts and closes cleanly", p.returncode == 0, p.stderr[-300:])
        work = os.path.join(tmp, "gui_in")
        os.makedirs(work)
        shutil.copy(fx["guide"], work)
        env = dict(env, DV_GUI_AUTORUN=work, DV_GUI_AUTOCLOSE="6000")
        p = subprocess.run([sys.executable, TOOL], capture_output=True, text=True, env=env, timeout=60)
        made = sorted(os.listdir(work))
        check("window run writes outputs", any(m.endswith("_phd2.txt") for m in made), str(made) + p.stderr[-200:])
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
            "widgets": all(visible(root, w) for w in g.all_widgets()),
            "entries": [[e.winfo_rootx(), e.winfo_width()] for e in (g.ent_src, g.ent_out)]}
    root.destroy()
root = tk.Tk()
g = sv.build_gui(root, lang)
root.update()
res["start_text"] = g.text.get("1.0", "end").strip()
res["title"] = root.title()
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
# status line and table after a run with two files
g.out.set(out_new); g.force.set(True); g.sel.set(os.path.dirname(src)); g.go(report=True); root.update()
res["run_log"] = g.text.get("1.0", "end")
res["run_status"] = g.status.get()
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
    env = {k: v for k, v in env.items() if not k.startswith("DV_GUI_")}
    p = subprocess.run([sys.executable, "-c", _GUI_PROBE, TOOL, src, out_new, out_file, "de"],
                       capture_output=True, text=True, env=env, timeout=60)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        check("window probe runs", False, (p.stderr or p.stdout)[-400:])
        return
    for scale, label in (("1.3333", "1.0x"), ("1.6667", "1.25x"), ("2.0", "1.5x")):
        for name, what in (("default", "start size"), ("min", "minimum size"),
                           ("tiny", "200x120 requested")):
            k = "%s@%s" % (name, scale)
            check("scaling %s, %s: all controls visible (incl. Dry run/Run)"
                  % (label, what), r[k]["widgets"], str(r[k]))
            check("scaling %s, %s: source and output folder fields aligned"
                  % (label, what), r[k]["entries"][0] == r[k]["entries"][1], str(r[k]["entries"]))
    check("window: GPL notice shown at start (DE)",
          r["start_text"].startswith("DecoVita v%s - Copyright" % sv.TOOL_VERSION)
          and "OHNE JEDE GEWÄHRLEISTUNG" in r["start_text"], r["start_text"][:200])
    check("window title: DecoVita vX", r["title"] == "DecoVita v%s" % sv.TOOL_VERSION, r["title"])
    check("output folder: dry run does not create it", r["dry_created"] is False)
    check("output folder: created and contains the outputs",
          r["out_files"] == ["GuideLog_2026-01-15_201500_decoded.txt",
                             "GuideLog_2026-01-15_201500_phd2.txt"], str(r["out_files"]))
    check("output folder: nothing written next to the input",
          r["src_files"] == [os.path.basename(src)], str(r["src_files"]))
    check("window: status line per file in the log",
          "[1/1] GuideLog 1/1: GuideLog_2026-01-15_201500.txt" in r["run_log"], r["run_log"][:300])
    check("window: summary table in the log",
          re.search(r"^#\s+Typ\s+Datei\s+Zeilen", r["run_log"], re.M) is not None, r["run_log"][-500:])
    check("window: status label shows the summary at the end",
          re.match(r"\(1 Datei, [\d.]+s\)$", r["run_status"]) is not None, r["run_status"])
    check("output folder is a file: message, no run",
          r["file_msg"].startswith("Zielordner ist eine Datei:"), r["file_msg"][:200])


def t_app(fx, tmp):
    print("\n[18] Phone app logs (Logs_App_*.txt, #18)")
    F, A = FAKE, APP_FAKE
    rnd = random.Random(5)
    samples = ["2026-01-15 20:15:10 | 相机温度初始：-5,0℃", "abc 相机 def ℃ xyz", "\tat x.y(Z.java:1)",
               "plain ascii line"]
    ok = all(sv.decode_app_line(sv.encode_app_line(t, k), k) == t for t in samples for k in range(95))
    check("app cipher: round trip with Chinese text and '℃' for all 95 keys", ok)
    raw = sv.encode_app_line(samples[0], 17)
    moj = samples[0].encode("utf-8").decode("latin1").encode("utf-8")      # double-encoded UTF-8
    check("app cipher: non-ASCII bytes are the double-encoded UTF-8, passed through unchanged",
          bytes(b for b in raw if b >= 0x80) == bytes(b for b in moj if b >= 0x80))
    check("app cipher: byte decoder (device logs) garbles text after a non-ASCII char",
          sv.decode_line(sv.encode_app_line("ab 相机 temperature", 3), 3).endswith("temperature") is False)
    check("app cipher: anchored via timestamp", sv.try_known(raw, sv.decode_app_line) == samples[0])

    check("sniff: encrypted app log", sv.sniff(fx["app"]) == ("app", False), str(sv.sniff(fx["app"])))
    out = os.path.join(tmp, "o_app_nr")
    r = sv.process_file(fx["app"], out_dir=out, enabled=(), log=quiet)
    dec = os.path.join(out, "Logs_App_20260115201500_decoded.txt")
    check("app: output <stem>_decoded.txt", r["outputs"] == [dec], str(r["outputs"]))
    got, exp = (body(dec) if os.path.exists(dec) else []), fx["app_lines"]
    bad = [i for i, (g, e) in enumerate(zip(got, exp)) if g != e]
    check("app: all %d lines exact (Chinese, '℃', stack trace lines)" % len(exp),
          len(got) == len(exp) and not bad, "first diff %r" % ((got[bad[0]], exp[bad[0]]) if bad else None,))
    check("app: no uncertain lines", r["uncertain"] == 0, str(r["uncertain"]))
    check("sniff: our decoded app output is recognised as plain app log",
          os.path.exists(dec) and sv.sniff(dec) == ("app", True))
    if not os.path.exists(dec):
        return
    r2 = sv.process_file(dec, out_dir=os.path.join(tmp, "o_app_again"), enabled=(), log=quiet)
    check("app: own output read again keeps UTF-8 text",
          body(r2["outputs"][0]) == exp if r2["outputs"] else False)

    out = os.path.join(tmp, "o_app")
    r = sv.process_file(fx["app"], out_dir=out, log=quiet)
    txt = "\n".join(body(r["outputs"][0])) if r["outputs"] else ""
    check("app: redacted output written", bool(txt))
    for k in ("ssid_short", "ssid_long", "password", "ip_dev", "ip_gw", "ip_other",
              "lat_json", "lon_json"):
        check("app: '%s' gone everywhere" % k, F[k] not in txt)
    for k in ("mac", "ip_phone", "ip_box", "lat7", "lon7", "alt", "msl"):
        check("app: '%s' gone everywhere" % k, A[k] not in txt)
    check("app hotspot: ssid= / previousSsid= -> placeholders",
          "wifi connected ssid=<SSID_1>, bssid=<MAC_1>, previousBssid=<MAC_1>, frequency=5180" in txt
          and "previousSsid=<SSID_1>, previousBssid=<MAC_1>" in txt, txt[:0])
    check("app hotspot: curWifi / curBoxWifi / lastWifiName",
          "lastWifiName:--curWifi:<SSID_1>--curBoxWifi:<SSID_2>" in txt
          and "lastWifiName:--curWifi:--curBoxWifi:<SSID_2>" in txt)
    check("app hotspot: Wi-Fi bridge / Wi-Fi name",
          "Wi-Fi bridge=====<SSID_1>-true--true-----false" in txt
          and "Update Wi-Fi name: <SSID_1> mIsBoxConnected:true" in txt)
    check("app hotspot: empty and 'null' Wi-Fi names stay, no extra SSID learned",
          "Wi-Fi bridge=====-false--false-----false" in txt and "Wi-Fi bridge=====null-false" in txt
          and "Update Wi-Fi name:  mIsBoxConnected:false" in txt and "<SSID_4>" not in txt)
    check("app hotspot: SSID seen only in free text (ssid=) replaced",
          "FAKE_CAFE" not in txt and "ssid=<SSID_3>, bssid=02:00:00:00:00:00, previousBssid=," in txt)
    check("app hotspot: 'null object reference' untouched (no SSID 'null')",
          "on a null object reference" in txt and "state, mIsBoxConnected:true selected" in txt)
    check("app hotspot: Android placeholder '<unknown ssid>' kept", "<SSID: <unknown ssid>, BSSID:" in txt)
    check("app hotspot: passwords -> <REDACTED>",
          '"password":"<REDACTED>"' in txt and '"wifi_password":"<REDACTED>"' in txt)
    check("app network: MAC -> <MAC_1>, Android placeholder 02:00:00:00:00:00 kept",
          "<MAC_1>" in txt and "BSSID: 02:00:00:00:00:00, MAC: 02:00:00:00:00:00" in txt)
    check("app network: private IPs in free text masked (3rd octet)",
          "loadBridgeHost192.168.<N1>.23" in txt and "Bridge IP: 192.168.<N1>.23" in txt
          and "IP: /192.168.<N1>.105," in txt and "connect 192.168.<N2>.5:4700 failed" in txt
          and "to /10.0.<N3>.1 (port 4700)" in txt, txt[:0])
    check("app network: JSON ip/gateway use the same tokens", '"ip":"192.168.<N1>.23"' in txt
          and '"gateway":"192.168.<N1>.1"' in txt and '"info":"ip:192.168.<N1>.105 ' in txt)
    check("app network: public server IP, subnet mask and versions unchanged",
          "http://203.0.113.10:8080/" in txt and '"subnet_mask":"255.255.255.0"' in txt
          and '"poaefw_sdk_version":"1.2.3.0"' in txt and "poaeFw version:1.2.3.0" in txt
          and "builddate: 1.0.12.20260101" in txt and '"tp_sdk_version":"60.32549.20260908"' in txt)
    check("app location: JSON coordinates rounded",
          '"CMD_MOUNT_GET_LOCATION":{"longitude":-23.5,"latitude":12.3}' in txt)
    check("app location: Data1 / twilight / update lines rounded",
          "Data1 longitude-time1 0-----23.5 latitude 12.3-=---<REDACTED>----<REDACTED>" in txt
          and "TimeZoneHourOffset [2026, 1, 15, 20, 15, 30]   1.0---12.3---23.5" in txt
          and "Update longitude and latitude: 23.5,12.3" in txt)
    check("app location: twilight/sunrise/sunset times -> <REDACTED>, current UT time kept",
          "Data1 -18 deg rise time <REDACTED>" in txt and "Data1 -18 deg down time <REDACTED>" in txt
          and "Data1 -0.833 deg sunrise time <REDACTED>" in txt and "Data1 -0.833 deg sunset time <REDACTED>" in txt
          and "mDays=16, mHours=<REDACTED>, mMinutes=<REDACTED>, mSeconds=<REDACTED>, mGmtoff=" in txt
          and "33.1234" not in txt and "7.9876" not in txt and "38.25" not in txt
          and "Data1 UT time 2026 1 15 19 15 30 offset 1.0" in txt
          and "low-frequency: 0+++0+++0+++0" in txt)
    check("app location: GPS altitude -> <REDACTED>, accuracy kept",
          "alt=<REDACTED> vAcc=1.5 mslAlt=<REDACTED> mslAltAcc=2.0" in txt
          and "bestLocation 12.345nullprovider:network" in txt)
    check("app: phone model and Android version kept (decision #18)",
          "model:%s " % A["model"] in txt and "androidVersion:15" in txt)
    check("app: Chinese text and '℃' intact after redaction",
          "相机温度替换后：-5.0℃" in txt and "MainCameraActivity 相机 connected, temperature -5.0℃ ok" in txt)
    check("app: counters per category",
          r["redactions"]["hotspot"] > 0 and r["redactions"]["network"] > 0
          and r["redactions"]["location"] > 0 and r["redactions"]["serial"] == 0, str(r["redactions"]))

    r3 = sv.process_file(fx["app"], out_dir=os.path.join(tmp, "o_app_nonet"), log=quiet,
                         enabled=tuple(c for c in sv.CATEGORIES if c != "network"))
    t3 = "\n".join(body(r3["outputs"][0]))
    check("app: --no-redact-network keeps MAC and IPs, rest redacted",
          A["mac"] in t3 and A["ip_phone"] in t3 and F["ssid_short"] not in t3 and A["alt"] not in t3)
    red = sv.Redactor(sv.CATEGORIES)
    line = "[20:15:00.100] [Net] peer " + A["mac"]
    check("device logs: MAC rule only active for app logs", red.feed(line) == line)

    st = []
    res = sv.process_all([fx["app"]], log=quiet, status=st.append, report=True)
    check("app: status line names the type AppLog", st and " AppLog 1/1: " in st[0], str(st))
    check("app: table row type AppLog", sv.results_table(res, "en")[2].split()[1] == "AppLog",
          sv.results_table(res, "en")[2])
    check("app: dry run counts match the real run", res[0]["redactions"] == r["redactions"],
          "%s vs %s" % (res[0]["redactions"], r["redactions"]))


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
    fx["app_lines"] = al = app_plain()
    fx["app"] = os.path.join(e, "Logs_App_20260115201500.txt")
    write(fx["app"], encrypt_app_lines(al, 16))
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
        t_status_table(fx, tmp)
        t_progress_i18n(fx, tmp)
        t_menu(fx, tmp)
        t_app(fx, tmp)
        t_gui(fx, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d tests, %d passed, %d failed, %d skipped"
          % (len(RESULTS), len(RESULTS) - len(failed), len(failed), len(SKIPPED)))
    for n, why in SKIPPED:
        print("  SKIP:", n, "--", why)
    for n, _, d in failed:
        print("  FAIL:", n, ("-- " + d) if d else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
