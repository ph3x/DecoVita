# DecoVita – log tool for the ToupTek StellaVita

Unofficial tool to decode, redact and convert the log files of the ToupTek
StellaVita astrophotography controller (Raspberry Pi CM4 inside). No connection
to ToupTek. Current version: see `TOOL_VERSION` in `decovita.py` (1.3.0 at the
time of writing).

## Repository layout

| File | Purpose |
|---|---|
| `decovita.py` | The tool. Single file, **standard library only** (tkinter optional). |
| `test_decovita.py` | Self-contained test suite with synthetic, fully fictitious fixtures. |
| `README.md` / `README.de.md` | User-facing description, English / German. Keep both in sync. |
| `LICENSE` | GPL v3 full text (canonical gnu.org version). |
| `.gitignore` | Keeps logs, outputs, `CLAUDE.local.md` and `.secrets/` out of the repo. |
| `CLAUDE.md` | This file: rules and technical notes for Claude (and human contributors). |

## Commands

```
python decovita.py                          # GUI (tkinter); falls back to a text menu
python decovita.py <file|folder> [-r] [-o OUT] [--lang de|en]
python decovita.py --help                   # all switches
python test_decovita.py [path/to/decovita.py]   # run ALL tests after every change
```

Supported Python: tested on 3.11, 3.12, 3.13, 3.14. The GUI needs tkinter, which on
Arch/CachyOS requires the system package `tk`. On Linux the GUI tests also need `Xvfb`;
on Windows and macOS they run directly on the desktop session. Without tkinter (or
Xvfb on Linux) those tests are reported as SKIP, not FAIL.

**CI** (`.github/workflows/tests.yml`, #28): every pull request and every push to `main`
runs the full suite incl. GUI tests on `ubuntu-latest` (Python 3.11 and 3.14, Xvfb) and
`windows-latest` (Python 3.14). There `DV_TEST_REQUIRE_GUI=1` turns a skipped GUI test
into a FAIL, and `DV_TEST_SHOTS=<dir>` stores GUI screenshots (Linux: ImageMagick
`import`, Windows: PowerShell), uploaded as run artifacts.

## Ground rules

- **All tests must pass** before a change counts as done. Add a test for every bug
  fixed and every feature added.
- **Test against real formats.** Synthetic fixtures once used an invented line format
  (`Number01:` instead of the real `Number#0:`), so location redaction silently failed
  on real logs while all tests were green. Fixtures must mirror real log lines exactly.
  If the maintainer provides real logs, verify against them too.
- **Never put personal data anywhere**: not in code, tests, fixtures, commit messages,
  or chat output. This covers coordinates, Wi-Fi names and passwords, IP addresses,
  serial numbers and the like. When inspecting real logs, print only counts or masked
  values (for example digits replaced with `d`; do not use `#`, because the real INDI
  format contains a literal `#`).
- **Everything on GitHub is (or will be) public:** issues, issue comments, PR titles
  and descriptions, review comments, labels, milestones, release notes, the repo
  description. The personal-data rule above applies there without exception: no
  excerpts from real logs (not even "redacted" ones without checking them line by
  line), no real counts that could identify a night or site, no file names of real logs (they contain date and time of a session).
  Use fictitious values (`192.168.77.x`, `FAKE_HOME`, ...) in examples. Before
  every GitHub write, re-read the text for this. If a user or contributor posts
  personal data, tell the maintainer; do not quote it anywhere.
- **Real logs never leave the maintainer's computer**: not into the repo, not into cloud
  sessions or uploaded project files. Work with real logs only in a session on the
  maintainer's computer, in temporary copies that are deleted afterwards, and print only
  counts or masked values.
- **Private notes** live in `CLAUDE.local.md` (git-ignored, maintainer's machine only).
  Credentials live in `.secrets/` (git-ignored): never print them, never copy them anywhere.
- **Workflow:** `origin` = https://github.com/ph3x/DecoVita. Work on a branch from `main`,
  one draft pull request per task. Never merge, force-push, push to `main` or change CI
  without the maintainer's go-ahead. If something you need is not reachable (a
  repository, a secret, a tool, real logs), say exactly what is missing and stop; do not
  mock, substitute or guess.
- **Never commit logs or tool outputs** (`GuideLog_*`, `DebugLog_*`, `Logs_App_*`, `*.glog`,
  `*_decoded.txt`, `*_phd2.txt`, `*_redacted*`, `*_plain*`).
- No third-party dependencies. numpy was benchmarked and is **4x slower** than the
  pure-Python lookup-table approach; do not reintroduce it.
- Code, comments and specs in English. UI strings exist in German and English
  (`_STR` dict, `_t(lang, key)`). Log content and PHD2 output always stay English,
  because phdlogview parses English keywords.
- Versioning: Semantic Versioning, bumped **per release, not per commit**. Patch
  (x.y.Z) = bug fixes only, minor (x.Y.0) = new backward-compatible features, major
  (X.0.0) = incompatible changes (removed switches, changed output formats). A release
  normally closes a GitHub milestone: bump `TOOL_VERSION`, commit, annotated tag
  `vX.Y.Z`, push, GitHub release with notes listing the closed issues. Claude does this
  only when the maintainer asks.

## Architecture of `decovita.py`

- **Cipher core:** `decode_line`, `encode_line` (inverse, used for test vectors),
  `decode_app_line`/`encode_app_line` (phone app variant),
  `t0_candidates`, `try_known`, `recover`, `train_model`, `_score`.
- **File type detection:** `sniff(path)` -> (`guide`|`debug`|`glog`|`app`|`unknown`,
  already_plain).
- **DebugLog dates:** `DebugDater` adds a full date from the filename and handles
  midnight rollover.
- **Redaction:** `Redactor` is streaming and stateful, with one method per category:
  `_do_hotspot`, `_do_network`, `_do_location`, `_do_serial`, plus `_stray_ssids`;
  placeholder numbering comes from a `Placeholders` shared per run (#21);
  `Redactor(enabled, app=True)` adds `_do_app` (app-log formats, MAC -> `<MAC_n>`).
- **Leak check (#20):** `check_leaks(path, enabled)` -> `{category: [line numbers]}`,
  an independent second pass over each written output (`_leak_cats` per line, own
  `_LK_*` patterns, never the redaction regexes). Placeholders are blanked via
  `Placeholders.PATTERN` first. Speed: the file is scanned in blocks
  (`_LK_BLOCK`) with literal-first pre-checks (`_LK_HINTS`); only matching lines get
  the full patterns (231 MB DebugLog: ~6 s). `process_file(..., leak_check=True)`
  stores `res["leaks"]` (`None` = not checked); `_log_done` prints category, count
  and line numbers, never values; table column `Leaks`/`Reste`.
- **PHD2 conversion:** `convert_to_phd2(lines, stats)`.
- **Orchestration:** `process_file(...)` (one file), `process_all(files, ...)` (several
  files: sniffs each once, emits a status line `[i/n] <Type> j/m: <name>` per file,
  returns the result dicts), `results_table(results, lang)` (plain-text summary table,
  one row per file; `-` instead of numbers for skipped/unknown files) and
  `gather(paths, recursive)` (folder walking, skips our own outputs). CLI, text menu
  and GUI all go through `process_all` + `results_table`.
- **User interfaces:** `build_parser` / `run_cli`, `run_menu` (text fallback),
  `run_gui` (tkinter). `main()` picks the UI.
- **Test hooks:** env vars `DV_GUI_AUTOCLOSE=<ms>` and `DV_GUI_AUTORUN=<path>`.
  These are used only by the test suite. The suite itself reads `DV_TEST_SHOTS` and
  `DV_TEST_REQUIRE_GUI` (see Commands).

## Log encryption (reverse-engineered from the files, no documentation)

Each line is encoded on its own. Only bytes 33..126 occur, and line endings are LF.

```
t_j   = (t0 + j) mod 95            # j = position in line, t0 random per line
a_j   = t_j - 1 if t_j > 32 else t_j
plain = 33 + (cipher - 33 - a_j) mod 94      # 126 -> space
```

- **Space/`~` collision:** 95 plaintext symbols map onto 94 cipher symbols, so `~`
  decodes as a space. This cannot be fixed.
- **Recovering t0:** the first character is known for timestamped lines (`[` in the
  DebugLog, `2` for date lines in the GuideLog). `t0_candidates(c0, first)` gives
  1–2 candidates; `TS` regex confirms.
- **Lines without a timestamp:** the tool brute-forces all 95 keys and keeps the
  best-scoring candidate. Scoring = bigram log-probabilities + common-character
  bonus + known-vocabulary bonus.
- **The scoring model:** a seed corpus plus bigrams from the first 20,000 anchored
  lines of the same file (`train_model`). The seed alone was not enough: it
  mis-decoded 66 camera-config lines in the real DebugLog.
- **Uncertain lines:** if the score gap to the runner-up is below
  `UNCERTAIN_MARGIN = 25`, the line counts as "uncertain" in the statistics.
  Digit-only lines (e.g. `1111111100000000…`) are inherently ambiguous, because
  another key yields a shifted digit string.
- **Speed:** precomputed per-position tables plus `bytes(map(operator.getitem, pos, raw))`.
  The 231 MB real DebugLog decodes in about 14 s; a full run with redaction and
  dates takes about 34 s.

## Log formats

### GuideLog (`GuideLog_YYYY-MM-DD_HHMMSS.txt`)

PHD2-like, but with StellaVita-specific lines:

- **Preamble:** `Log begin at YYYY-MM-DD_HHMMSS`, `Platform: RaspberryPi`,
  `Version: 2.0.37`, `Version protocol: 2`.
- **Event lines:** `YYYY-MM-DD HH:MM:SS: Guiding Begins`, `... Calibration Begins`,
  `... Guiding Ends`, `... Settle State Changed`, `... Guiding Dithered`,
  `... Set Lock Position`, `... Calibration Direct Complete`.
- **Steps:** `...: Guiding Step-> FrameNum-N, StepTime-S, "Mount", CamOffsetX-…,
  CamOffsetY-…, MountOffsetX-…, MountOffsetY-…, DistRa-…, DistDec-…, DurRa-D (W|E|),
  DurDec-D (N|S|)   StarMass-…, StarSNR-…, StarErr-0`.
  Negative numbers appear as `X--1.23`.
- **Drops:** `...: Guiding Frame Dropped-> FrameNum-N, Time-0.000, "DROP"
  StarMass-…, StarSNR-…, StarErr-E, "eGuideState::GUIDING"`. The time is always
  0.000; the converter estimates it from the wall clock.
- **Calibration:** `...: Calibration Step-> Direction-West|East|Backlash|North|South|NudgeSouth,
  StepNum-…, DX-…, DY-…, X-…, Y-…, Dist-…`.
- **Lines already in PHD2 syntax** (copied 1:1): the header block (`Pixel scale = …`,
  `Mount = …, xAngle = …`, `X guide algorithm = …`, etc.), the column headings
  `Frame,Time,mount,…` and `Direction,Step,dx,dy,x,y,Dist`, `INFO: …` lines,
  `West/North calibration complete …` and `Calibration complete, mount = …`.
- **Quirks:**
  - The header shows `xAngle = 0.0` even after the calibration measured about −180°.
    phdlogview ignores this field.
  - Guide-algorithm parameters (min move etc.) are not logged, so phdlogview shows
    no min-move lines.
- **StarErr codes** (derived from matching DebugLog messages, not documented):
  - 2 = star not found / low SNR
  - 4 = too near edge
  - 7 = mass changed
  - 8 = moved too far (CheckDistance)

### DebugLog (`DebugLog_YYYY-MM-DD_HHMMSS.txt`)

- **Timestamped lines:** `[HH:MM:SS.mmm] …` with time only, no date. Local time.
  The Pi has no RTC, so time can jump.
- **CoreServer lines:** `[CoreServer][RES|REQ|EVT][ipv4:A.B.C.D:port] {…}`. The JSON is
  partly malformed (e.g. `{"event_type":"X":{…}}`), so use regex, never `json.loads`.
- **INDI dumps:** `-> Number (PROP)(RO)` followed by element lines
  `--> Number#<n>: name = X, label = …, value = V, min = …, max = …, step = …`.
  Note the literal `#`. Same scheme for `--> Text#<n>: … text = V` and
  `--> Switch#<n>: … state = V`.
- **gphoto config dumps** (no timestamp, decoded by brute force): `Config: /main/…`,
  then field lines `  Label      : `, `  Readonly   : `, `  Type       : `,
  `  Current    : `, `  Choices    : `.
- **Source paths:** ToupTek's own build paths appear in error lines. These are not
  user data.

### Phone app log (`Logs_App_YYYYMMDDhhmmss.txt`, kind `app`, #18)

Analysed 2026-10-18 and 2026-10-25 on 8 real app logs (counts only). Same per-line
cipher, but:
- **Non-ASCII bytes pass through and do not advance the position counter** `j`
  (`decode_app_line`; verified: only this model gives a number before every `℃`, and
  every non-ASCII line anchors on its timestamp).
- **Double-encoded UTF-8:** the raw bytes are valid UTF-8 of characters U+0080..U+00FF;
  after decoding, `bytes.decode("utf-8").encode("latin1").decode("utf-8")`.
- Lines: `YYYY-MM-DD hh:mm:ss | <Tag> ...` (anchored by `TS`). Lines without timestamp
  are tab-indented stack traces and version blocks (`TP version:…`); the leading tab
  is a constant shift, so brute force handles them. No date handling needed.
- One line can contain NUL bytes (`Bridge IP: \0\0…`); they pass through.
- Personal data and formats (all covered by `Redactor._do_app`, active only for
  `app`): JSON SSIDs/passwords (existing rules); free-text SSIDs `ssid=`,
  `previousSsid=`, `lastWifiName:/curWifi:/curBoxWifi:` (separator `--cur`),
  `Wi-Fi name: `, `Wi-Fi bridge=====<v>-true-`; Android `TransportInfo` with
  `<unknown ssid>` and `02:00:00:00:00:00` placeholders (kept); `bssid=` MACs; about
  30 free-text IPv4 formats (so: every private IPv4, public ones stay, e.g. the OTA
  server); lat/lon in JSON, `Update longitude and latitude: a,b`,
  `Data1 longitude-time1 n-----lon latitude lat-=---<dawn h>----<dusk h>`,
  `…TimeZoneHourOffset [y, m, d, h, m, s]   tz---lat---lon`; GPS `alt=`/`mslAlt=` in
  `bestLocation Location[…]` (Android already masks lat/lon there). The generic
  IPv4/MAC rules now run for every log type (#25).
- **Twilight block** (verified 2026-10-25): `Data1 <deg> deg rise|down|sunrise|sunset
  time D h m s.ssss` for -18/-12/-6/-0.833 deg, the two decimal hours in the
  `longitude-time1` line (-18 deg dawn/dusk) and `TwilightData{…mHours/mMinutes/
  mSeconds…}`. Times are in UT+offset with sub-second precision; with the date they
  give the longitude (rough test: ~17 km) and, away from the equinox, the latitude,
  so they are `<REDACTED>` (location). `Data1 UT time … offset …` is the current
  time and stays.
- **Not personal (checked):** `generateKey ToupTek#Server#…` (cache keys),
  `…VersionKey`/`latestToupSdkKey` (versions), `/data/user/0/…` (app path),
  `deviceId=` (Android input device), `sessionId=` (stream number). No account,
  token, e-mail, IMEI or Android-ID fields exist. Phone model / Android version stay
  (maintainer decision). Wi-Fi names `null` / empty are placeholders, not SSIDs.

### libtoupcam `.glog`

Plain-text SDK start log: SDK version, `as_core`, CM4 hardware, kernel, settings,
USB enumeration. It contains no personal data. The tool only adds a header and
applies redaction.

## Redaction (decisions)

Redaction is on by default. There are four categories (`CATEGORIES`), each with
its own switch: `--no-redact-hotspot|network|location|serial`, plus `--no-redact`
for all of them.

### Placeholders (#21)

- `Placeholders` holds the value -> placeholder maps (`<SSID_n>`, subnet `N<n>`,
  `<MAC_n>`). `process_all` creates one per run and passes it to every
  `process_file`, so the same value gets the same placeholder in all outputs of the
  run; numbering = order of first appearance (so it depends on the file order).
  A single `process_file` call without one gets its own.
- A known SSID learned in an earlier file is also replaced as a stray occurrence in
  later files of the run.
- The mapping stays in memory: never written, logged or printed (`repr` shows counts
  only).
- `Placeholders.PATTERN` matches every placeholder the redactor emits; new
  placeholder kinds (#25) and the leak check (#20) must use it.
- IPs keep the 3rd-octet scheme (`192.168.<N1>.23`), no whole-address `<IP_n>`
  (maintainer decision 2026-10-26, keeps the output format compatible).

### hotspot

- Values of keys matching `*ssid` become `<SSID_n>`, so the hotspot and the home
  network stay distinguishable.
- Keys seen in real data: `ssid`, `wifi_ssid`, `connecting_bridge_wifi_ssid`,
  `connected_bridge_wifi_ssid`.
- Stray occurrences elsewhere are replaced too: longest value first (one SSID can be
  a prefix of another), only values with 4+ characters, never inside placeholders.
- Values of keys matching `*password|passwd|psk|pwd` become `<REDACTED>`.
  The home-network password is not in the logs, only the hotspot password.

### network

- The **3rd octet** is replaced by a per-subnet token: `192.168.<N1>.105`. The 4th
  octet stays, so devices remain distinguishable while the network does not.
- Context rules mask any IPv4 (public too) in the `ipv4:` prefix, in JSON keys
  `*ip` / `*gateway`, and in `ip:` inside info strings.
- Generic rules for every log type (`Redactor._do_any_net`, #18 app, #25 all): every
  private IPv4 (10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10) anywhere in a line,
  and MACs -> `<MAC_n>` (Android placeholders `02:00:00:00:00:00` kept). A cheap
  substring pre-check in `feed` keeps the cost low (231 MB DebugLog: redaction
  +~3 s, full run ~25 s; real logs byte-identical to before, 2026-10-26).
- Subnet masks and public IPs (outside the context rules) stay unchanged.
- Version strings that look like IPs (`"poaefw_sdk_version":"x.x.x.x"`, `EFW-x.x.x.x`,
  `v10.x.x.x`) must never be touched: `_RE_VER_CTX` skips an IP right after
  `version|ver|fw|sdk`. This is covered by tests.

### location

- **GuideLog: untouched.** Decision: its header precision (~10 km) is acceptable.
- **DebugLog:** `LAT`, `LONG` and JSON `latitude` / `longitude` are rounded to 1
  decimal.
- **DebugLog values replaced by `<REDACTED>`:**
  - `ALT`, `AZ`, `LST`, `ELEV`
  - `SYNCPOLARALIGN_ALT/AZ`
  - `*_JD` and `*_SYNCTIME` of the sync/align points
  - `HORIZONLIMITS_POINT_*`
  - `TIME_UTC` (`UTC`, `OFFSET`)
- **Why so strict:** from the mount's ALT/AZ/LST alone the site can be reconstructed
  to < 1 m in latitude and ~250 m in longitude. Rounding does not help: even at 1°
  the error is only ~2 km, because thousands of samples average out.
- `RA` / `DEC` stay. On their own they reveal no location.

### serial

- In gphoto config blocks whose path ends in `serialnumber`, `eosserialnumber`,
  `ownername`, `artist` or `copyright`, the `Current`/`Default`/`Choices` value
  becomes `<REDACTED>`.
- Inside such a block, any line that is not a recognisable field line is replaced
  entirely (protection against mis-decoded value lines).
- The block ends at the next timestamped line or the next `Config:` line.
- JSON keys matching `*serial*` are redacted as well.
- INDI `CONNECTION_SERIAL` is a connection-mode switch, not a serial number, so it
  stays.

### Output header

Every output file starts with `# ` comment lines:

- tool version and an "unofficial" note
- which categories were redacted
- a warning line if a category was **not** redacted
- a note that the encrypted originals still contain everything
- a note on the space/`~` collision

phdlogview ignores these lines. When the tool reads its own output again, it skips them.

## Outputs and behaviour

- **Output names:** `<stem>_decoded.txt`, `<stem>_phd2.txt` (GuideLog only, switch
  `--no-phd2`), `<stem>_redacted.glog`
  (`<stem>_plain.glog` when no category is redacted, #17).
  Every output suffix must be in `OUT_SUFFIXES`, `.gitignore` and both README tables,
  otherwise folder mode reads the output back in as input.
- **Location:** next to the input, or in `-o OUT` (flat, created if missing).
- **Safety:**
  - The originals are never modified.
  - Nothing is overwritten without `--force`.
  - In folder mode, the tool's own outputs and files that are not log files are skipped.
- **DebugLog full date:** on by default (`--no-full-date`). The date comes from the
  filename. A new day is counted only on a backward jump of more than 12 h. Without a
  date in the filename the tool warns and leaves the date off.
- **Leak check (#20):** on by default, `--no-leak-check` (CLI only) turns it off. Only
  enabled categories are checked; dry run and `--no-redact` check nothing. Verified
  2026-10-26 on the real logs: 0 warnings on all redacted outputs, and on unredacted
  outputs it flags exactly the lines the redactor changes (counts only).
  Not flagged on purpose: public IPs outside address fields (OTA server), IPs after
  `version|ver|fw|sdk|v`, 1-decimal LAT/LONG, RA/Dec pairs (`a---b`, `a----b`),
  `delta_alt/az`, `nan`, Android placeholder MACs, hashes after `md5|sha|hash|crc`,
  GuideLog header `Alt = … deg`.
- **`--report`:** dry run. It writes nothing (not even the output folder) and the
  counts match a real run.
- **Version check:** a GuideLog `Version:` / `Version protocol:` outside
  `KNOWN_APP_VERSIONS` / `KNOWN_PROTOCOL` produces a warning.
- **UI selection:**
  - The CLI always works.
  - Without arguments the GUI starts. If tkinter is missing or there is no display, the
    tool prints the reason (interpreter path plus error) and falls back to the text menu.
  - The GUI has an optional output folder (empty = next to the input), like `-o`.
  - GUI layout: `build_gui(root, lang)` builds the window and returns a namespace
    (vars, widgets, `go()`, `all_widgets()`); `run_gui` adds the env test hooks and
    runs the mainloop. Buttons and progress bar are packed from the bottom before the
    log text, and the window size/minsize come from the requested size, so nothing is
    cut off at any display scaling (tested at 1.0x/1.25x/1.5x).
- **Statistics:** lines, uncertain lines, redactions per category,
  sessions/steps/drops. A progress bar appears for files larger than 20 MB (CLI/menu,
  on stderr). Per file a status line, at the end a summary table (stdout stays free of
  control characters). The GUI shows the status line above the progress bar (with the
  running line count), and the log area does not wrap lines (scrollbars instead) so
  the table stays readable.

## GuideLog -> PHD2 conversion (validated with phdlogview)

- **Preamble:** `PHD2 version StellaVita-<ver>, Log version 2.5. Log enabled at
  YYYY-MM-DD HH:MM:SS`.
- **Event lines:** `Guiding Begins at …`, `Calibration Begins at …`,
  `Guiding Ends at …` followed by an empty line. A stray `Guiding Ends` without an
  open session is dropped.
- **Step rows:** `frame,dt,"Mount",dx,dy,RAraw,DECraw,RAguide,DECguide,RAdur,E|W,DECdur,N|S,,,mass,snr,err`
  (`dt` = StepTime).
- **Drop rows:** `frame,dt,"DROP"` + 12 empty fields + `,mass,snr,err,"<description>"`.
  The time is estimated from the wall clock, median-offset corrected, and kept
  strictly increasing.
- **Calibration rows:** `Direction,step,dx,dy,x,y,dist`. `NudgeSouth` rows end up
  as header text in phdlogview; that is the intended behaviour.
- **Blank lines** inside sections are removed, because phdlogview would end the
  section there.
- **phdlogview facts:**
  - GPLv3, C++/wxWidgets/GSL; the parser is `logparser.cpp`.
  - The test suite contains a Python port of its parser (`phdlogview_parse`).
  - The x-axis is the frame index and the time labels are interpolated, so they are
    misleading when frame cadence changes; hover shows the true time.
- **Building phdlogview for visual checks:** wxWidgets 3.2 (GTK3), GSL, CMake;
  `cmake -DHAVE_WXFB=FALSE` uses the pre-generated GUI files.

## Test suite (`test_decovita.py`)

- **Coverage:** cipher, type detection, exact decoding, redaction per
  category, redaction in doubt, category switches, output header, GuideLog location
  kept, dates/rollover, PHD2 conversion, files, dry run, version check, CLI,
  progress/i18n, text menu (incl. tkinter-without-display), GUI under Xvfb or on the
  native desktop (Windows/macOS).
- **Portability:** every subprocess goes through `run()`: UTF-8 pipes on every platform
  (Windows with Python <= 3.14 defaults to cp1252 and breaks on `℃`) and a timeout,
  so a window that waits for input fails the check instead of hanging the suite. The
  test "tkinter without display" is skipped on Windows/macOS: removing `DISPLAY` hides
  nothing there.
- **Last run:** 376/376 passed on Python 3.14 with Xvfb (2026-10-26); CI results: see the Actions tab.
- **Fixtures:** built in a temp dir from fake plaintext and encrypted with `encode_line`.
  All values are invented (e.g. `FAKE_HOME`/`FAKE_HOME_EXT`, `FAKESERIAL…`,
  `192.168.77.x`).
## Open items / ToDo

**Tasks live in GitHub issues** (single source of truth since 2026-10-10):
https://github.com/ph3x/DecoVita/issues. Do not keep a task list here.
Labels: `bug`, `enhancement`, `documentation`, `chore`, `question`; one milestone
per release. Reference issues in commits and pull requests (`Fixes #N`).

Decisions and background (not tasks) stay here:

- **Dropped:**
  - A DebugLog filter. It belongs in a viewer, not here.
  - numpy.
  - Asking phdlogview upstream to import decoded StellaVita GuideLogs directly
    (dropped 2026-10-10): our PHD2 conversion already works, decoding/redaction would
    still need this tool, and it would only shift work onto other people.
- **Naming (decided 2026-10-10, #16):** the tool is called **DecoVita** (`decovita.py`),
  never "StellaVita Log Tool" or similar, to avoid trademark trouble. The device name
  is only used descriptively ("decodes ToupTek StellaVita logs", "for the StellaVita",
  `PHD2 version StellaVita-<ver>` in PHD2 output). A test guards against the old name.
- **License (decided 2026-10-09):** `GPL-3.0-or-later`. Every source file starts
  with `SPDX-FileCopyrightText` and `SPDX-License-Identifier` lines. Reason: the test
  suite's `phdlogview_parse` is a port of GPLv3 code (phdlogview `logparser.cpp`),
  so GPL keeps everything consistent without a rewrite.
- **Known limits:** the space/`~` collision, ambiguous digit-only lines, and
  phdlogview's interpolated time axis.
