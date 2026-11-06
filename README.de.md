# DecoVita

[English](README.md) | **Deutsch**

Inoffizielles Werkzeug zum Entschlüsseln, Schwärzen und Umwandeln der Logdateien
des ToupTek StellaVita. Keine Verbindung zu ToupTek.

## Funktionen

- `GuideLog_*.txt` und `DebugLog_*.txt` (Gerät) sowie `Logs_App_*.txt`
  (Handy-App) entschlüsseln
- Persönliche Daten schwärzen (standardmäßig an, einzeln abschaltbar):
  Hotspot/WLAN, Netzwerkadressen (IP und MAC), Standort, Seriennummern
- Jede geschwärzte Ausgabe auf übrig gebliebene persönliche Daten prüfen (Nachprüfung)
- Warnen, wenn sich ein Log nicht mehr sicher entschlüsseln lässt (z. B. weil ein
  Firmware- oder App-Update das Format geändert hat), und sich vor jedem Lauf an
  eingebauten Beispielzeilen selbst prüfen
- GuideLogs zusätzlich ins PHD2-Format umwandeln (für phdlogview)
- `libtoupcam*.glog` (Klartext) schwärzen

## Voraussetzungen

- Python 3.11 oder neuer (getestet mit 3.11 bis 3.14), nur Standardbibliothek
- Für das Fenster: tkinter (Pythons Schnittstelle zu Tcl/Tk). Ohne tkinter oder
  ohne Bildschirm nennt `python decovita.py` den Grund und startet stattdessen
  ein Textmenü. Die Kommandozeile (`python decovita.py <Datei|Ordner>`) braucht
  nie tkinter.

So prüfst du, ob dein Python tkinter hat:

```
python -c "import tkinter; print(tkinter.TkVersion)"   # gibt z. B. 8.6 aus
python -m tkinter                                      # öffnet ein kleines Testfenster
```

Scheitert der erste Befehl mit `ModuleNotFoundError`, fehlt tkinter:

- Windows (Installer von python.org): Installer erneut starten, „Modify“
  wählen und „tcl/tk and IDLE“ anhaken (standardmäßig angehakt).
- Linux: tkinter ist meist ein eigenes Paket, z. B. `tk` unter Arch/CachyOS,
  `python3-tk` unter Debian/Ubuntu.
- macOS (getestet mit macOS 27.2 auf Apple Silicon, Python 3.13): Der Installer
  von python.org enthält tkinter. Beim Python von Homebrew das passende Tk-Paket
  installieren, z. B. `brew install python-tk@3.13`.

## Benutzung

```
python decovita.py                     # Fenster (tkinter), sonst Textmenü
python decovita.py <Datei|Ordner> [-r] [-o Ausgabeordner] [--lang de|en]
python decovita.py --help              # alle Schalter
```

Nützliche Schalter:

- `--report` – Probelauf: zeigt, was geschwärzt würde, schreibt nichts
- `--no-redact-hotspot`, `--no-redact-network`, `--no-redact-location`,
  `--no-redact-serial` – eine Kategorie nicht schwärzen; `--no-redact` schwärzt nichts
- `--no-phd2` – keine PHD2-Datei für GuideLogs
- `--no-leak-check` – Nachprüfung auslassen (spart bei einem großen DebugLog etwa
  ein Fünftel der Laufzeit)
- `--no-full-date` – DebugLog-Zeitstempel im Originalformat (ohne Datum)
- `--force` – vorhandene Ausgaben überschreiben
- `--selftest` – nur den Selbsttest ausführen (siehe unten) und das Ergebnis zeigen

## Ausgaben

| Eingabe | Ausgabe |
|---|---|
| GuideLog | `<Name>_decoded.txt` und `<Name>_phd2.txt` |
| DebugLog | `<Name>_decoded.txt` (Zeitstempel mit vollem Datum) |
| App-Log (`Logs_App_*.txt`) | `<Name>_decoded.txt` |
| `.glog` | `<Name>_redacted.glog` (`<Name>_plain.glog` mit `--no-redact`) |

Die Ausgaben landen neben der Eingabe oder in einem Zielordner (`-o` in der
Kommandozeile, "Zielordner" im Fenster; wird bei Bedarf angelegt). Die
Originale werden nie verändert, und vorhandene Ausgaben werden nur mit `--force`
überschrieben. Jede Ausgabe beginnt mit einigen `# `-Zeilen zu Tool-Version und
Schwärzung.

## Was geschwärzt wird

- **Hotspot/WLAN:** Netzwerknamen werden zu `<SSID_1>`, `<SSID_2>`, …;
  Passwörter werden zu `<REDACTED>`.
- **Netzwerk:** Der dritte Teil von IP-Adressen wird ersetzt (`192.168.<N1>.23`).
  Geräte bleiben unterscheidbar, das Netz nicht. Das gilt für jede private
  IP-Adresse, egal wo sie im Log steht (öffentliche Adressen wie der Update-Server
  von ToupTek, Subnetzmasken und Versionsnummern bleiben), und MAC-/BSSID-Adressen
  werden zu `<MAC_1>`, `<MAC_2>`, ….
- **Gleicher Wert, gleicher Platzhalter:** Innerhalb eines Laufs bekommt ein Wert
  in allen Ausgabedateien denselben Platzhalter (z. B. ist `<SSID_1>` im DebugLog
  und im App-Log dasselbe Netz). Nummeriert wird in der Reihenfolge des ersten
  Auftretens. Die Zuordnung liegt nur im Speicher und wird nie gespeichert oder
  angezeigt.
- **Standort (DebugLog):** Breite und Länge werden auf 0,1° gerundet. Höhe und
  Azimut der Montierung, Sternzeit, der Stundenwinkel des Meridian-Flips, Höhe über
  dem Meer und UTC-Zeit werden entfernt, weil sich daraus der Standort sehr genau
  zurückrechnen ließe.
- **Standort (App-Log):** Breite und Länge werden auf 0,1° gerundet. Die GPS-Höhe,
  die berechneten Dämmerungs-, Sonnenauf- und -untergangszeiten und die Sternzeit der
  Himmelskarte werden entfernt, weil sie zusammen mit dem Datum den Standort verraten.
- **Standort (GuideLog):** bleibt unverändert. Der Kopf enthält den Standort nur auf
  etwa 10 km genau.
- **Seriennummern:** Seriennummer der Kamera sowie die Felder Besitzer, Künstler und
  Copyright.
- **Nicht geschwärzt:** Handymodell und Android-Version im App-Log.

Das Schwärzen ist eine Hilfe, keine Garantie. Prüfe die Ausgaben selbst, bevor du
sie weitergibst.

### Nachprüfung

Nach dem Schreiben liest das Tool jede geschwärzte Ausgabe noch einmal und sucht
mit eigenen, unabhängigen Mustern nach Resten: private IP-Adressen (und jede IP in
einem Adressfeld), MAC-Adressen, Koordinaten mit mehr als einer Nachkommastelle,
Standort- und Zeitwerte der Montierung, Dämmerungszeiten, WLAN-Namen und
-Passwörter, Seriennummern und lange Hex-Zeichenketten. Platzhalter wie
`<SSID_1>`, `<MAC_1>`, `<REDACTED>` oder `192.168.<N1>.23` gelten als sauber. So
fallen Werte auf, die durchrutschen, weil eine Logzeile ein Format hat, das das
Schwärzen nicht kennt.

Für jede betroffene Ausgabe erscheint eine Warnung mit Kategorie, Anzahl der Zeilen
und Zeilennummern, nie mit den Werten:

```
  ! Nachprüfung: vermutlich persönliche Daten übrig in DebugLog_2026-01-15_201500_decoded.txt – vor dem Weitergeben prüfen:
      Hotspot/WLAN 2 (Zeilen 5, 6)
```

Die Übersichtstabelle zeigt die Zahl der markierten Zeilen pro Datei in der Spalte
`Reste` (`-` = nicht geprüft). Geprüft werden nur geschwärzte Kategorien; ein
Probelauf (`--report`) und `--no-redact` prüfen nichts. Die Nachprüfung ist
standardmäßig an; `--no-leak-check` schaltet sie ab.

## Wie die Logs kodiert sind

Jede Zeile ist einzeln mit einer Zeichenverschiebung über die druckbaren Zeichen
kodiert. Der Startwert ist pro Zeile zufällig, und die Verschiebung wächst mit der
Position im Text, fast immer um eins. Aus dem bekannten ersten Zeichen (`[` im
DebugLog, `2` für Datumszeilen im GuideLog) ergeben sich ein oder zwei mögliche
Startwerte; der Zeitstempel bestätigt den richtigen. Bei Zeilen ohne Zeitstempel
probiert das Skript alle 95 Startwerte durch und nimmt den plausibelsten Text.
Leerzeichen und `~` werden gleich kodiert und sind danach nicht unterscheidbar.

Die Logs der Handy-App nutzen dasselbe Verfahren mit zwei Unterschieden:
Nicht-ASCII-Zeichen (z. B. chinesische Texte oder `℃`) bleiben unverändert und
zählen nicht als Position, und der Text ist doppelt UTF-8-kodiert. Das Tool macht
beides rückgängig.

Das Verfahren wurde allein aus den Logdateien abgeleitet. Es gibt dazu keine
Dokumentation von ToupTek.

### Decodier-Sicherheit und Selbsttest

Ein Firmware- oder App-Update könnte die Kodierung ändern. Das Tool würde dann
Zeichensalat erzeugen, und in Zeichensalat findet die Schwärzung keine
persönlichen Daten. Dagegen gibt es zwei Prüfungen:

- **Decodier-Sicherheit:** der Anteil der nicht leeren Zeilen einer Datei, die
  sicher entschlüsselt wurden (ein Zeitstempel hat den Startwert bestätigt, oder
  ein Startwert war klar der plausibelste). Er steht pro Datei in der Ausgabe
  (`Decodier-Sicherheit 100.0 %`) und in der Übersichtstabelle, Spalte `sicher`
  (`-` = nicht entschlüsselt, z. B. `.glog` oder eine schon entschlüsselte
  Datei). Alle bisherigen echten Logs erreichen 100.0 %. Unter 95 % wird der
  Wert mit `!` markiert, und eine Warnung sagt, dass sich das Format vermutlich
  geändert hat und die Schwärzung unvollständig sein kann. Dateien mit weniger
  als 20 Zeilen bekommen keine Warnung (zu wenig für ein Urteil).
- **Unbekanntes Format:** Eine Datei, die wie ein StellaVita-Log heißt
  (`GuideLog_*.txt`, `DebugLog_*.txt`, `Logs_App_*.txt`, `*.glog`), deren Inhalt
  sich aber gar nicht entschlüsseln lässt, wird mit einer Warnung übersprungen;
  die Tabelle zeigt `Format geändert?`.
- **Selbsttest:** Vor jedem Lauf entschlüsselt, schwärzt und prüft das Tool
  einige eingebaute, erfundene Beispielzeilen in den echten Logformaten. Schlägt
  das fehl, verarbeitet es nichts und nennt die fehlgeschlagenen Prüfungen.
  `--selftest` führt ihn allein aus.

## Bekannte Grenzen

- Leerzeichen und `~` sind nicht unterscheidbar (siehe oben).
- Zeilen, die nur aus Ziffern bestehen, können mehrdeutig sein. Die Statistik zählt
  solche Zeilen als "unsicher"; das senkt die Decodier-Sicherheit etwas.
- phdlogview interpoliert die Zeitachse aus den Bildnummern. Ändert sich die
  Bildrate, sind die Zeitbeschriftungen irreführend; beim Überfahren mit der Maus
  wird die echte Zeit angezeigt.

## Datenschutz

Die verschlüsselten Originaldateien enthalten immer alle Daten. Logs und Ausgaben
gehören nicht ins Repo (siehe `.gitignore`).

## Tests

```
python test_decovita.py
```

Die Fenster-Tests brauchen tkinter, unter Linux zusätzlich `Xvfb` (sonst werden sie
als SKIP gemeldet). Unter Windows und macOS öffnen sie sich kurz auf dem Desktop.
Jeder Pull Request wird automatisch unter Linux, Windows und macOS getestet
(GitHub Actions).

## Mitmachen

Fehlermeldungen, Ideen und Pull Requests sind willkommen, über
[GitHub Issues](https://github.com/ph3x/DecoVita/issues) und Pull Requests.

- **Fehlermeldungen:** bitte das Formular für Fehlermeldungen nutzen. Es fragt
  nach DecoVita-Version (Fenstertitel oder `--help`), Betriebssystem,
  Python-Version, dem verwendeten Befehl bzw. den Schritten sowie der Meldung oder
  der Übersichtstabelle.
- **Log-Proben gesucht:** Die Nachtanalyse soll später Filterwechsel,
  Meridian-Flips und Autofokus-Läufe erkennen, aber die Formate dieser Ereignisse
  sind noch unbekannt. Hast du ein Filterrad, einen Fokussierer oder Nächte mit
  Meridian-Flip, teile bitte einen geschwärzten Auszug über das
  [Formular für Log-Proben](https://github.com/ph3x/DecoVita/issues/new?template=log_sample.yml).
  Nur die Zeilen rund um das Ereignis aus der Ausgabe von DecoVita, nie das
  Original-Log. Prüfe jede Zeile selbst: Persönliche Daten in diesen Ereignissen
  kennt DecoVita vielleicht noch nicht.
- **Niemals Original-Logs anhängen.** Sie enthalten deine WLAN-Namen,
  Netzwerkadressen, deinen Standort und Seriennummern. Wird ein Log-Auszug
  gebraucht, nimm die geschwärzte Ausgabe des Tools und prüfe sie Zeile für Zeile,
  bevor du sie postest. Dateinamen der Logs enthalten Datum und Uhrzeit deiner
  Sitzung, ersetze sie also (auch in der Übersichtstabelle). Issues sind
  öffentlich.
- **Pull Requests:** `python test_decovita.py` ausführen (alle Tests müssen
  bestehen), für jede Korrektur und jede Funktion einen Test ergänzen, nur
  Standardbibliothek, Code und Kommentare auf Englisch, Texte für Nutzer auf
  Englisch und Deutsch.

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
