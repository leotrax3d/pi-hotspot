# pi-hotspot

Ein Raspberry Pi als WLAN-Hotspot mit animiertem SchülerWLAN-Portal,
shadcn-Dashboard, Geräteverwaltung, Chat und Games. Optional mit Mullvad/WireGuard,
VPN-Auswahl pro Gerät, lokalem DNS-Domain-Log und optionalem [Pi-hole DNS-Schutz](docs/pihole.md).

**Status: erste Raspberry-Pi-Portierung.** Der Ausgangscode stammt direkt vom
laufenden Arduino UNO Q. Softwaretests ersetzen keine Hardwaretests: eine
vollständige Installation auf Pi 3, 4 und 5 ist bisher **nicht auf echter
Pi-Hardware bestätigt**. Ein-Adapter-Betrieb ist experimentell.

## Installation mit einem Befehl

Auf einem **frisch installierten Raspberry Pi OS Lite 64 Bit** mit bestehender
Internetverbindung ausführen:

```bash
curl -fsSL https://raw.githubusercontent.com/leotrax3d/pi-hotspot/main/install.sh -o /tmp/pi-hotspot-install.sh && sudo bash /tmp/pi-hotspot-install.sh
```

Bei fehlenden USB-Treibern zeigt der Assistent zuerst eine separate Treiber-Zusammenfassung und richtet sie nach Bestätigung ein. Dafür ist eine bereits funktionierende Internetverbindung erforderlich.

Der Assistent fragt alle Einstellungen in der Kommandozeile ab. Er zeigt vor
Änderungen eine Zusammenfassung und verlangt eine Bestätigung. Passwörter werden
verdeckt eingegeben. Die Installation benötigt Root-Rechte auf dem **Pi**;
Administratorrechte auf dem Windows-PC sind nicht erforderlich.

Alternativ zuerst den Code ansehen und aus einem Checkout installieren:

```bash
git clone https://github.com/leotrax3d/pi-hotspot.git
cd pi-hotspot
sudo bash install.sh --check
sudo bash install.sh
```

Der Installer installiert Linux-Pakete, richtet Netzwerk, Firewall, DHCP/DNS,
lokales HTTPS, Admin-Zugang und automatisch startende systemd-Dienste ein.
Die Weboberfläche ist bereits gebaut; Node.js wird auf dem Pi nicht benötigt.
Netzwerk und SSH können während der Umstellung kurz unterbrochen werden.

## Hardware und Netzwerke

| Gerät | Betriebssystem | Status |
| --- | --- | --- |
| Raspberry Pi 3B / 3B+ | Raspberry Pi OS Lite 64 Bit, Bookworm oder Trixie | Zielplattform; Hardwaretest offen |
| Raspberry Pi 4B | gleich | Zielplattform; Hardwaretest offen |
| Raspberry Pi 5B | gleich | Zielplattform; Hardwaretest offen |

| Modus | Internet | Hotspot |
| --- | --- | --- |
| LAN | Ethernet | integriertes WLAN oder USB-WLAN |
| Zwei Adapter | WLAN-Adapter A | WLAN-Adapter B |
| Ein Adapter, experimentell | WLAN-Client | virtuelle AP-Schnittstelle desselben Radios |

Der erste Installer richtet den Hotspot für **Deutschland auf 2,4 GHz, Kanal
1–11** ein. Im Ein-Adapter-Modus folgt der Hotspot dem Kanal des 2,4-GHz-Uplinks.
Der Treiber muss AP und Station gleichzeitig erlauben. Ein Kanalwechsel des
Upstream-WLANs kann eine Neueinrichtung des Hotspots erfordern. 5-GHz- und
DFS-Hotspots sind in dieser Version nicht implementiert.

USB-Adapter benötigen einen Linux-Treiber mit AP-Modus.
Der Installer erkennt USB-WLAN-Adapter und richtet unterstützte Treiber automatisch ein. AIC8800-Adapter einschließlich UGREEN CM762/CM763 erhalten einen gepinnten Radxa-DKMS-Treiber, Firmware, passende Kernel-Header und erforderliche USB-Moduswechsel. Realtek/MediaTek werden über Kernelmodule und Distributions-Firmware versorgt. Ein generischer 1111:1111-Datenträger wird ohne passende Produktkennung nur nach expliziter Modellauswahl umgeschaltet. Unbekannte Chips werden nicht mit einem beliebigen Fremdtreiber behandelt. Ein erfolgreicher Build bestätigt noch keinen AP-Betrieb auf jedem Pi.
LAN + integriertes WLAN ist die Ausgangskonfiguration mit den wenigsten
Treiberabhängigkeiten.

WLAN-Uplink: Personal-WLAN, offen oder WPA2 Enterprise mit PEAP/MSCHAPv2.
Enterprise fragt Benutzername, Passwort, vertrauenswürdige Server-Domain und
optional eine CA-Datei ab; ohne CA-Datei werden System-Zertifikate verwendet.
Andere EAP-Varianten müssen vorab in NetworkManager eingerichtet werden.
Ein vorhandenes NetworkManager-Profil kann unverändert weitergenutzt werden.

## Auswählbare Funktionen

- Portal und Dashboard als Grundsystem; WPA2-Passwort oder offenes Gast-WLAN,
  jeweils mit Portal und optionalen Voucher-Codes.
- Chat mit Namen, Online-Anzeige, Wortfilter und Linkfilter.
- Acht Singleplayer-Games mit lokalen Rekorden.
- Multiplayer mit Lobbys: Pong, Tic-Tac-Toe, Vier gewinnt und Reaktion.
- Optional Mullvad/WireGuard mit Dashboard-Schalter und VPN-Auswahl pro Gerät.
- Optional kompakte farbige DNS-Domain-Logs in JetBrains Mono.

Chat, Singleplayer, Multiplayer und VPN lassen sich im CLI-Assistenten einzeln
aktivieren. Die Auswahl steuert Verfügbarkeit und sichtbare Community-Ansichten;
es wird ein gemeinsames Softwarepaket installiert. Datenvolumen, Sitzungsdauer
und Bandbreite sind standardmäßig unbegrenzt und im Dashboard konfigurierbar.
Die Arduino-LED-Matrix gehört nicht zur Pi-Version.

## Name und Portal-Adresse

Unter **Einstellungen → Portal → Name** wird das Projekt global umbenannt. Vorkommen des bisherigen Namens in SSID und Portaltexten sowie daraus abgeleitete Hostnamen und Domains folgen automatisch. Unabhängig gewählte Namen/Adressen und ausdrücklich neue Domain-Eingaben bleiben erhalten. Anzeigename, Portal-Domain, WLAN-SSID, Titel und Portaltexte sind auch einzeln konfigurierbar. Beispiel: `Campus Nord` und `login.campus.lan`. DNS, Weiterleitungen, Browser-Titel, Chat, Dashboard, Authenticator-Name und das lokale TLS-Zertifikat folgen der Konfiguration. Domains werden als DNS-Namen validiert; URLs mit Pfad oder Port sind keine Domain. Internationale Domains werden in IDNA umgewandelt.

Die Adresse wird im Hotspot lokal aufgelöst. Ein eigener Name registriert keine öffentliche Domain. Namen unter `.local` erhalten bei Bedarf einen Avahi-Eintrag für die Hotspot-IP. Auf dem Uplink bleibt die Pi-IP die Ausweichadresse. Nach einer Domain-Änderung muss das neu erzeugte lokale Zertifikat erneut geprüft werden. Netzwerkänderungen erfordern weiter die Erreichbarkeitsbestätigung innerhalb von 120 Sekunden.

Gerätenamen werden aus aktuellen DHCP-Leases angezeigt, sofern das Gerät einen Namen übermittelt. Die Zuordnung verwendet MAC und IP; IP und MAC bleiben sichtbar. Es erfolgen keine zusätzlichen DNS-Abfragen oder Netzwerkscans.

## Verwaltung

Nach der Einrichtung: **https://pi-hotspot.local/admin** oder
**https://10.77.0.1/admin** (falls die Standard-IP gewählt wurde).
Der lokale Name hängt von der mDNS-Unterstützung des Clients ab; die IP ist
die Ausweichadresse. Über den LAN-Uplink ist auch die LAN-IP des Pi erreichbar.

Das lokale Zertifikat ist selbstsigniert. Der Installer zeigt seinen SHA-256-
Fingerabdruck. Vor dem Vertrauen im Browser mit dem Fingerabdruck am Pi
vergleichen. Admin-Passwort und Hotspot-Passwort sind getrennt.

```bash
sudo pi-hotspot status       # Dienste
sudo pi-hotspot logs         # Diagnose
sudo pi-hotspot doctor       # Zustand ohne Zugangsdaten
sudo pi-hotspot recover      # abgebrochene Installation wiederherstellen
sudo pi-hotspot drivers      # USB-WLAN-Treiber erkennen/einrichten
sudo pi-hotspot configure    # Assistent erneut vollständig durchlaufen
sudo pi-hotspot backup       # lokale Root-Sicherung
sudo pi-hotspot update       # manuelles Update von main mit Sicherung
```

Neu-Konfiguration übernimmt bestehende Einstellungen als Vorgaben. Profile, Portaltexte, Voucher- und Sitzungsdaten bleiben erhalten. Ein leeres Admin-Passwort behält den bisherigen Zugang einschließlich 2FA bei. Ein ausdrücklich neu gesetztes Passwort setzt die bisherige 2FA-Konfiguration zurück.

## Automatischer Start

Nach erfolgreicher Installation sind Routersteuerung, Weboberfläche und Namensauflösung dauerhaft über systemd aktiviert. Die Routersteuerung erzeugt beim Start die Laufzeitkonfiguration und startet Hotspot und DHCP/DNS. Eine Anmeldung am Pi oder ein manueller Startbefehl ist nicht erforderlich.

Fehlgeschlagene Dienste werden erneut gestartet, auch wenn ein USB-Adapter erst spät erscheint. Gespeicherte Adapter-MACs helfen, geänderte WLAN-Interface-Nummern wieder zuzuordnen. NetworkManager verbindet den gespeicherten Uplink automatisch. Bei getrenntem Uplink und Hotspot kann das lokale Portal auch ohne Internet starten. VPN-Verbindungen werden mit begrenzter Wiederholungsrate erneut aufgebaut; der Kill Switch bleibt aktiv. Im experimentellen Ein-Adapter-Modus ist der Hotspot weiterhin vom verbundenen Uplink-Kanal abhängig.

Ein echter Kaltstart-/Stromausfalltest auf jedem Pi-Modell steht weiterhin aus.

## VPN und Privatsphäre

Eine eigene Mullvad-WireGuard-`.conf` im Installer auswählen oder später im
Dashboard importieren. Schlüssel bleiben rootgeschützt auf dem Pi. Der Import
akzeptiert keine ausführbaren `PostUp`-/`PreDown`-Hooks.

Der globale VPN-Schalter gilt für Hotspot-Geräte. Einzelne Geräte können danach
in der Geräteliste vom VPN ausgenommen werden. Die Auswahl wird anhand der
MAC-Adresse gespeichert; eine neue zufällige MAC ist ein neues Gerät.
Ausgenommene Geräte verwenden den direkten Uplink. Der Verwaltungsverkehr des
Pi selbst wird nicht pauschal durch den VPN geleitet.

Für VPN-Geräte blockieren Firewall und Policy-Routing den direkten Ausweg bei
Tunnelausfall. IPv6 wird im Gastnetz gesperrt. Bei eingeschaltetem VPN verwendet
der gemeinsame lokale DNS-Resolver VPN-DNS, **auch für vom VPN ausgenommene
Geräte**; deren übriger Internetverkehr geht direkt. Fällt der Tunnel aus, kann
dadurch die Namensauflösung auch auf diesen Geräten ausfallen. Individuell
getrennte DNS-Resolver sind in dieser Version nicht enthalten.

DNS-Logging ist standardmäßig ausgeschaltet. Bei Aktivierung fragt der Installer
die Aufbewahrung von 1–168 Stunden ab und ergänzt einen Hinweis im Portal.
Gespeichert werden höchstens 2.000 Domain-Ereignisse, keine vollständigen HTTPS-
URLs oder Seiteninhalte. Bereinigung erfolgt etwa alle 30 Sekunden, solange
der Dienst läuft. Rohdaten liegen begrenzt unter `/run`, nicht im Systemjournal.
Verschlüsseltes DNS kann diese Erfassung umgehen. Chat und Multiplayer-Zustände
liegen im Arbeitsspeicher und werden bei Dienstneustart verworfen.

## Sicherung und Wiederherstellung

Vor der Netzwerkeinrichtung und Updates entsteht eine lokale Sicherung unter
`/var/backups/pi-hotspot/<Zeitstempel>/`. Sie enthält gegebenenfalls Passwörter,
VPN-Schlüssel und Nutzerdaten und ist ausschließlich für Root lesbar.
Vor Paket- und Netzwerkänderungen wird eine geprüfte Sicherung mit SHA-256-Prüfsumme erstellt; SQLite wird über seine Backup-API konsistent gesichert. Der Installer sperrt parallele Installationen und Updates.

Ein separater systemd-Timer stellt bei einer abgebrochenen Installation nach 45 Minuten, bei einem abgebrochenen Update nach 15 Minuten wieder her. Ein dauerhaft gespeicherter Transaktionsmarker und ein eigener Boot-Dienst decken einen Neustart oder Stromausfall während dieser Phase ab. Vor dem Wiederherstellen wird das Archiv geprüft und in ein temporäres Verzeichnis entpackt; beschädigte Archive oder unsichere Pfade führen vor dem Anhalten der Dienste zum Abbruch. Nach erfolgreichen Dienst-, Autostart- und HTTPS-Prüfungen werden Timer und Marker entfernt.

Die Treibervorbereitung bleibt eine getrennte, vorab bestätigte Phase. Installierte Pakete, Firmware und Kernelmodule werden durch die Anwendungssicherung nicht rückgängig gemacht.

Bei einem Fehler wird sofort zurückgerollt. Eine Sicherung manuell herstellen:

```bash
sudo pi-hotspot recover
# Falls der CLI-Befehl nach einem Abbruch noch nicht installiert ist:
sudo python3 /var/lib/pi-hotspot/recovery.py --manual
# Alternativ eine bestimmte Sicherung:
sudo python3 /var/backups/pi-hotspot/<Zeitstempel>/rollback.py /var/backups/pi-hotspot/<Zeitstempel>
```

Wiederherstellung setzt die gesicherten Projekt-/Netzwerkdateien zurück. Bereits
installierte Linux-Pakete, USB-Treiber, Firmware, DKMS-Registrierungen und der Systembenutzer werden nicht entfernt. Sie ist
kein vollständiges SD-Karten-Image und stellt keine fremden Firewall-Dienste
wieder her. Gedacht für einen dedizierten, frisch installierten Pi.

## Entwicklung und Tests

```bash
python3 -m pip install flask cryptography
python3 -m unittest discover -s tests -v
python3 -m compileall -q qspot installer
bash -n install.sh installer/pi-hotspot
cd frontend
npm ci
npm run build
node package-static.mjs
```

Frontend-Entwicklung benötigt eine aktuelle unterstützte Node.js-Version
(24 empfohlen). Änderungen am Frontend auch in `qspot/static/app` neu paketieren,
damit der Installer die aktuelle Oberfläche erhält.

Die Tests prüfen Konfigurationsvalidierung, Authentifizierung/CSRF, Geräte-
Aktionen, VPN-Routing-Befehle und Firewall-Regeln. Ein echter Test von DHCP,
WPA2 Enterprise, AP-Treiber, Internet und VPN-Ausfall auf jedem Pi-Modell ist
vor produktivem Einsatz weiterhin erforderlich.

Technische Grundlagen: [Raspberry-Pi-Netzwerkkonfiguration](https://www.raspberrypi.com/documentation/computers/configuration.html)
und [NetworkManager-Einstellungen](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html).

## Lizenz

Eigener Projektcode: [MIT](LICENSE). Eingebundene Bibliotheken und Schriftarten
behalten ihre jeweiligen Lizenzen; siehe `THIRD_PARTY_LICENSES.txt` und die
Paketmetadaten in `frontend/package-lock.json`. Es werden keine persönlichen
Zugangsdaten, Mullvad-Profile oder Daten vom Arduino veröffentlicht.

USB-Treiberquelle: [Radxa AIC8800, gepinnter Stand](https://github.com/radxa-pkg/aic8800/tree/5562c254b0231be34588dc608ec28c4f1d613285). [UGREEN Linux-Treiber für CM762/CM763](https://www.lulian.cn/download/462.html). [AIC-Moduswechsel auf Raspberry Pi](https://github.com/olamellberg/AIC8800D80/tree/98ccdbf60385f6bdb8071588ec95164aa606ca14). Treiber und Firmware bleiben unter ihren jeweiligen Upstream-Lizenzen; der Installer lädt sie getrennt herunter.

Startverhalten: [systemd.service](https://freedesktop.org/software/systemd/man/latest/systemd.service.html) und [Startbegrenzung](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit).
