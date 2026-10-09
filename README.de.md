# DecoVita – StellaVita Log Tool

[English](README.md) | **Deutsch**

Inoffizielles Werkzeug zum Entschlüsseln, Schwärzen und Umwandeln der Logdateien
des ToupTek StellaVita. Keine Verbindung zu ToupTek.

## Funktionen

- `GuideLog_*.txt` und `DebugLog_*.txt` entschlüsseln
- Persönliche Daten schwärzen (standardmäßig an, einzeln abschaltbar):
  Hotspot/WLAN, Netzwerkadressen, Standort, Seriennummern
- GuideLogs zusätzlich ins PHD2-Format umwandeln (für phdlogview)
- `libtoupcam*.glog` (Klartext) schwärzen

## Voraussetzungen

- Python 3.11 oder neuer (getestet mit 3.11 bis 3.14), nur Standardbibliothek
- Für das Fenster: tkinter. Unter Arch/CachyOS ist das das Paket `tk`. Ohne
  tkinter oder ohne Bildschirm startet stattdessen ein Textmenü.

## Benutzung

```
python stellavita.py                     # Fenster (tkinter), sonst Textmenü
python stellavita.py <Datei|Ordner> [-r] [-o Ausgabeordner] [--lang de|en]
python stellavita.py --help              # alle Schalter
```

Nützliche Schalter:

- `--report` – Probelauf: zeigt, was geschwärzt würde, schreibt nichts
- `--no-redact-hotspot`, `--no-redact-network`, `--no-redact-location`,
  `--no-redact-serial` – eine Kategorie nicht schwärzen; `--no-redact` schwärzt nichts
- `--no-phd2` – keine PHD2-Datei für GuideLogs
- `--no-full-date` – DebugLog-Zeitstempel im Originalformat (ohne Datum)
- `--force` – vorhandene Ausgaben überschreiben

## Ausgaben

| Eingabe | Ausgabe |
|---|---|
| GuideLog | `<Name>_decoded.txt` und `<Name>_phd2.txt` |
| DebugLog | `<Name>_decoded.txt` (Zeitstempel mit vollem Datum) |
| `.glog` | `<Name>_redacted.glog` |

Die Ausgaben landen neben der Eingabe oder in einem Zielordner (`-o` in der
Kommandozeile, "Zielordner" im Fenster; wird bei Bedarf angelegt). Die
Originale werden nie verändert, und vorhandene Ausgaben werden nur mit `--force`
überschrieben. Jede Ausgabe beginnt mit einigen `# `-Zeilen zu Tool-Version und
Schwärzung.

## Was geschwärzt wird

- **Hotspot/WLAN:** Netzwerknamen werden zu `<SSID_1>`, `<SSID_2>`, …;
  Passwörter werden zu `<REDACTED>`.
- **Netzwerk:** Der dritte Teil von IP-Adressen wird ersetzt (`192.168.<N1>.23`).
  Geräte bleiben unterscheidbar, das Netz nicht.
- **Standort (DebugLog):** Breite und Länge werden auf 0,1° gerundet. Höhe und
  Azimut der Montierung, Sternzeit, Höhe über dem Meer und UTC-Zeit werden entfernt,
  weil sich daraus der Standort sehr genau zurückrechnen ließe.
- **Standort (GuideLog):** bleibt unverändert. Der Kopf enthält den Standort nur auf
  etwa 10 km genau.
- **Seriennummern:** Seriennummer der Kamera sowie die Felder Besitzer, Künstler und
  Copyright.

Das Schwärzen ist eine Hilfe, keine Garantie. Prüfe die Ausgaben selbst, bevor du
sie weitergibst.

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

## Bekannte Grenzen

- Leerzeichen und `~` sind nicht unterscheidbar (siehe oben).
- Zeilen, die nur aus Ziffern bestehen, können mehrdeutig sein. Die Statistik zählt
  solche Zeilen als "unsicher".
- phdlogview interpoliert die Zeitachse aus den Bildnummern. Ändert sich die
  Bildrate, sind die Zeitbeschriftungen irreführend; beim Überfahren mit der Maus
  wird die echte Zeit angezeigt.

## Datenschutz

Die verschlüsselten Originaldateien enthalten immer alle Daten. Logs und Ausgaben
gehören nicht ins Repo (siehe `.gitignore`).

## Tests

```
python test_stellavita.py
```

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
