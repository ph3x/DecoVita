# DecoVita

**English** | [Deutsch](README.de.md)

Unofficial tool to decode, redact and convert the log files of the ToupTek
StellaVita. Not affiliated with ToupTek.

## Features

- Decode `GuideLog_*.txt` and `DebugLog_*.txt` (device) and `Logs_App_*.txt`
  (phone app)
- Redact personal data (on by default, each category can be switched off):
  hotspot/Wi-Fi, network addresses (IP and MAC), location, serial numbers
- Check every redacted output for leftover personal data (leak check)
- Warn when a log no longer decodes reliably (e.g. after a firmware or app update
  changed the format), and check itself on built-in sample lines before every run
- Additionally convert GuideLogs to PHD2 format (for phdlogview)
- Redact `libtoupcam*.glog` files (plain text)

## Requirements

- Python 3.11 or newer (tested with 3.11 to 3.14), standard library only
- For the window: tkinter (Python's interface to Tcl/Tk). Without tkinter or
  without a display, `python decovita.py` prints the reason and starts a text
  menu instead. The command line (`python decovita.py <file|folder>`) never
  needs tkinter.

Check whether your Python has tkinter:

```
python -c "import tkinter; print(tkinter.TkVersion)"   # prints e.g. 8.6
python -m tkinter                                      # opens a small test window
```

If the first command fails with `ModuleNotFoundError`, tkinter is missing:

- Windows (installer from python.org): run the installer again, choose
  "Modify" and tick "tcl/tk and IDLE" (ticked by default).
- Linux: tkinter is usually a separate package, e.g. `tk` on Arch/CachyOS,
  `python3-tk` on Debian/Ubuntu.
- macOS: not tested.

## Usage

```
python decovita.py                     # window (tkinter), otherwise text menu
python decovita.py <file|folder> [-r] [-o OUTPUT_FOLDER] [--lang de|en]
python decovita.py --help              # all switches
```

Useful switches:

- `--report` – dry run: shows what would be redacted, writes nothing
- `--no-redact-hotspot`, `--no-redact-network`, `--no-redact-location`,
  `--no-redact-serial` – keep one category; `--no-redact` keeps everything
- `--no-phd2` – no PHD2 file for GuideLogs
- `--no-leak-check` – skip the leak check (saves about a fifth of the run time
  on a large DebugLog)
- `--no-full-date` – keep the original DebugLog time format (without date)
- `--force` – overwrite existing outputs
- `--selftest` – only run the selftest (see below) and show the result

## Outputs

| Input | Output |
|---|---|
| GuideLog | `<name>_decoded.txt` and `<name>_phd2.txt` |
| DebugLog | `<name>_decoded.txt` (timestamps with full date) |
| App log (`Logs_App_*.txt`) | `<name>_decoded.txt` |
| `.glog` | `<name>_redacted.glog` (`<name>_plain.glog` with `--no-redact`) |

The outputs are written next to the input, or into an output folder (`-o` on the
command line, "Output folder" in the window; created if missing).
The originals are never modified, and existing outputs are only overwritten with
`--force`. Every output starts with a few `# ` lines stating the tool version and
what was redacted.

## What gets redacted

- **Hotspot/Wi-Fi:** network names become `<SSID_1>`, `<SSID_2>`, …;
  passwords become `<REDACTED>`.
- **Network:** the third part of IP addresses is replaced (`192.168.<N1>.23`).
  Devices stay distinguishable, the network does not. This applies to every
  private IP address wherever it appears in a log (public addresses such as
  ToupTek's update server, subnet masks and version numbers stay), and MAC/BSSID
  addresses become `<MAC_1>`, `<MAC_2>`, ….
- **Same value, same placeholder:** within one run, a value gets the same placeholder
  in every output file (e.g. `<SSID_1>` is the same network in the DebugLog and in
  the app log). Numbering follows the order of first appearance. The mapping is
  kept in memory only and never saved or shown.
- **Location (DebugLog):** latitude and longitude are rounded to 0.1°. Mount
  altitude/azimuth, sidereal time, elevation and UTC time are removed, because the
  site could be reconstructed from them very precisely.
- **Location (app log):** latitude and longitude are rounded to 0.1°. The GPS
  altitude and the computed twilight, sunrise and sunset times are removed, because
  together with the date they give away the site.
- **Location (GuideLog):** unchanged. The header only contains the location at
  roughly 10 km precision.
- **Serial numbers:** camera serial number, owner, artist and copyright fields.
- **Not redacted:** phone model and Android version in the app log.

Redaction is an aid, not a guarantee. Check the outputs yourself before you share
them.

### Leak check

After writing, the tool reads every redacted output once more and looks for
leftovers with its own, independent patterns: private IP addresses (and any IP in
an address field), MAC addresses, coordinates with more than one decimal, site and
time values of the mount, twilight times, Wi-Fi names and passwords, serial
numbers and long hex strings. Placeholders such as `<SSID_1>`, `<MAC_1>`,
`<REDACTED>` or `192.168.<N1>.23` count as clean. This catches values that slip
through because a log line has a format the redaction does not know.

For each affected output it prints a warning with the category, the number of lines
and their line numbers, never the values:

```
  ! Leak check: possible personal data left in DebugLog_2026-01-15_201500_decoded.txt - check before sharing:
      Hotspot/Wi-Fi 2 (lines 5, 6)
```

The summary table shows the number of flagged lines per file in the column
`Leaks` (`-` = not checked). Only redacted categories are checked; a dry run
(`--report`) and `--no-redact` check nothing. The check is on by default;
`--no-leak-check` turns it off.

## How the logs are encoded

Each line is encoded on its own with a character shift over the printable
characters. The start value is random per line, and the shift grows with the
position in the text, almost always by one. The known first character (`[` in the
DebugLog, `2` for date lines in the GuideLog) gives one or two possible start
values; the timestamp confirms the right one. For lines without a timestamp the
script tries all 95 start values and keeps the most plausible text. Space and `~`
are encoded the same way and cannot be told apart afterwards.

The phone app logs use the same scheme with two differences: non-ASCII characters
(for example Chinese texts or `℃`) are left as they are and do not count as a
position, and the text is UTF-8-encoded twice. The tool undoes both.

The scheme was derived from the log files alone. There is no documentation of it
from ToupTek.

### Decode confidence and selftest

A firmware or app update could change the encoding. The tool would then produce
garbage, and the redaction cannot find personal data in garbage. Two checks guard
against this:

- **Decode confidence:** the share of non-empty lines of a file that decoded
  with certainty (a timestamp confirmed the start value, or one start value was
  clearly the most plausible). It is shown per file (`decode confidence 100.0%`)
  and in the summary table, column `Conf` (`-` = not decoded, e.g. `.glog` or
  an already decoded file). All real logs so far reach 100.0%. Below 95% the
  value is marked with `!` and a warning says that the format has probably
  changed and the redaction may be incomplete. Files with fewer than 20 lines
  get no warning (too few to judge).
- **Unknown format:** a file named like a StellaVita log (`GuideLog_*.txt`,
  `DebugLog_*.txt`, `Logs_App_*.txt`, `*.glog`) whose content cannot be
  decoded at all is skipped with a warning; the table shows `format changed?`.
- **Selftest:** before every run the tool decodes, redacts and leak-checks a few
  built-in, invented sample lines in the real log formats. If that fails, it
  processes nothing and names the failed checks. `--selftest` runs it on its own.

## Known limits

- Space and `~` cannot be distinguished (see above).
- Lines consisting only of digits can be ambiguous. The statistics count such lines
  as "uncertain", which lowers the decode confidence slightly.
- phdlogview interpolates its time axis from the frame numbers. When the frame rate
  changes, the time labels are misleading; hovering shows the true time.

## Privacy

The encrypted original files always contain all data. Logs and outputs do not
belong in the repository (see `.gitignore`).

## Tests

```
python test_decovita.py
```

The window tests need tkinter; on Linux also `Xvfb` (otherwise they are reported as
SKIP). On Windows and macOS they open briefly on the desktop. Every pull request is
tested automatically on Linux and Windows (GitHub Actions).

## Contributing

Bug reports, ideas and pull requests are welcome, via
[GitHub Issues](https://github.com/ph3x/DecoVita/issues) and pull requests.

- **Bug reports:** please include the DecoVita version (window title or
  `--help`), operating system, Python version, the command or steps you used, and
  the message or the summary table.
- **Never attach original logs.** They contain your Wi-Fi names, network addresses,
  location and serial numbers. If a log excerpt is needed, use the tool's redacted
  output and check it line by line before posting. Issues are public.
- **Pull requests:** run `python test_decovita.py` (all tests must pass), add a
  test for every fix or feature, standard library only, code and comments in
  English, user-facing texts in English and German.

## License

GNU General Public License v3.0 or later (`GPL-3.0-or-later`), see
[`LICENSE`](LICENSE). The test suite contains a Python port of parts of the parser
of [phdlogview](https://github.com/agalasso/phdlogview) (GPL v3).

## Disclaimer

- For research, analysis and interoperability purposes only, for example to evaluate
  your own guiding data or for troubleshooting.
- Unofficial: not a ToupTek product, not endorsed or reviewed by ToupTek. Trademarks
  and product names belong to their owners.
- No warranty: use at your own risk. Decoded content can contain errors (see
  "uncertain lines" in the statistics).
- Redaction is an aid, not a guarantee. Check the outputs yourself before you share
  them.
- Only use the tool on log files from your own device or with the permission of the
  entitled person.
