# pi-hotspot

## Bestätigter Umfang

- Öffentliches GitHub-Repository: leotrax3d/pi-hotspot.
- MIT-Lizenz für eigenen Projektcode; Lizenzen eingebundener Drittanbieter bleiben bestehen.
- Basis sind die direkt vom laufenden Arduino übernommenen Quellen.
- Ziel: frisch installiertes Raspberry Pi OS Lite 64 Bit auf Pi 3B/3B+, 4 und 5.
- CLI-Einrichtung mit einzeln auswählbaren Funktionen: Portal, Dashboard,
  Geräteverwaltung, Chat, Singleplayer, Multiplayer und optional Mullvad.
- Netzwerkvarianten: LAN-Uplink, WLAN mit separatem Hotspot-Adapter sowie
  experimentell gleichzeitiger WLAN-Uplink und Hotspot auf einem Adapter.
- Netzwerkänderungen erst nach Zusammenfassung und Bestätigung, mit Sicherung.
- Zugangsdaten, VPN-Schlüssel und Nutzerdaten gehören nicht ins Repository.

## Gewählte Einstellungen

- CLI-Auswahl: WLAN-Passwort, offenes WLAN/Portal und Voucher.
- VPN global und pro Gerät; Kill Switch bei Ausfall.
- DNS-Logging und Aufbewahrung im Installer abfragen (Option 2).
- pi-hotspot.local; manuelle Updates mit Sicherung.

## Stand der Übernahme

Die Ordner qspot, frontend, system und tests wurden am 17. November 2026 direkt
aus /opt/qspot auf dem per USB angeschlossenen Arduino übernommen.
Laufzeitdaten unter /var/lib/qspot und private VPN-Konfigurationen wurden nicht
kopiert. Der veraltete verschachtelte Ordner qspot/qspot sowie der lokale
Mullvad-Importhelfer wurden bei der Übernahme ausgeschlossen.

Der Installer und die Netzwerkabstraktion werden für Raspberry Pi angepasst.
Raspberry-Pi-Hardwaretests stehen aus; Einzelheiten im README.
