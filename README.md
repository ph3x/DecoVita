# DecoVita – StellaVita Log Tool

**English** | [Deutsch](README.de.md)

Unofficial tool to decode, redact and convert the log files of the ToupTek
StellaVita. Not affiliated with ToupTek.

## Features

- Decode `GuideLog_*.txt` and `DebugLog_*.txt`
- Redact personal data (on by default, each category can be switched off):
  hotspot/Wi-Fi, network addresses, location, serial numbers
- Additionally convert GuideLogs to PHD2 format (for phdlogview)
- Redact `libtoupcam*.glog` files (plain text)

## Requirements

- Python 3.11 or newer, standard library only
- For the window: tkinter. On Arch/CachyOS this is the package `tk`. Without
  tkinter or without a display the tool falls back to a text menu.

## Usage

```
python stellavita.py                     # window (tkinter), otherwise text menu
python stellavita.py <file|folder> [-r] [-o OUTPUT_FOLDER] [--lang de|en]
python stellavita.py --help              # all switches
```

Useful switches:

- `--report` – dry run: shows what would be redacted, writes nothing
- `--no-redact-hotspot`, `--no-redact-network`, `--no-redact-location`,
  `--no-redact-serial` – keep one category; `--no-redact` keeps everything
- `--no-phd2` – no PHD2 file for GuideLogs
- `--no-full-date` – keep the original DebugLog time format (without date)
- `--force` – overwrite existing outputs

## Outputs

| Input | Output |
|---|---|
| GuideLog | `<name>_decoded.txt` and `<name>_phd2.txt` |
| DebugLog | `<name>_decoded.txt` (timestamps with full date) |
| `.glog` | `<name>_redacted.glog` |

The outputs are written next to the input, or into the folder given with `-o`.
The originals are never modified, and existing outputs are only overwritten with
`--force`. Every output starts with a few `# ` lines stating the tool version and
what was redacted.

## What gets redacted

- **Hotspot/Wi-Fi:** network names become `<SSID_1>`, `<SSID_2>`, …;
  passwords become `<REDACTED>`.
- **Network:** the third part of IP addresses is replaced (`192.168.<N1>.23`).
  Devices stay distinguishable, the network does not.
- **Location (DebugLog):** latitude and longitude are rounded to 0.1°. Mount
  altitude/azimuth, sidereal time, elevation and UTC time are removed, because the
  site could be reconstructed from them very precisely.
- **Location (GuideLog):** unchanged. The header only contains the location at
  roughly 10 km precision.
- **Serial numbers:** camera serial number, owner, artist and copyright fields.

Redaction is an aid, not a guarantee. Check the outputs yourself before you share
them.

## How the logs are encoded

Each line is encoded on its own with a character shift over the printable
characters. The start value is random per line, and the shift grows with the
position in the text, almost always by one. The known first character (`[` in the
DebugLog, `2` for date lines in the GuideLog) gives one or two possible start
values; the timestamp confirms the right one. For lines without a timestamp the
script tries all 95 start values and keeps the most plausible text. Space and `~`
are encoded the same way and cannot be told apart afterwards.

The scheme was derived from the log files alone. There is no documentation of it
from ToupTek.

## Known limits

- Space and `~` cannot be distinguished (see above).
- Lines consisting only of digits can be ambiguous. The statistics count such lines
  as "uncertain".
- phdlogview interpolates its time axis from the frame numbers. When the frame rate
  changes, the time labels are misleading; hovering shows the true time.

## Privacy

The encrypted original files always contain all data. Logs and outputs do not
belong in the repository (see `.gitignore`).

## Tests

```
python test_stellavita.py
```

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
