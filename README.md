# DecoVita – StellaVita Log Tool

Inoffizielles Werkzeug zum Entschlüsseln, Schwärzen und Umwandeln der Logdateien
des ToupTek StellaVita. Keine Verbindung zu ToupTek.

## Funktionen

- `GuideLog_*.txt` und `DebugLog_*.txt` entschlüsseln
- Persönliche Daten schwärzen (standardmäßig an, einzeln abschaltbar):
  Hotspot/WLAN, Netzwerkadressen, Standort, Seriennummern
- GuideLogs zusätzlich ins PHD2-Format umwandeln (für phdlogview)
- `libtoupcam*.glog` (Klartext) schwärzen

## Benutzung

```
python stellavita.py                     # Fenster (tkinter), sonst Textmenü
python stellavita.py <Datei|Ordner> [-r] [-o Ausgabeordner] [--lang de|en]
python stellavita.py --help              # alle Schalter
```

Unter Arch/CachyOS braucht das Fenster das Paket `tk`.

## Tests

```
python test_stellavita.py
```

## Datenschutz

Die verschlüsselten Originaldateien enthalten immer alle Daten. Logs und Ausgaben
gehören nicht ins Repo (siehe `.gitignore`).
