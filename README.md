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

## Wie die Logs kodiert sind

Jede Zeile ist einzeln mit einer Zeichenverschiebung über die druckbaren Zeichen
kodiert. Der Startwert ist pro Zeile zufällig, und die Verschiebung wächst mit der
Position im Text, fast immer um eins. Aus dem bekannten ersten Zeichen (`[` im
DebugLog, `2` für Datumszeilen im GuideLog) ergeben sich ein oder zwei mögliche
Startwerte; der Zeitstempel bestätigt den richtigen. Bei Zeilen ohne Zeitstempel
probiert das Skript alle 95 Startwerte durch und nimmt den plausibelsten Text.
Leerzeichen und `~` werden gleich kodiert und sind danach nicht unterscheidbar.

Das Verfahren wurde allein aus den Logdateien abgeleitet. Es gibt dazu keine
Dokumentation von ToupTek.

## Datenschutz

Die verschlüsselten Originaldateien enthalten immer alle Daten. Logs und Ausgaben
gehören nicht ins Repo (siehe `.gitignore`).

## Lizenz

GNU General Public License v3.0 oder später (`GPL-3.0-or-later`), siehe
[`LICENSE`](LICENSE). Die Testsuite enthält eine Python-Portierung von Teilen des
Parsers aus [phdlogview](https://github.com/agalasso/phdlogview) (GPL v3).

## Haftungsausschluss

- Nur für Forschungs-, Analyse- und Interoperabilitätszwecke, z. B. zur Auswertung
  der eigenen Guiding-Daten oder zur Fehlersuche.
- Inoffiziell: kein Produkt von ToupTek, nicht von ToupTek unterstützt oder geprüft.
  Marken- und Produktnamen gehören ihren Inhabern.
- Ohne Gewähr: Die Nutzung erfolgt auf eigene Gefahr. Entschlüsselte Inhalte können
  fehlerhaft sein (siehe "unsichere Zeilen" in der Statistik).
- Das Schwärzen ist eine Hilfe, keine Garantie. Prüfe die Ausgaben selbst, bevor du
  sie weitergibst.
- Verwende das Tool nur für Logdateien deines eigenen Geräts oder mit Erlaubnis
  der berechtigten Person.
