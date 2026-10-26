#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 ph3x
# SPDX-License-Identifier: GPL-3.0-or-later
"""
DecoVita  -  decode, redact and convert ToupTek StellaVita logs.

This is an unofficial community tool. It has no connection to ToupTek Astro.

What it does
  * decodes the obfuscated GuideLog_*.txt / DebugLog_*.txt files into readable text
  * optionally redacts personal data (Wi-Fi names/passwords, IP and MAC
    addresses, location, serial numbers) - on by default, each category switchable
  * for GuideLogs it also writes a PHD2-format file that phdlogview can open
  * reads cleartext libtoupcam *.glog files (redact only)
  * decodes the phone app logs Logs_App_*.txt (non-ASCII characters do not
    advance the position, and the text is double-encoded UTF-8)

The decoding scheme was worked out from the files themselves, not from any
documentation.  Per line, only the printable characters 33..126 are used:
  t_j = (t0 + j) mod 95         (j = position in the line, t0 random per line)
  a_j = t_j - 1 if t_j > 32 else t_j
  plain = 33 + (cipher - 33 - a_j) mod 94      (126 -> space)
Space and '~' collide (95 plaintext symbols mapped onto 94); '~' is rare in
these logs and decodes to a space.

Usage:  python3 decovita.py [options] [file-or-folder ...]
Run without arguments for a window (or a text menu if tkinter is missing).
No third-party packages are required - pure standard library.

License: GNU GPL v3 or later (see LICENSE).  This program comes with
ABSOLUTELY NO WARRANTY.
"""

import os
import re
import sys
import time
import math
import argparse
import bisect

# ----------------------------------------------------------------------------
#  Version / known-good markers
# ----------------------------------------------------------------------------

TOOL_VERSION = "1.3.0"
COPYRIGHT = "Copyright (C) 2026 ph3x"
KNOWN_APP_VERSIONS = ("2.0.37",)      # GuideLog "Version:" values seen so far
KNOWN_PROTOCOL = ("2",)               # GuideLog "Version protocol:" values

OUT_SUFFIXES = ("_decoded", "_phd2", "_redacted", "_plain")

# ----------------------------------------------------------------------------
#  Cipher core
# ----------------------------------------------------------------------------

def _build_tables():
    """95 translation tables (one per effective key t), 256 bytes each."""
    tabs = []
    for t in range(95):
        a = t - 1 if t > 32 else t
        tab = bytearray(range(256))          # identity for bytes outside 33..126
        for c in range(33, 127):
            p = 33 + (c - 33 - a) % 94
            tab[c] = 32 if p == 126 else p
        tabs.append(bytes(tab))
    return tabs

_TAB = _build_tables()
_POS_CACHE = {}          # t0 -> list of tables, extended on demand
from operator import getitem as _getitem


def _pos(t0, n):
    lst = _POS_CACHE.get(t0)
    if lst is None:
        lst = []
        _POS_CACHE[t0] = lst
    if len(lst) < n:
        base = len(lst)
        for j in range(base, n):
            lst.append(_TAB[(t0 + j) % 95])
    return lst


def decode_line(raw, t0):
    """Decode one raw (bytes) line with line key t0 -> str."""
    if not raw:
        return ""
    pos = _pos(t0, len(raw))
    return bytes(map(_getitem, pos, raw)).decode("latin1")


def encode_line(text, t0):
    """Inverse of decode_line.  text (str) -> raw (bytes).  For test vectors.

    '~' in the plaintext is encoded like a space (the known collision) and will
    come back as a space when decoded.
    """
    out = bytearray(len(text))
    for j, ch in enumerate(text):
        pch = ord(ch)
        t = (t0 + j) % 95
        a = t - 1 if t > 32 else t
        if pch == 32 or pch == 126:          # space or '~'  -> raw symbol 126
            praw = 126
        elif 33 <= pch <= 125:
            praw = pch
        else:                                # non-printable: leave untouched
            out[j] = pch & 0xFF
            continue
        out[j] = 33 + (praw - 33 + a) % 94
    return bytes(out)


# ---- phone app logs (Logs_App_*.txt, issue #18) -------------------------------
# Same cipher, but bytes >= 0x80 pass through and do NOT advance the position j,
# and the text is double-encoded UTF-8 (each byte of the original UTF-8 text was
# written again as its own UTF-8 character).

def _undo_double_utf8(bs):
    try:
        s = bs.decode("utf-8")
    except UnicodeDecodeError:
        return bs.decode("latin1")
    try:
        return s.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def decode_app_line(raw, t0):
    """Decode one raw phone-app log line with line key t0 -> str."""
    if not raw:
        return ""
    if raw.isascii():
        return decode_line(raw, t0)
    asc = iter(decode_line(bytes(b for b in raw if b < 0x80), t0).encode("latin1"))
    return _undo_double_utf8(bytes(next(asc) if b < 0x80 else b for b in raw))


def encode_app_line(text, t0):
    """Inverse of decode_app_line.  For test vectors."""
    moj = text.encode("utf-8").decode("latin1")          # the double encoding
    asc = iter(encode_line("".join(c for c in moj if ord(c) < 0x80), t0))
    out = bytearray()
    for c in moj:
        if ord(c) < 0x80:
            out.append(next(asc))
        else:
            out += c.encode("utf-8")
    return bytes(out)


TS = re.compile(r'(\[\d\d:\d\d:\d\d\.\d{3}\]|\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)')


def t0_candidates(c0, first):
    s = (c0 - first) % 94
    if s < 32:
        return (s,)
    if s == 32:
        return (32, 33)
    return (s + 1,)


def try_known(raw, dec=decode_line):
    """Fast path: recover a timestamped line from its known first character.
    dec: decode_line (device logs) or decode_app_line (phone app logs)."""
    if not raw:
        return ""
    c0 = raw[0]
    for f in (0x5B, 0x32):               # '[' (DebugLog) or '2' (date lines)
        for t0 in t0_candidates(c0, f):
            d = dec(raw, t0)
            if TS.match(d):
                return d
    return None


# ---- fallback brute-force scoring (lines without a timestamp anchor) --------

_WORD = re.compile(r'[A-Za-z]{2,}')
_COMMON = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.:-=%/"{}[]()'
)
_SEED = (
    "Log begin at Platform RaspberryPi Version protocol Guiding Begins Ends "
    "Calibration Step Direction West East North South Backlash NudgeSouth complete "
    "Dither both axes scale Image noise reduction none Pixel arc-sec per px Binning "
    "Focal length mm Search region Star mass tolerance Multi-star mode list size "
    "Camera full size pixel um Exposure Mount connected guiding enabled xAngle xRate "
    "yAngle yRate parity Norm rates dec X guide algorithm Hysteresis Y Resist Switch "
    "Backlash comp disabled pulse Max RA duration DEC mode auto Guide Speed Cal Lock "
    "position Star HFD Frame Time mount dx dy RARawDistance DECRawDistance RAGuide "
    "DECGuide RADuration RADirection DECDuration DECDirection XStep YStep StarMass "
    "SNR ErrorCode INFO SETTLING STATE CHANGE Settling started complete failed SET "
    "LOCK POSITION new lock pos DITHER by CoreServer ScopeINDI received Property "
    "Number Switch Text name label value min max step Altitude Azimuth Latitude "
    "Longitude Local Sidereal Time event_type frame_number offset guide camera "
    "focuser exposure gain filter wheel meridian flip mosaic autofocus gphoto "
    "serial number copyright artist owner ssid password gateway subnet mask "
    "\nConfig: /main/settings/iso\n  Label      : ISO Speed\n  Readonly   : 0\n"
    "  Type       : RADIO\n  Current    : 100\n  Choices    : Auto, 100, 200, 400\n"
    "  Printable  : 0\n  Info       : \n11111111000000000000 0101 1000 2026-10-03 19:26:29 "
)

_TRAIN_LINES = 20000      # anchored lines of the same file used for training


def _build_model(texts):
    import collections
    c = collections.Counter()
    vocab = set()
    for t in texts:
        for a, b in zip(t, t[1:]):
            c[a + b] += 1
        vocab.update(w.lower() for w in _WORD.findall(t))
    tot = sum(c.values()) or 1
    model = {k: math.log(v / tot) for k, v in c.items()}
    floor = math.log(0.5 / tot)
    return model, floor, vocab


_MODEL = _build_model([_SEED])


def train_model(path, dec=decode_line):
    """Seed + bigrams from the first anchored (timestamped) lines of this file.
    Reads at most _TRAIN_LINES lines; the file is still processed line by line."""
    sample = []
    with open(path, "rb") as f:
        for i, ln in enumerate(f):
            if i >= _TRAIN_LINES:
                break
            d = try_known(ln.rstrip(b"\r\n"), dec)
            if d:
                sample.append(d)
    return _build_model(sample + [_SEED])


def _score(d, mdl=None):
    model, floor, vocab = mdl or _MODEL
    bigram = 0.0
    for i in range(len(d) - 1):
        bigram += model.get(d[i:i + 2], floor)
    common = 0
    for ch in d:
        if ch in _COMMON:
            common += 1
    known = 0
    for w in _WORD.findall(d):
        if w.lower() in vocab:
            known += len(w)
    return bigram + 5 * common + 10 * known


UNCERTAIN_MARGIN = 25.0     # score gap below which a guessed line counts as uncertain


def recover(raw, mdl=None, dec=decode_line):
    """Decode one line -> (text, anchored, margin).
    anchored=True: key derived from the known first character (certain).
    anchored=False: key guessed by scoring; margin = gap to the runner-up."""
    if not raw:
        return "", True, 0.0
    d = try_known(raw, dec)
    if d is not None:
        return d, True, 0.0
    best = None
    best_s = second = None
    for t0 in range(95):
        d = dec(raw, t0)
        s = _score(d, mdl)
        if best_s is None or s > best_s:
            second, best_s, best = best_s, s, d
        elif second is None or s > second:
            second = s
    margin = (best_s - second) if second is not None else 0.0
    return best, False, margin


# ----------------------------------------------------------------------------
#  File-type detection
# ----------------------------------------------------------------------------

_MK_GUIDE = ("Guiding Begins", "Calibration Step->", "Frame,Time,mount",
             "Log begin at", "Guiding Step->")
_MK_DEBUG = ("CoreServer", "ScopeINDI", "-> Number (", "received Property")
_MK_GLOG = ("libtoupcam", "EnumLibusb", "sdk: lib")
_MK_APP = ("logCallback: [CoreClient]", "SkyMapActivity", "LocationUtil",
           "RecordWifiTrace", "MainCameraActivity", "TpSkyMapHandler")


def sniff(path, sample_lines=400):
    """Return (kind, already_plain).  kind in guide/debug/glog/app/unknown."""
    raw = []
    with open(path, "rb") as f:
        for i, ln in enumerate(f):
            raw.append(ln.rstrip(b"\r\n"))
            if i + 1 >= sample_lines:
                break
    text_raw = b"\n".join(raw).decode("latin1", "replace")
    if "libtoupcam" in text_raw or "EnumLibusb" in text_raw:
        return "glog", True
    if any(m in text_raw for m in _MK_APP):
        return "app", True
    if any(m in text_raw for m in _MK_DEBUG):
        return "debug", True
    if any(m in text_raw for m in _MK_GUIDE):
        return "guide", True
    # otherwise try to decode the sample
    dec = "\n".join(recover(l)[0] for l in raw[:120] if l)
    if "libtoupcam" in dec:
        return "glog", False
    if any(m in dec for m in _MK_APP):
        return "app", False
    if any(m in dec for m in _MK_DEBUG):
        return "debug", False
    if any(m in dec for m in _MK_GUIDE):
        return "guide", False
    return "unknown", None


# ----------------------------------------------------------------------------
#  DebugLog date handling
# ----------------------------------------------------------------------------

_DATE_IN_NAME = re.compile(r'(\d{4})[-_](\d{2})[-_](\d{2})')
_TS_DEBUG = re.compile(r'^\[(\d\d):(\d\d):(\d\d)\.(\d{3})\]')


def date_from_name(path):
    m = _DATE_IN_NAME.search(os.path.basename(path))
    if not m:
        return None
    return tuple(int(x) for x in m.groups())      # (Y, M, D)


class DebugDater:
    """Prefixes DebugLog timestamps with a full date, tracking midnight rollover
    (the StellaVita Pi has no battery clock, so time can jump)."""
    def __init__(self, start_date):
        self.y, self.m, self.d = start_date
        self.prev = None

    def feed(self, line):
        mt = _TS_DEBUG.match(line)
        if not mt:
            return line
        h, mi, s = int(mt.group(1)), int(mt.group(2)), int(mt.group(3))
        secs = h * 3600 + mi * 60 + s
        if self.prev is not None and secs < self.prev - 12 * 3600:
            self._next_day()
        self.prev = secs
        date = "%04d-%02d-%02d " % (self.y, self.m, self.d)
        return "[" + date + line[1:]

    def _next_day(self):
        import datetime
        nd = datetime.date(self.y, self.m, self.d) + datetime.timedelta(days=1)
        self.y, self.m, self.d = nd.year, nd.month, nd.day


# ----------------------------------------------------------------------------
#  Redaction
# ----------------------------------------------------------------------------

CATEGORIES = ("hotspot", "network", "location", "serial")

_RE_SSID = re.compile(r'("(?:[a-z0-9_]*ssid)"\s*:\s*")((?:[^"\\]|\\.)*)(")', re.I)
_RE_PW = re.compile(r'("(?:[a-z0-9_]*(?:password|passwd|psk|pwd))"\s*:\s*")((?:[^"\\]|\\.)*)(")', re.I)
_RE_IP_PREFIX = re.compile(r'(ipv[46]:)(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})')
_RE_IP_JSON = re.compile(r'("(?:[a-z0-9_]*(?:ip|gateway))"\s*:\s*")(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(")', re.I)
_RE_IP_INFO = re.compile(r'(\bip:\s*)(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})', re.I)
_RE_NUM = re.compile(r'(--> Number#?\d*:\s*name = )([A-Z_0-9]+)(,.*?value = )(-?[\d.]+(?:[eE][-+]?\d+)?)')
_RE_TXT = re.compile(r'(--> Text#?\d*:\s*name = )(UTC|OFFSET)(,.*?text = )(\S+)')
_RE_LATLON_JSON = re.compile(r'("(?:latitude|longitude)"\s*:\s*)(-?\d+(?:\.\d+)?)', re.I)
_RE_SERIAL_JSON = re.compile(r'("(?:[a-z0-9_]*serial[a-z0-9_]*)"\s*:\s*")([^"]*)(")', re.I)
_RE_SERIAL_JSON_NUM = re.compile(r'("(?:[a-z0-9_]*serial[a-z0-9_]*)"\s*:\s*)(\d+)', re.I)
_RE_CONFIG = re.compile(r'^Config:\s*(\S+)')
_RE_CURRENT = re.compile(r'^(\s*(?:Current|Default|Choices)\s*:\s*)(.*)$')
_RE_FIELD = re.compile(r'^\s*(?:Label|Type|Readonly|Printable|Info|Bottom|Top|Step)\s*:')

# phone app logs (issue #18): free-text formats seen in real app logs
_RE_APP_SSID = (
    re.compile(r'(\b(?:ssid|previousSsid)=)([^,]+)(,)'),
    re.compile(r'((?:lastWifiName|curWifi|curBoxWifi):)(?!--cur)(.+?)((?=--cur)|$)'),
    re.compile(r'(Wi-Fi name: )(?! mIsBoxConnected:)(.+?)( mIsBoxConnected:|$)'),
    re.compile(r'(Wi-Fi bridge=====)(?!-(?:true|false)-)(.+?)(-(?:true|false)-)'),
    re.compile(r'((?<!B)SSID: )([^,]+)(,)'),
)
_SSID_NONE = frozenset(("null", "<unknown ssid>"))   # placeholders, not SSIDs
_RE_ANY_IP = re.compile(r'(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?!\.?\d)')
_RE_MAC = re.compile(r'(?<![0-9A-Fa-f:])[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}(?![0-9A-Fa-f:])')
# a version number right before a private-looking IP ("..._version":"10.1.2.3",
# EFW-10.1.2.3, v10.1.2.3) is not an address (#25); "ver" not inside "server"
_RE_VER_CTX = re.compile(r'(?:version|(?<![a-z])ver|fw|(?<![a-z])sdk)\w*["\'\s:=-]*v?$', re.I)
# the middle of any MAC; a time "12:34:56" is not one.  Literal ":" first = fast
_MAC_HINT = re.compile(r':[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:')
_MAC_KEEP = frozenset(("02:00:00:00:00:00", "00:00:00:00:00:00"))   # Android placeholders
_RE_APP_LATLON = (
    re.compile(r'(longitude and latitude: )(-?\d+(?:\.\d+)?)(,)(-?\d+(?:\.\d+)?)'),
    re.compile(r'(longitude-time\d* -?\d+-----)(-?\d+(?:\.\d+)?)( latitude )(-?\d+(?:\.\d+)?)'),
    re.compile(r'(TimeZoneHourOffset \[[^\]]*\]\s+-?[\d.]+---)(-?\d+(?:\.\d+)?)(---)(-?\d+(?:\.\d+)?)'),
)
_RE_APP_ALT = re.compile(r'(\b(?:alt|mslAlt)=)(-?\d+(?:\.\d+)?)')
# twilight / sunrise / sunset times: together with the date they give the site
_RE_APP_TWI = (
    re.compile(r'(Data\d+ -?[\d.]+ deg (?:rise|down|sunrise|sunset) time )(\S.*)$'),
    re.compile(r'(\bm(?:Hours|Minutes|Seconds)=)(-?\d+(?:\.\d+)?)'),
)
# "Data1 longitude-time1 n-----lon latitude lat-=---<dawn h>----<dusk h>"
_RE_APP_TWI_HOURS = re.compile(r'( latitude \S*?-=---)(-?\d+(?:\.\d+)?)(----)(-?\d+(?:\.\d+)?)')


def _private_ip(o1, o2):
    return (o1 == 10 or (o1 == 172 and 16 <= o2 <= 31) or (o1 == 192 and o2 == 168)
            or (o1 == 169 and o2 == 254) or (o1 == 100 and 64 <= o2 <= 127))


_LOC_BLANK = frozenset((
    "ALT", "AZ", "LST", "ELEV",
    "SYNCPOLARALIGN_ALT", "SYNCPOLARALIGN_AZ",
    "STANDARDSYNCPOINT_JD", "STANDARDSYNCPOINT_SYNCTIME",
    "ALIGNPOINT_JD", "ALIGNPOINT_SYNCTIME",
    "HORIZONLIMITS_POINT_AZ", "HORIZONLIMITS_POINT_ALT",
))
_LOC_ROUND = frozenset(("LAT", "LONG"))
_SENS_CONFIG = ("serialnumber", "eosserialnumber", "ownername", "artist", "copyright")

REDACTED = "<REDACTED>"


def _valid_ip(*octs):
    return all(0 <= int(o) <= 255 for o in octs)


class Placeholders:
    """Value -> placeholder mapping shared by every file of one run (#21).
    Numbering follows the order of first appearance.  The mapping lives in
    memory only: it is never written, logged or printed."""
    # every placeholder the redactor emits; a leak check (#20) can use it too
    PATTERN = re.compile(r'<SSID_\d+>|<REDACTED>|<N\d+>|<MAC_\d+>')

    def __init__(self):
        self.ssid = {}              # value -> token
        self.net = {}               # (o1,o2,o3) -> token
        self.mac = {}               # MAC (lower case) -> token

    @staticmethod
    def _get(table, key, fmt):
        tok = table.get(key)
        if tok is None:
            tok = table[key] = fmt % (len(table) + 1)
        return tok

    def ssid_token(self, val):
        return self._get(self.ssid, val, "<SSID_%d>")

    def net_token(self, o1, o2, o3):
        return self._get(self.net, (o1, o2, o3), "N%d")

    def mac_token(self, val):
        return self._get(self.mac, val.lower(), "<MAC_%d>")

    def __repr__(self):             # never show the values, e.g. in a traceback
        return "<Placeholders ssid=%d net=%d mac=%d>" % (
            len(self.ssid), len(self.net), len(self.mac))


class Redactor:
    """Streaming, stateful redactor.  feed(line)->line, counters in .counts.
    ph: Placeholders shared across the files of one run (default: a new one)."""
    def __init__(self, enabled, app=False, ph=None):
        self.en = {c: (c in enabled) for c in CATEGORIES}
        self.counts = {c: 0 for c in CATEGORIES}
        self.app = app              # phone app log: extra free-text rules
        self.ph = ph if ph is not None else Placeholders()
        self.ssid_map = self.ph.ssid    # alias, shared with the other files of the run
        self._cfg_sensitive = False

    # -- helpers ---------------------------------------------------------
    def _ssid_token(self, val):
        return self.ph.ssid_token(val)

    def _net_token(self, o1, o2, o3):
        return self.ph.net_token(o1, o2, o3)

    def _mac_token(self, val):
        return self.ph.mac_token(val)

    # -- category passes -------------------------------------------------
    def _do_hotspot(self, line):
        def ssid(m):
            self.counts["hotspot"] += 1
            return m.group(1) + self._ssid_token(m.group(2)) + m.group(3)
        line = _RE_SSID.sub(ssid, line)

        def pw(m):
            self.counts["hotspot"] += 1
            return m.group(1) + REDACTED + m.group(3)
        line = _RE_PW.sub(pw, line)

        # catch any stray occurrence of a known SSID elsewhere (longest first)
        if self.ssid_map:
            line = self._stray_ssids(line)
        return line

    def _do_network(self, line):
        def pref(m):
            if not _valid_ip(m.group(2), m.group(3), m.group(4), m.group(5)):
                return m.group(0)
            self.counts["network"] += 1
            tok = self._net_token(m.group(2), m.group(3), m.group(4))
            return "%s%s.%s.<%s>.%s" % (m.group(1), m.group(2), m.group(3), tok, m.group(5))
        line = _RE_IP_PREFIX.sub(pref, line)

        def js(m):
            if not _valid_ip(m.group(2), m.group(3), m.group(4), m.group(5)):
                return m.group(0)
            self.counts["network"] += 1
            tok = self._net_token(m.group(2), m.group(3), m.group(4))
            return "%s%s.%s.<%s>.%s%s" % (m.group(1), m.group(2), m.group(3), tok,
                                          m.group(5), m.group(6))
        line = _RE_IP_JSON.sub(js, line)

        def info(m):
            if not _valid_ip(m.group(2), m.group(3), m.group(4), m.group(5)):
                return m.group(0)
            self.counts["network"] += 1
            tok = self._net_token(m.group(2), m.group(3), m.group(4))
            return "%s%s.%s.<%s>.%s" % (m.group(1), m.group(2), m.group(3), tok, m.group(5))
        line = _RE_IP_INFO.sub(info, line)
        return line

    def _do_location(self, line):
        def num(m):
            name = m.group(2)
            if name in _LOC_BLANK:
                self.counts["location"] += 1
                return m.group(1) + name + m.group(3) + REDACTED
            if name in _LOC_ROUND:
                self.counts["location"] += 1
                return m.group(1) + name + m.group(3) + _round1(m.group(4))
            return m.group(0)
        if "--> Number" in line:
            line = _RE_NUM.sub(num, line)

        def txt(m):
            self.counts["location"] += 1
            return m.group(1) + m.group(2) + m.group(3) + REDACTED
        if "--> Text" in line:
            line = _RE_TXT.sub(txt, line)

        def ll(m):
            self.counts["location"] += 1
            return m.group(1) + _round1(m.group(2))
        if "latitude" in line or "longitude" in line:
            line = _RE_LATLON_JSON.sub(ll, line)
        return line

    def _do_serial(self, line):
        # stateful gphoto config dump ("Config: <path>" followed by field lines)
        mc = _RE_CONFIG.match(line) if line.startswith("Config:") else None
        if mc:
            path = mc.group(1).lower()
            self._cfg_sensitive = any(path.endswith(s) or path.endswith(s + "/")
                                      for s in _SENS_CONFIG)
            return line
        if self._cfg_sensitive:
            if line.startswith("["):              # timestamped line ends the block
                self._cfg_sensitive = False
            elif line.strip():
                mcur = _RE_CURRENT.match(line)
                if mcur:
                    if mcur.group(2).strip():
                        self.counts["serial"] += 1
                        return mcur.group(1) + REDACTED
                    return line
                if not _RE_FIELD.match(line):
                    # not a recognisable field line -> possibly mis-decoded value
                    # line; redact the whole line rather than risk a leak
                    self.counts["serial"] += 1
                    return REDACTED
        # JSON serial fields
        if "serial" in line.lower():
            def sj(m):
                self.counts["serial"] += 1
                return m.group(1) + REDACTED + m.group(3)
            line = _RE_SERIAL_JSON.sub(sj, line)

            def sjn(m):
                self.counts["serial"] += 1
                return m.group(1) + REDACTED
            line = _RE_SERIAL_JSON_NUM.sub(sjn, line)
        return line

    def _do_any_net(self, line):
        """MAC addresses and private IPv4 addresses anywhere in a line, for
        every log type (#18 app logs, #25 all).  Public addresses, subnet masks
        and version strings stay."""
        if _MAC_HINT.search(line):
            def mac(m):
                if m.group(0) in _MAC_KEEP:
                    return m.group(0)
                self.counts["network"] += 1
                return self._mac_token(m.group(0))
            line = _RE_MAC.sub(mac, line)

        def ip(m):
            o = [int(x) for x in m.groups()]
            if (max(o) > 255 or not _private_ip(o[0], o[1])
                    or _RE_VER_CTX.search(line, max(0, m.start() - 40), m.start())):
                return m.group(0)
            self.counts["network"] += 1
            tok = self._net_token(*m.groups()[:3])
            return "%s.%s.<%s>.%s" % (m.group(1), m.group(2), tok, m.group(4))
        return _RE_ANY_IP.sub(ip, line)

    def _do_app(self, line):
        """Phone app log rules (issue #18).  Runs before the generic passes, so
        SSIDs learned here are also replaced as stray occurrences."""
        if self.en["hotspot"] and ("ssid" in line.lower() or "Wifi" in line
                                   or "Wi-Fi" in line):
            def ssid(m):
                if m.group(2) in _SSID_NONE:
                    return m.group(0)
                self.counts["hotspot"] += 1
                return m.group(1) + self._ssid_token(m.group(2)) + m.group(3)
            for rx in _RE_APP_SSID:
                line = rx.sub(ssid, line)
        if self.en["location"]:
            if "latitude" in line or "TimeZoneHourOffset" in line:
                def ll(m):
                    self.counts["location"] += 2
                    return (m.group(1) + _round1(m.group(2)) + m.group(3)
                            + _round1(m.group(4)))
                for rx in _RE_APP_LATLON:
                    line = rx.sub(ll, line)
            def blank(m):
                self.counts["location"] += 1
                return m.group(1) + REDACTED
            if "Location[" in line:
                line = _RE_APP_ALT.sub(blank, line)
            if " time " in line or "TwilightData" in line:
                for rx in _RE_APP_TWI:
                    line = rx.sub(blank, line)
            if "-=---" in line:
                def hours(m):
                    self.counts["location"] += 2
                    return m.group(1) + REDACTED + m.group(3) + REDACTED
                line = _RE_APP_TWI_HOURS.sub(hours, line)
        return line

    # -- public ----------------------------------------------------------
    def feed(self, line):
        if self.app:
            line = self._do_app(line)
        # cheap pre-check (#25): substring tests first, so the regexes of
        # _do_any_net run on few lines of a large DebugLog
        if self.en["network"] and (
                "192.168." in line or "10." in line or "172." in line
                or "169.254." in line or "100." in line
                or (line.count(":") >= 5 and _MAC_HINT.search(line))):
            line = self._do_any_net(line)
        low = line.lower()
        # serial first (stateful on Config/Current lines)
        if self.en["serial"] and (self._cfg_sensitive or line.startswith("Config:")
                                  or "serial" in low):
            line = self._do_serial(line)
        if self.en["location"] and ("name = " in line or "latitude" in low
                                    or "longitude" in low):
            line = self._do_location(line)
        if self.en["network"] and ("ipv4:" in low or '"ip' in low or '_ip"' in low
                                   or "gateway" in low or "ip:" in low):
            line = self._do_network(line)
        if self.en["hotspot"]:
            if "ssid" in low or "pass" in low or "psk" in low or "pwd" in low:
                line = self._do_hotspot(line)
            elif self.ssid_map:
                line = self._stray_ssids(line)
        return line

    _TOKEN_SPLIT = re.compile('(%s)' % Placeholders.PATTERN.pattern)

    def _stray_ssids(self, line):
        """Replace known SSIDs that appear outside SSID fields (longest first,
        never inside existing placeholders, only values of 4+ characters)."""
        vals = [v for v in sorted(self.ssid_map, key=len, reverse=True) if len(v) >= 4]
        for v in vals:
            if v not in line:
                continue
            parts = self._TOKEN_SPLIT.split(line)
            for i in range(0, len(parts), 2):      # even indices = non-token text
                if v in parts[i]:
                    self.counts["hotspot"] += parts[i].count(v)
                    parts[i] = parts[i].replace(v, self.ssid_map[v])
            line = "".join(parts)
        return line


def _round1(s):
    try:
        return ("%.1f" % round(float(s), 1))
    except ValueError:
        return s


# ----------------------------------------------------------------------------
#  Leak check (#20): independent second pass over the written outputs
# ----------------------------------------------------------------------------
# Own patterns on purpose: a line format the redaction regexes miss must not be
# missed here for the same reason.  Every placeholder (Placeholders.PATTERN,
# incl. the 3rd-octet token in "192.168.<N1>.23") is blanked before matching.
# Findings are line numbers only; the values are never kept or shown.

_LK_BLANK = "\x01"
_LK_IP = re.compile(r'(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?!\.?\d)')
_LK_IP_CTX = re.compile(r'(?:ipv[46]:|\bip\s*[:=]\s*|ip"\s*:\s*"|gateway"\s*:\s*")$', re.I)
_LK_VER_CTX = re.compile(r'(?:ver(?:sion)?|fw|sdk)\w*["\'\s:=-]{0,4}$|(?<![A-Za-z])v$', re.I)
_LK_MAC = re.compile(r'(?<![0-9A-Fa-f:-])[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}'
                     r'(?:\1[0-9A-Fa-f]{2}){4}(?![0-9A-Fa-f:-])')
_LK_MAC_OK = frozenset(("00:00:00:00:00:00", "02:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"))
_LK_LATLON = re.compile(r'(?<![A-Za-z])(?:lat|lon|long|latitude|longitude)(?![A-Za-z])'
                        r'[^A-Za-z\n]{0,15}?\d{1,3}\.\d{2}', re.I)
# twilight times, GPS altitude and "...HourOffset [date] tz---lat---lon" (app
# log) give the site too; other "a---b" pairs are RA/Dec
_LK_LOC_MISC = re.compile(r'deg (?:rise|down|sunrise|sunset) time -?\d|\bm(?:Hours|Minutes|Seconds)=\d'
                          r'|-=----?\d|(?<![A-Za-z])(?:alt|mslAlt)=-?\d'
                          r'|TimeZoneHourOffset \[[^\]]*\]\s+[-\d.]+---\s*-?\d+\.\d\d')
_LK_INDI = re.compile(r'--> (Number|Text)#?\d*:\s*name = (\w+),.*?(?:value|text) = ([^\s,]*)')
_LK_INDI_LOC = re.compile(r'(?:^|_)(?:LAT|LONG|ALT|AZ|LST|ELEV|JD|SYNCTIME|UTC|OFFSET)$')
_LK_SSID = re.compile(r'(?<![A-Za-z])(?:[a-z_]*(?<!b)ssid|(?:last)?wifi ?name|curwifi|curboxwifi|wi-fi name'
                      r'|wi-fi bridge)"?\s*(?::|=+|\s)\s*"?(?!mIsBoxConnected)'
                      r'((?:(?!-(?:true|false)-|--)[^\s",}])*)', re.I)
_LK_PW = re.compile(r'(?<![A-Za-z])[a-z_]*(?:password|passwd|psk|pwd)(?![A-Za-z])'
                    r'"?\s*[:=]\s*"?([^\s",}]*)', re.I)
_LK_SERIAL = re.compile(r'(?<![A-Za-z])[a-z_]*serial[a-z_]*"\s*:\s*"?([^\s",}]*)', re.I)
_LK_CFG = re.compile(r'^Config:\s*\S*(?:serialnumber|ownername|artist|copyright)/?\s*$', re.I)
_LK_CFG_VAL = re.compile(r'^\s*(?:Current|Default|Choices)\s*:\s*(.*)$')
_LK_HEX = re.compile(r'(?<![\w.])(?=[0-9A-Fa-f]*\d)(?=[0-9A-Fa-f]*[A-Fa-f])'
                     r'[0-9A-Fa-f]{12,}(?![\w.])')
_LK_HASH_CTX = re.compile(r'(?:md5|sha\d*|hash|checksum|crc\d*)\w*["\'\s:=]*$', re.I)
# cheap pre-checks over a whole block of lines (literal first character =
# fast scan); the full patterns run only on the few lines that pass, so a
# 231 MB DebugLog costs seconds.  (pattern, on lower case?)
_LK_HINTS = tuple((re.compile(p), lc) for p, lc in (
    (r'\.\d{1,3}\.\d{1,3}\.\d', False),                      # IPv4
    (r':[0-9a-f]{2}:[0-9a-f]{2}:', True), (r'-[0-9a-f]{2}-[0-9a-f]{2}-', True),  # MAC
    (r'l(?:at|on)', True),                                      # location
    (r' time -?\d', False), (r'm(?:Hours|Minutes|Seconds)=', False), (r'alt=', True),
    (r'TimeZoneHourOffset', False), (r'-=---', False),
    (r'name = \w*(?:LAT|LONG|ALT|AZ|LST|ELEV|JD|SYNCTIME|UTC|OFFSET),[^\n]*?'
     r'(?:value|text) = (?!<REDACTED>)', False),
    (r's(?:sid|erial)', True), (r'wi-?fi', True), (r'p(?:ass|sk|wd)', True),
    (r'Config:', False),
    (r'dh', None), (r'hd', None),       # digit next to a hex letter, see _LK_HEX_MAP
))
_LK_BLOCK = 1 << 22                     # bytes of whole lines scanned at once
_LK_HEX_MAP = str.maketrans("0123456789abcdef", "dddddddddd" "hhhhhh")   # on lower case


def _lk_private(o):
    return (o[0] == 10 or (o[0] == 172 and 16 <= o[1] <= 31) or o[:2] == [192, 168]
            or o[:2] == [169, 254] or (o[0] == 100 and 64 <= o[1] <= 127))


def _lk_value_ok(v):
    """An empty value, a placeholder or a known non-value is not a leak."""
    return (not v or v.startswith(_LK_BLANK) or v.lower() in ("null", "nan", "<unknown")
            or v.startswith("--"))


def _leak_cats(line, state):
    """Categories with a possible leftover in one output line (independent of
    Redactor).  state: dict carried from line to line (gphoto config block)."""
    found = set()
    if "<" in line:
        line = Placeholders.PATTERN.sub(_LK_BLANK, line)
    low = line.lower()
    # network: private IPv4 anywhere, any IPv4 in an address field; MACs
    if "." in line:
        for m in _LK_IP.finditer(line):
            o = [int(x) for x in m.groups()]
            if max(o) > 255:
                continue
            pre = line[max(0, m.start() - 30):m.start()]
            if _LK_VER_CTX.search(pre):
                continue
            if _lk_private(o) or _LK_IP_CTX.search(pre):
                found.add("network")
                break
    if ":" in line or "-" in line:
        for m in _LK_MAC.finditer(line):
            if m.group(0).lower().replace("-", ":") not in _LK_MAC_OK:
                found.add("network")
                break
    # location: lat/lon with 2+ decimals (1 decimal is the redacted precision),
    # INDI site/time values that are not <REDACTED>
    if (("lat" in low or "lon" in low) and _LK_LATLON.search(line)) or _LK_LOC_MISC.search(line):
        found.add("location")
    if "--> " in line:
        m = _LK_INDI.search(line)
        if m and _LK_INDI_LOC.search(m.group(2)) and not _lk_value_ok(m.group(3)):
            name, val = m.group(2), m.group(3)
            if not (name.endswith(("LAT", "LONG")) and re.match(r'-?\d+(\.\d)?$', val)):
                found.add("location")
    # hotspot: SSID and password values that are not placeholders
    if "ssid" in low or "wifi" in low or "wi-fi" in low:
        if any(not _lk_value_ok(m.group(1)) for m in _LK_SSID.finditer(line)):
            found.add("hotspot")
    if "pass" in low or "psk" in low or "pwd" in low:
        if any(not _lk_value_ok(m.group(1)) for m in _LK_PW.finditer(line)):
            found.add("hotspot")
    # serial: JSON serial fields, sensitive gphoto config blocks, long hex strings
    if "serial" in low:
        if any(not _lk_value_ok(m.group(1)) for m in _LK_SERIAL.finditer(line)):
            found.add("serial")
    if line.startswith("Config:"):
        state["cfg"] = bool(_LK_CFG.match(line))
    elif state.get("cfg"):
        if line.startswith("["):              # timestamped line ends the block
            state["cfg"] = False
        else:
            m = _LK_CFG_VAL.match(line)
            if m and not _lk_value_ok(m.group(1).strip()):
                found.add("serial")
    for m in _LK_HEX.finditer(line):
        if not _LK_HASH_CTX.search(line, max(0, m.start() - 20), m.start()):
            found.add("serial")
            break
    return found


def check_leaks(path, enabled=CATEGORIES):
    """Scan a written output file.  Returns {category: [line numbers]} for the
    enabled categories with possible leftovers (empty dict = clean)."""
    hits = {}
    state = {}
    base = 0                    # line number before the current block
    cfg_open = False            # a sensitive gphoto config block runs on
    with open(path, encoding="utf-8", errors="replace") as f:
        while True:
            lines = f.readlines(_LK_BLOCK)
            if not lines:
                break
            block = "".join(lines)
            low = block.lower()
            texts = {False: block, True: low, None: low.translate(_LK_HEX_MAP)}
            starts = [0]
            for ln in lines:
                starts.append(starts[-1] + len(ln))
            cand = set()
            for rx, lc in _LK_HINTS:
                for m in rx.finditer(texts[lc]):
                    cand.add(bisect.bisect_right(starts, m.start()) - 1)
            # lines of a sensitive config block (up to the next timestamped or
            # Config: line, which resets the state) are checked as well
            heads = [k for k in sorted(cand) if lines[k].startswith("Config:")
                     and _LK_CFG.match(lines[k])]
            if cfg_open:                    # continued from the previous block
                heads.insert(0, -1)
            cfg_open = False
            for k in heads:
                i = k + 1
                while i < len(lines) and not lines[i].startswith(("[", "Config:")):
                    cand.add(i)
                    i += 1
                if i < len(lines):
                    cand.add(i)
                else:
                    cfg_open = True
            for k in sorted(cand):
                for c in _leak_cats(lines[k].rstrip("\n"), state):
                    if c in enabled:
                        hits.setdefault(c, []).append(base + k + 1)
            base += len(lines)
    return hits


# ----------------------------------------------------------------------------
#  GuideLog -> PHD2 converter  (validated against phdlogview)
# ----------------------------------------------------------------------------

_CONV_TS = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d): (.*)$')
_CONV_KV = re.compile(r'([A-Za-z]+)-(-?\d+(?:\.\d+)?)(?: \(([A-Z]?)\))?')
_STAR_ERR = {2: 'Star lost - low SNR / not found', 4: 'Star lost - too near edge',
             7: 'Star lost - mass changed', 8: 'Star lost - moved too far'}


def _kv(s):
    return {m.group(1): (m.group(2), m.group(3)) for m in _CONV_KV.finditer(s)}


def _wall(ts):
    import datetime
    return datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')


def convert_to_phd2(lines, stats=None):
    """lines: iterable of decoded GuideLog text lines -> list of PHD2 lines."""
    out, sess, state, ver = [], None, None, {"v": "unknown"}

    def flush():
        nonlocal sess
        if not sess:
            return
        rows, begin = sess['rows'], sess['begin']
        steps = [r for r in rows if r['kind'] == 'step']
        offs = sorted(float(r['dt']) - (r['wall'] - begin).total_seconds() for r in steps)
        off = offs[len(offs) // 2] if offs else 0.0
        nxt, upcoming = [None] * len(rows), None
        for i in range(len(rows) - 1, -1, -1):
            nxt[i] = upcoming
            if rows[i]['kind'] == 'step':
                upcoming = float(rows[i]['dt'])
        prev = 0.0
        for i, r in enumerate(rows):
            if r['kind'] == 'drop':
                t = (r['wall'] - begin).total_seconds() + off
                hi = nxt[i] - 0.001 if nxt[i] is not None else t
                t = min(max(t, prev + 0.001), max(hi, prev + 0.001))
                r['dt'] = '%.3f' % t
            if r['kind'] in ('step', 'drop'):
                prev = float(r['dt'])
                out.append(r['line'].replace('{DT}', r['dt']))
            else:
                out.append(r['line'])
        sess = None

    for raw in lines:
        ln = raw.rstrip('\r\n')
        m = _CONV_TS.match(ln)
        if m:
            ts, ev = m.groups()
            if ev == 'Guiding Begins':
                flush()
                state, sess = 'guide', {'begin': _wall(ts), 'rows': []}
                if stats is not None:
                    stats['sessions'] += 1
                out.append('Guiding Begins at ' + ts)
            elif ev == 'Calibration Begins':
                flush()
                state = 'cal'
                out.append('Calibration Begins at ' + ts)
            elif ev == 'Guiding Ends':
                if state == 'guide':
                    flush()
                    out.append('Guiding Ends at ' + ts)
                    out.append('')
                state = None
            elif sess is None and ev.startswith(('Guiding Step->', 'Guiding Frame Dropped->')):
                pass
            elif ev.startswith('Guiding Step->'):
                d = _kv(ev)
                (rd, rdir), (dd, ddir) = d['DurRa'], d['DurDec']
                row = ','.join([d['FrameNum'][0], '{DT}', '"Mount"',
                                d['CamOffsetX'][0], d['CamOffsetY'][0],
                                d['MountOffsetX'][0], d['MountOffsetY'][0],
                                d['DistRa'][0], d['DistDec'][0],
                                rd, rdir or '', dd, ddir or '', '', '',
                                d['StarMass'][0], d['StarSNR'][0], d['StarErr'][0]])
                sess['rows'].append({'kind': 'step', 'line': row,
                                     'dt': d['StepTime'][0], 'wall': _wall(ts)})
                if stats is not None:
                    stats['steps'] += 1
            elif ev.startswith('Guiding Frame Dropped->'):
                d = _kv(ev)
                err = int(d['StarErr'][0])
                desc = _STAR_ERR.get(err, 'Frame dropped (StellaVita StarErr %d)' % err)
                row = ','.join([d['FrameNum'][0], '{DT}', '"DROP"'] + [''] * 12 +
                               [d['StarMass'][0], d['StarSNR'][0], str(err), '"%s"' % desc])
                sess['rows'].append({'kind': 'drop', 'line': row, 'dt': None, 'wall': _wall(ts)})
                if stats is not None:
                    stats['drops'] += 1
            elif ev.startswith('Calibration Step->'):
                d = _kv(ev)
                dirn = re.search(r'Direction-(\w+)', ev).group(1)
                out.append(','.join([dirn, d['StepNum'][0], d['DX'][0], d['DY'][0],
                                     d['X'][0], d['Y'][0], d['Dist'][0]]))
            continue

        if ln.startswith('Log begin at '):
            stamp = ln[len('Log begin at '):].replace('_', ' ', 1)
            if len(stamp) == 17:
                stamp = stamp[:13] + ':' + stamp[13:15] + ':' + stamp[15:]
            out.append('PHD2 version StellaVita-{VER}, Log version 2.5. Log enabled at ' + stamp)
        elif ln.startswith('Version: '):
            ver['v'] = ln[9:].strip()
            out[:] = [o.replace('{VER}', ver['v']) for o in out]
        elif ln.startswith(('Platform:', 'Version protocol:')):
            pass
        elif ln == '':
            continue
        else:
            if sess is not None and (sess['rows'] or ln.startswith('INFO: ')):
                sess['rows'].append({'kind': 'text', 'line': ln})
                continue
            out.append(ln)
            if ln.startswith('Calibration complete'):
                out.append('')
                state = None
    flush()
    out[:] = [o.replace('{VER}', ver['v']) for o in out]
    return out


# ----------------------------------------------------------------------------
#  Processing one file
# ----------------------------------------------------------------------------

def is_our_output(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return any(stem.endswith(s) for s in OUT_SUFFIXES)


def _strip_suffix(stem):
    for s in OUT_SUFFIXES:
        if stem.endswith(s):
            return stem[:-len(s)]
    return stem


def _redaction_header(enabled, lang):
    names = {"hotspot": {"de": "Hotspot/WLAN", "en": "Hotspot/Wi-Fi"},
             "network": {"de": "Netzwerkadressen", "en": "Network addresses"},
             "location": {"de": "Standort", "en": "Location"},
             "serial": {"de": "Seriennummern", "en": "Serial numbers"}}
    on = [names[c][lang] for c in CATEGORIES if c in enabled]
    off = [names[c][lang] for c in CATEGORIES if c not in enabled]
    if lang == "de":
        txt = ("# Mit DecoVita v%s entschlüsselt. Inoffiziell, "
               "keine Verbindung zu ToupTek.\n" % TOOL_VERSION)
        txt += ("# Geschwärzt: " + (", ".join(on) if on else "nichts") + "\n")
        if off:
            txt += ("# ACHTUNG nicht geschwärzt (enthält persönliche Daten): "
                    + ", ".join(off) + "\n")
        txt += ("# Achtung: die verschlüsselten Originaldateien enthalten "
                "weiterhin alle Daten. Leerzeichen und '~' sind nicht unterscheidbar.\n")
    else:
        txt = ("# Decoded with DecoVita v%s. Unofficial, no connection "
               "to ToupTek.\n" % TOOL_VERSION)
        txt += ("# Redacted: " + (", ".join(on) if on else "nothing") + "\n")
        if off:
            txt += ("# WARNING not redacted (contains personal data): "
                    + ", ".join(off) + "\n")
        txt += ("# Note: the encrypted originals still contain all data. "
                "Space and '~' are indistinguishable.\n")
    return txt


def _iter_raw(path, plain):
    """Yield raw lines (bytes, no line ending).  For already-plain inputs the
    comment header written by this tool (leading '# ' lines) is skipped."""
    with open(path, "rb") as f:
        head = plain
        for rawl in f:
            rawl = rawl.rstrip(b"\r\n")
            if head:
                if rawl.startswith(b"# "):
                    continue
                head = False
            yield rawl


def process_file(path, out_dir=None, enabled=CATEGORIES, make_phd2=True,
                 full_date=True, report=False, force=False, lang="en",
                 progress=None, log=print, sniffed=None, placeholders=None,
                 leak_check=True):
    """Decode (and optionally redact/convert) one file.  Returns a result dict.
    sniffed: result of sniff(path) if the caller already has it.
    placeholders: Placeholders shared with other files of the same run.
    leak_check: scan the written outputs for leftovers of the redacted
    categories (#20); res["leaks"] = {output name: {category: [lines]}}."""
    res = {"path": path, "kind": None, "outputs": [], "skipped": None, "report": report,
           "redactions": {c: 0 for c in CATEGORIES}, "warnings": [],
           "lines": 0, "uncertain": 0, "leaks": None,
           "guide": {"sessions": 0, "steps": 0, "drops": 0}}

    kind, plain = sniffed or sniff(path)
    res["kind"] = kind
    if kind == "unknown":
        res["skipped"] = "unknown"
        log(_t(lang, "skip_unknown") % os.path.basename(path))
        return res

    size = os.path.getsize(path)
    stem = _strip_suffix(os.path.splitext(os.path.basename(path))[0])
    outdir = out_dir or os.path.dirname(os.path.abspath(path))
    if not report:
        os.makedirs(outdir, exist_ok=True)
    red = Redactor(enabled, app=(kind == "app"), ph=placeholders)

    # --- GuideLog: buffer (small), decode, redact, convert ---------------
    if kind == "guide":
        decoded = []
        mdl = None if plain else train_model(path)
        for rawl in _iter_raw(path, plain):
            if plain:
                d, anchored, margin = rawl.decode("latin1"), True, 0.0
            else:
                d, anchored, margin = recover(rawl, mdl)
            res["lines"] += 1
            if not anchored and margin < UNCERTAIN_MARGIN:
                res["uncertain"] += 1
            decoded.append(red.feed(d))
        _check_guide_version(decoded, res, lang)
        if report:
            res["redactions"] = dict(red.counts)
            _log_report(res, lang, log)
            return res
        dec_out = os.path.join(outdir, stem + "_decoded.txt")
        if _guard(dec_out, force, log, lang):
            with open(dec_out, "w", encoding="utf-8") as o:
                o.write(_redaction_header(enabled, lang))
                o.write("\n".join(decoded) + "\n")
            res["outputs"].append(dec_out)
        if make_phd2:
            gstats = {"sessions": 0, "steps": 0, "drops": 0}
            phd = convert_to_phd2(decoded, gstats)
            res["guide"] = gstats
            phd_out = os.path.join(outdir, stem + "_phd2.txt")
            if _guard(phd_out, force, log, lang):
                with open(phd_out, "w", encoding="utf-8") as o:
                    o.write(_redaction_header(enabled, lang))
                    o.write("\n".join(phd) + "\n")
                res["outputs"].append(phd_out)
        res["redactions"] = dict(red.counts)
        _leak_pass(res, enabled, leak_check)
        _log_done(res, lang, log)
        return res

    # --- glog: cleartext, redact only ------------------------------------
    if kind == "glog":
        lines = []
        for rawl in _iter_raw(path, True):
            res["lines"] += 1
            lines.append(red.feed(rawl.decode("latin1")))
        if report:
            res["redactions"] = dict(red.counts)
            _log_report(res, lang, log)
            return res
        # the suffix tells whether redaction ran (#17)
        suffix = "_redacted" if enabled else "_plain"
        out = os.path.join(outdir, stem + suffix + ".glog")
        if _guard(out, force, log, lang):
            with open(out, "w", encoding="utf-8") as o:
                o.write(_redaction_header(enabled, lang))
                o.write("\n".join(lines) + "\n")
            res["outputs"].append(out)
        res["redactions"] = dict(red.counts)
        _leak_pass(res, enabled, leak_check)
        _log_done(res, lang, log)
        return res

    # --- DebugLog / phone app log: stream (large) -------------------------
    app = kind == "app"
    dec = decode_app_line if app else decode_line
    dater = None
    if full_date and not app:          # app log lines already carry a full date
        dnm = date_from_name(path)
        if dnm:
            dater = DebugDater(dnm)
        else:
            res["warnings"].append("no_date")
            log(_t(lang, "warn_no_date"))
    dec_out = os.path.join(outdir, stem + "_decoded.txt")
    if not report and not _guard(dec_out, force, log, lang):
        return res
    o = None if report else open(dec_out, "w", encoding="utf-8")
    try:
        if o:
            o.write(_redaction_header(enabled, lang))
        done = 0
        mdl = None if plain else train_model(path, dec)
        for rawl in _iter_raw(path, plain):
            done += len(rawl) + 1
            if plain:
                # our own app output is proper UTF-8; device logs are ASCII
                d = rawl.decode("utf-8", "replace") if app else rawl.decode("latin1")
                anchored, margin = True, 0.0
            else:
                d, anchored, margin = recover(rawl, mdl, dec)
            res["lines"] += 1
            if not anchored and margin < UNCERTAIN_MARGIN:
                res["uncertain"] += 1
            d = red.feed(d)
            if dater:
                d = dater.feed(d)
            if o:
                o.write(d + "\n")
            if progress and (res["lines"] & 0x3FFF) == 0:
                progress(done, size, res["lines"])
    finally:
        if o:
            o.close()
    if progress:
        progress(size, size, res["lines"])
    res["redactions"] = dict(red.counts)
    if not report:
        res["outputs"].append(dec_out)
    if report:
        _log_report(res, lang, log)
    else:
        _leak_pass(res, enabled, leak_check)
        _log_done(res, lang, log)
    return res


def _leak_pass(res, enabled, on):
    """Leak check (#20) over the outputs written for this file.  Only the
    redacted categories are checked: the others are known to be in clear."""
    if not (on and enabled and res["outputs"]):
        return
    res["leaks"] = {}
    for out in res["outputs"]:
        hits = check_leaks(out, enabled)
        if hits:
            res["leaks"][os.path.basename(out)] = hits


def _check_guide_version(decoded, res, lang):
    ver = proto = None
    for ln in decoded[:10]:
        if ln.startswith("Version: "):
            ver = ln[9:].strip()
        elif ln.startswith("Version protocol: "):
            proto = ln[18:].strip()
    if (ver and ver not in KNOWN_APP_VERSIONS) or (proto and proto not in KNOWN_PROTOCOL):
        res["warnings"].append("version:%s/%s" % (ver, proto))


def _guard(path, force, log, lang):
    if os.path.exists(path) and not force:
        log(_t(lang, "skip_exists") % os.path.basename(path))
        return False
    return True


# ----------------------------------------------------------------------------
#  Several files: status line per file and a summary table (issues #14, #15)
# ----------------------------------------------------------------------------

KIND_NAMES = {"guide": "GuideLog", "debug": "DebugLog", "glog": "glog", "app": "AppLog",
              "unknown": "?"}


def process_all(files, lang="en", log=print, status=None, progress_for=None, **kw):
    """Process several files.  Before each file a status line like
    "[2/5] DebugLog 1/2: name" goes to status(text) (default: log).
    progress_for(path) may return a progress callback for that file.
    Remaining keyword arguments go to process_file.  Returns the result dicts.
    All files share one Placeholders, so a value gets the same placeholder in
    every output of the run (#21)."""
    import collections
    ph = Placeholders()
    status = status or log
    sniffed = [(f, sniff(f)) for f in files]
    total = collections.Counter(sn[0] for _, sn in sniffed)
    seen = collections.Counter()
    results = []
    for i, (f, sn) in enumerate(sniffed, 1):
        seen[sn[0]] += 1
        status("[%d/%d] %s %d/%d: %s" % (i, len(files), KIND_NAMES[sn[0]], seen[sn[0]],
                                         total[sn[0]], os.path.basename(f)))
        _POS_CACHE.clear()
        results.append(process_file(f, lang=lang, log=log, sniffed=sn,
                                    progress=progress_for(f) if progress_for else None,
                                    placeholders=ph, **kw))
    return results


def _result_state(r):
    if r["skipped"] == "unknown":
        return "unknown"
    if r["report"]:
        return "dry"
    return "ok" if r["outputs"] else "skipped"


def results_table(results, lang):
    """Summary table, one row per file.  Plain text, monospace aligned."""
    head = [_t(lang, "col_" + c) for c in ("no", "type", "file", "lines", "uncertain")]
    head += [_t(lang, "col_" + c) for c in CATEGORIES]
    head += [_t(lang, "col_leaks"), _t(lang, "col_state")]
    rows = []
    for i, r in enumerate(results, 1):
        state = _result_state(r)
        nums = [r["lines"], r["uncertain"]] + [r["redactions"][c] for c in CATEGORIES]
        # nothing was (fully) processed -> no numbers rather than misleading ones
        nums = ["-"] * len(nums) if state in ("skipped", "unknown") else [str(x) for x in nums]
        # flagged lines of the leak check; "-" = not checked (dry run, nothing redacted)
        lk = r.get("leaks")
        nums.append("-" if lk is None else str(sum(len(v) for h in lk.values() for v in h.values())))
        rows.append([str(i), KIND_NAMES[r["kind"] or "unknown"], os.path.basename(r["path"])]
                    + nums + [_t(lang, "state_" + state)])
    width = [max(len(x[c]) for x in [head] + rows) for c in range(len(head))]
    left = {1, 2, len(head) - 1}               # text columns; numbers right-aligned

    def fmt(cells):
        return "  ".join(c.ljust(w) if k in left else c.rjust(w)
                         for k, (c, w) in enumerate(zip(cells, width))).rstrip()
    return [fmt(head), fmt(["-" * w for w in width])] + [fmt(x) for x in rows]


# ----------------------------------------------------------------------------
#  Folder walking
# ----------------------------------------------------------------------------

def gather(paths, recursive):
    files = []
    for p in paths:
        if os.path.isdir(p):
            if recursive:
                for root, _, names in os.walk(p):
                    for n in names:
                        files.append(os.path.join(root, n))
            else:
                for n in sorted(os.listdir(p)):
                    fp = os.path.join(p, n)
                    if os.path.isfile(fp):
                        files.append(fp)
        elif os.path.isfile(p):
            files.append(p)
    # drop our own outputs and obvious non-logs
    out = []
    for f in files:
        if is_our_output(f):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in (".txt", ".log", ".glog", ""):
            out.append(f)
    return out


# ----------------------------------------------------------------------------
#  i18n (UI strings only; log content stays English for phdlogview)
# ----------------------------------------------------------------------------

_STR = {
    "skip_unknown": {"de": "Übersprungen (unbekannter Typ): %s",
                     "en": "Skipped (unknown type): %s"},
    "skip_exists": {"de": "Übersprungen (existiert, --force zum Überschreiben): %s",
                    "en": "Skipped (exists, use --force to overwrite): %s"},
    "warn_no_date": {"de": "  Warnung: kein Datum im Dateinamen, DebugLog ohne volles Datum.",
                     "en": "  Warning: no date in filename, DebugLog without full date."},
    "done": {"de": "Fertig: %s", "en": "Done: %s"},
    "no_files": {"de": "Keine Logdateien gefunden.", "en": "No log files found."},
    "no_tk": {"de": "Kein Fenster: tkinter fehlt in %s (Python %s): %s\n-> Textmenü.",
              "en": "No window: tkinter missing in %s (Python %s): %s\n-> text menu."},
    "no_display": {"de": "Kein Fenster: kein Bildschirm verfügbar (%s)\n-> Textmenü.",
                   "en": "No window: no display available (%s)\n-> text menu."},
    "warn_unredacted": {"de": "ACHTUNG: nicht geschwärzt (%s) – die Ausgaben enthalten persönliche Daten.",
                        "en": "WARNING: not redacted (%s) - the outputs contain personal data."},
    "report_head": {"de": "Probelauf (nichts geschrieben): %s",
                    "en": "Dry run (nothing written): %s"},
    "cat_hotspot": {"de": "Hotspot/WLAN", "en": "Hotspot/Wi-Fi"},
    "cat_network": {"de": "Netzwerk", "en": "Network"},
    "cat_location": {"de": "Standort", "en": "Location"},
    "cat_serial": {"de": "Seriennummern", "en": "Serials"},
    "stat_lines": {"de": "Zeilen", "en": "lines"},
    "stat_uncertain": {"de": "unsichere Zeilen", "en": "uncertain lines"},
    "stat_guide": {"de": "Sessions/Schritte/Ausfälle", "en": "sessions/steps/drops"},
    "col_no": {"de": "#", "en": "#"},
    "col_type": {"de": "Typ", "en": "Type"},
    "col_file": {"de": "Datei", "en": "File"},
    "col_lines": {"de": "Zeilen", "en": "Lines"},
    "col_uncertain": {"de": "unsicher", "en": "Uncertain"},
    "col_state": {"de": "Status", "en": "Status"},
    "col_hotspot": {"de": "WLAN", "en": "Wi-Fi"},      # short headers keep the table narrow
    "col_network": {"de": "Netz", "en": "Net"},
    "col_location": {"de": "Ort", "en": "Loc"},
    "col_serial": {"de": "SerNr", "en": "Serial"},
    "col_leaks": {"de": "Reste", "en": "Leaks"},
    "leak_head": {"de": "  ! Nachprüfung: vermutlich persönliche Daten übrig in %s – vor dem Weitergeben prüfen:",
                  "en": "  ! Leak check: possible personal data left in %s - check before sharing:"},
    "leak_lines": {"de": "Zeilen", "en": "lines"},
    "state_ok": {"de": "fertig", "en": "done"},
    "state_dry": {"de": "Probelauf", "en": "dry run"},
    "state_skipped": {"de": "existiert", "en": "exists"},
    "state_unknown": {"de": "unbekannt", "en": "unknown"},
    "gpl_notice": {"de": "DecoVita v%s - %s\n"
                          "Dieses Programm kommt OHNE JEDE GEWÄHRLEISTUNG. Es ist freie "
                          "Software (GPL-3.0-or-later); Weitergabe unter deren Bedingungen "
                          "ist erlaubt, siehe LICENSE.",
                   "en": "DecoVita v%s - %s\n"
                          "This program comes with ABSOLUTELY NO WARRANTY. It is free "
                          "software (GPL-3.0-or-later); you may redistribute it under its "
                          "conditions, see LICENSE."},
    "gui_source": {"de": "Quelle:", "en": "Source:"},
    "gui_outdir": {"de": "Zielordner (leer = Quellordner):",
                   "en": "Output folder (empty = source folder):"},
    "bad_outdir": {"de": "Zielordner ist eine Datei: %s", "en": "Output folder is a file: %s"},
}


def _t(lang, key):
    return _STR[key][lang]


def gpl_notice(lang):
    """Short start notice for interactive use, as recommended by the GPL."""
    return _t(lang, "gpl_notice") % (TOOL_VERSION, COPYRIGHT)


def _cat_summary(counts, lang):
    return ", ".join("%s %d" % (_t(lang, "cat_" + c), counts[c])
                     for c in CATEGORIES if counts[c])


def warn_unredacted(enabled, lang, log):
    off = [_t(lang, "cat_" + c) for c in CATEGORIES if c not in enabled]
    if off:
        log(_t(lang, "warn_unredacted") % ", ".join(off))


def _log_done(res, lang, log):
    log(_t(lang, "done") % os.path.basename(res["path"]))
    for out in res["outputs"]:
        log("  -> " + os.path.basename(out))
    cs = _cat_summary(res["redactions"], lang)
    if cs:
        log("  " + cs)
    log("  %d %s, %d %s" % (res["lines"], _t(lang, "stat_lines"),
                            res["uncertain"], _t(lang, "stat_uncertain")))
    g = res["guide"]
    if g["sessions"] or g["steps"]:
        log("  %s: %d/%d/%d" % (_t(lang, "stat_guide"),
                                g["sessions"], g["steps"], g["drops"]))
    for w in res["warnings"]:
        log("  ! " + w)
    for name, hits in sorted((res.get("leaks") or {}).items()):
        log(_t(lang, "leak_head") % name)
        for c in CATEGORIES:
            if c in hits:
                log("      %s %d (%s %s)" % (_t(lang, "cat_" + c), len(hits[c]),
                                            _t(lang, "leak_lines"), _line_list(hits[c])))


def _line_list(nums, limit=10):
    """'3, 17, 40' - at most limit numbers, then '... +N'.  Line numbers only,
    never values."""
    txt = ", ".join(str(n) for n in nums[:limit])
    return txt + (", ... +%d" % (len(nums) - limit) if len(nums) > limit else "")


def _log_report(res, lang, log):
    log(_t(lang, "report_head") % os.path.basename(res["path"]))
    cs = _cat_summary(res["redactions"], lang)
    log("  " + (cs if cs else "-"))
    log("  %d %s, %d %s" % (res["lines"], _t(lang, "stat_lines"),
                            res["uncertain"], _t(lang, "stat_uncertain")))


def default_lang():
    env = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    return "de" if env.startswith("de") else "en"


# ----------------------------------------------------------------------------
#  CLI
# ----------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="decovita.py",
        description="Decode, redact and convert ToupTek StellaVita logs. "
                    "Unofficial tool, no connection to ToupTek.",
        epilog=gpl_notice("en").replace("\n", " "))
    p.add_argument("paths", nargs="*", help="files or folders")
    p.add_argument("-o", "--out", help="output folder (default: next to input; created if missing)")
    p.add_argument("-r", "--recursive", action="store_true", help="recurse into subfolders")
    p.add_argument("--force", action="store_true", help="overwrite existing outputs")
    p.add_argument("--no-phd2", dest="phd2", action="store_false",
                   help="do not write the PHD2 file for guide logs")
    p.add_argument("--full-date", dest="full_date", action="store_true", default=True,
                   help="prefix DebugLog timestamps with the date (default)")
    p.add_argument("--no-full-date", dest="full_date", action="store_false",
                   help="keep the original DebugLog time format")
    p.add_argument("--lang", choices=("de", "en"), default=default_lang(),
                   help="UI language")
    p.add_argument("--report", action="store_true",
                   help="dry run: show what would be redacted, write nothing")
    p.add_argument("--no-redact", dest="redact", action="store_false",
                   help="turn off all redaction")
    p.add_argument("--no-leak-check", dest="leak_check", action="store_false",
                   help="skip the check of the outputs for leftover personal data")
    for c in CATEGORIES:
        p.add_argument("--no-redact-" + c, dest="red_" + c, action="store_false",
                       help="do not redact %s" % c)
        p.set_defaults(**{"red_" + c: True})
    return p


def enabled_from_args(a):
    if not a.redact:
        return ()
    return tuple(c for c in CATEGORIES if getattr(a, "red_" + c))


def run_cli(a):
    files = gather(a.paths, a.recursive)
    if not files:
        print(_t(a.lang, "no_files"))
        return 1
    enabled = enabled_from_args(a)
    warn_unredacted(enabled, a.lang, print)
    t0 = time.time()
    res = process_all(files, lang=a.lang, progress_for=lambda f: _big_progress(f, a.lang),
                      out_dir=a.out, enabled=enabled, make_phd2=a.phd2,
                      full_date=a.full_date, report=a.report, force=a.force,
                      leak_check=a.leak_check)
    print()
    print("\n".join(results_table(res, a.lang)))
    print(_summary(len(res), time.time() - t0, a.lang))
    return 0


def _big_progress(path, lang):
    """Progress line on stderr, only for files larger than 20 MB."""
    return make_progress(lang) if os.path.getsize(path) > 20 * 1024 * 1024 else None


def make_progress(lang):
    word = "Zeilen" if lang == "de" else "lines"

    def prog(done, total, lines):
        pct = 100.0 * done / total if total else 0
        sys.stderr.write("\r  %5.1f%%  %d %s   " % (pct, lines, word))
        sys.stderr.flush()
        if done >= total:
            sys.stderr.write("\n")
    return prog


def _summary(n, secs, lang):
    word = ("Datei" if n == 1 else "Dateien") if lang == "de" else ("file" if n == 1 else "files")
    return "(%d %s, %.1fs)" % (n, word, secs)


# ----------------------------------------------------------------------------
#  Text menu (fallback when there is no GUI)
# ----------------------------------------------------------------------------

def run_menu(lang):
    de = lang == "de"
    print(gpl_notice(lang))
    print("(unofficial / inoffiziell)")
    prompt = "Datei oder Ordner: " if de else "File or folder: "
    path = input(prompt).strip().strip('"')
    if not path or not os.path.exists(path):
        print("?")
        return 1
    rec = False
    if os.path.isdir(path):
        rec = input("Unterordner? [j/N] " if de else "Recurse? [y/N] ").strip().lower() in ("j", "y")
    enabled = list(CATEGORIES)
    q = ("Schwärzen (Enter = alles, sonst Nummern der auszulassenden Kategorien):"
         if de else "Redact (Enter=all, or drop by number):")
    print(q)
    for i, c in enumerate(CATEGORIES, 1):
        print("  %d %s" % (i, _t(lang, "cat_" + c)))
    drop = input("Auswahl (z. B. 3 oder 2,3): " if de else "Selection (e.g. 3 or 2,3): ").strip()
    if drop:
        rm = {int(x) for x in re.findall(r'\d+', drop)}
        enabled = [c for i, c in enumerate(CATEGORIES, 1) if i not in rm]
    phd2 = input("PHD2? [J/n] " if de else "PHD2? [Y/n] ").strip().lower() != ("n")
    files = gather([path], rec)
    if not files:
        print(_t(lang, "no_files"))
        return 1
    warn_unredacted(enabled, lang, print)
    t0 = time.time()
    res = process_all(files, lang=lang, progress_for=lambda f: _big_progress(f, lang),
                      enabled=tuple(enabled), make_phd2=phd2)
    print()
    print("\n".join(results_table(res, lang)))
    print(_summary(len(res), time.time() - t0, lang))
    return 0


# ----------------------------------------------------------------------------
#  tkinter GUI
# ----------------------------------------------------------------------------

def run_gui(lang):
    try:
        import tkinter as tk
    except Exception as e:     # signal: no GUI available -> text menu
        print(_t(lang, "no_tk") % (sys.executable, sys.version.split()[0], e))
        return None
    try:
        root = tk.Tk()
    except Exception as e:     # tkinter installed but no display (SSH, console)
        print(_t(lang, "no_display") % e)
        return None
    g = build_gui(root, lang)

    # test hooks (used by the automated test suite only)
    ar = os.environ.get("DV_GUI_AUTORUN")
    if ar:
        g.sel.set(ar)
        root.after(300, lambda: g.go(report=False))
    ac = os.environ.get("DV_GUI_AUTOCLOSE")
    if ac:
        root.after(int(ac), root.destroy)
    root.mainloop()
    return 0


def build_gui(root, lang):
    """Fill the main window.  Returns a namespace with the variables, widgets and
    the go() action (used by run_gui and by the test suite)."""
    import types
    import tkinter as tk
    from tkinter import filedialog, ttk
    de = lang == "de"
    root.title("DecoVita v%s" % TOOL_VERSION)
    pad = {"padx": 8, "pady": 4}

    # source and output folder share one grid, so both entries line up (issue #12)
    sel = tk.StringVar()
    outv = tk.StringVar()
    iof = tk.Frame(root); iof.pack(fill="x", **pad)
    iof.columnconfigure(1, weight=1)
    tk.Label(iof, text=_t(lang, "gui_source")).grid(row=0, column=0, sticky="w")
    ent_src = tk.Entry(iof, textvariable=sel)
    ent_src.grid(row=0, column=1, sticky="ew")
    srcb = tk.Frame(iof); srcb.grid(row=0, column=2, sticky="w")
    tk.Button(srcb, text=("Datei..." if de else "File..."),
              command=lambda: sel.set(filedialog.askopenfilename() or sel.get())
              ).pack(side="left")
    tk.Button(srcb, text=("Ordner..." if de else "Folder..."),
              command=lambda: sel.set(filedialog.askdirectory() or sel.get())
              ).pack(side="left")
    tk.Label(iof, text=_t(lang, "gui_outdir")).grid(row=1, column=0, sticky="w")
    ent_out = tk.Entry(iof, textvariable=outv)
    ent_out.grid(row=1, column=1, sticky="ew")
    tk.Button(iof, text=("Ordner..." if de else "Folder..."),
              command=lambda: outv.set(filedialog.askdirectory() or outv.get())
              ).grid(row=1, column=2, sticky="w")

    opt = tk.Frame(root); opt.pack(fill="x", **pad)
    v_rec = tk.BooleanVar(value=False)
    v_phd2 = tk.BooleanVar(value=True)
    v_date = tk.BooleanVar(value=True)
    v_force = tk.BooleanVar(value=False)
    tk.Checkbutton(opt, text=("Unterordner" if de else "Recurse"), variable=v_rec).pack(side="left")
    tk.Checkbutton(opt, text="PHD2", variable=v_phd2).pack(side="left")
    tk.Checkbutton(opt, text=("Volles Datum" if de else "Full date"), variable=v_date).pack(side="left")
    tk.Checkbutton(opt, text=("Überschreiben" if de else "Overwrite"), variable=v_force).pack(side="left")

    catf = tk.LabelFrame(root, text=("Schwärzen" if de else "Redact")); catf.pack(fill="x", **pad)
    cvars = {}
    for c in CATEGORIES:
        cvars[c] = tk.BooleanVar(value=True)
        tk.Checkbutton(catf, text=_t(lang, "cat_" + c), variable=cvars[c]).pack(side="left")

    # Buttons and progress bar are packed from the bottom *before* the log text,
    # so the text is what shrinks when the window is small (issue #1).
    btn = tk.Frame(root); btn.pack(side="bottom", fill="x", **pad)
    b_dry = tk.Button(btn, text=("Probelauf" if de else "Dry run"),
                      command=lambda: go(report=True))
    b_dry.pack(side="left")
    b_run = tk.Button(btn, text=("Start" if de else "Run"),
                      command=lambda: go(report=False))
    b_run.pack(side="right")
    bar = ttk.Progressbar(root, maximum=100); bar.pack(side="bottom", fill="x", **pad)
    stat = tk.StringVar()
    tk.Label(root, textvariable=stat, anchor="w").pack(side="bottom", fill="x", **pad)
    # log area: no line wrapping (the summary table is wider than the window),
    # scrollbars instead
    logf = tk.Frame(root); logf.pack(fill="both", expand=True, **pad)
    logf.rowconfigure(0, weight=1); logf.columnconfigure(0, weight=1)
    txt = tk.Text(logf, height=6, wrap="none")
    txt.grid(row=0, column=0, sticky="nsew")
    ysb = tk.Scrollbar(logf, orient="vertical", command=txt.yview)
    ysb.grid(row=0, column=1, sticky="ns")
    xsb = tk.Scrollbar(logf, orient="horizontal", command=txt.xview)
    xsb.grid(row=1, column=0, sticky="ew")
    txt.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
    txt.insert("end", gpl_notice(lang) + "\n")      # replaced by the log on the first run

    # Size from what the widgets actually need (fonts, display scaling), so nothing
    # is cut off; 640x560 is only the preferred minimum.
    root.update_idletasks()
    rw, rh = root.winfo_reqwidth(), root.winfo_reqheight()
    root.minsize(rw, rh)
    root.geometry("%dx%d" % (max(640, rw), max(560, rh)))

    def logw(msg):
        txt.insert("end", msg + "\n"); txt.see("end"); root.update_idletasks()

    cur = {"text": ""}

    def status(text):
        cur["text"] = text
        stat.set(text); logw(text)

    def prog(done, total, lines):
        bar["value"] = 100.0 * done / total if total else 0
        stat.set("%s  (%d %s)" % (cur["text"], lines, _t(lang, "stat_lines")))
        root.update_idletasks()

    def go(report=False):
        txt.delete("1.0", "end")
        p = sel.get().strip().strip('"')
        if not p or not os.path.exists(p):
            logw("?"); return
        out = outv.get().strip().strip('"') or None
        if out and os.path.exists(out) and not os.path.isdir(out):
            logw(_t(lang, "bad_outdir") % out); return
        enabled = tuple(c for c in CATEGORIES if cvars[c].get())
        t_start = time.time()
        files = gather([p], v_rec.get())
        if not files:
            logw(_t(lang, "no_files")); return
        warn_unredacted(enabled, lang, logw)
        bar["value"] = 0
        res = process_all(files, lang=lang, log=logw, status=status,
                          progress_for=lambda f: prog, out_dir=out, enabled=enabled,
                          make_phd2=v_phd2.get(), full_date=v_date.get(), report=report,
                          force=v_force.get())
        logw("")
        for line in results_table(res, lang):
            logw(line)
        bar["value"] = 100
        stat.set(_summary(len(res), time.time() - t_start, lang))

    def all_widgets():
        """Every non-container widget in the window (for layout checks)."""
        out, todo = [], list(root.winfo_children())
        while todo:
            w = todo.pop()
            kids = w.winfo_children()
            if kids:
                todo.extend(kids)
            else:
                out.append(w)
        return out

    return types.SimpleNamespace(root=root, sel=sel, out=outv, status=stat, ent_src=ent_src,
                                 ent_out=ent_out, rec=v_rec, phd2=v_phd2,
                                 date=v_date, force=v_force, cats=cvars, text=txt,
                                 bar=bar, btn_dry=b_dry, btn_run=b_run, go=go,
                                 all_widgets=all_widgets)


# ----------------------------------------------------------------------------
#  main
# ----------------------------------------------------------------------------

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):      # never crash on odd consoles
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    argv = sys.argv[1:] if argv is None else argv
    a = build_parser().parse_args(argv)
    if a.paths:
        return run_cli(a)
    # no paths -> interactive
    r = run_gui(a.lang)
    if r is None:
        return run_menu(a.lang)
    return r


if __name__ == "__main__":
    sys.exit(main())
