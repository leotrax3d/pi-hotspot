# Pi-hole

Optional im CLI unter **Pi-hole DNS-Schutz** auswählbar. Nachträglich:
`sudo pi-hotspot configure`. Unterstützte Zielsysteme bleiben Raspberry Pi OS
Lite 64 Bit (Bookworm/Trixie) auf Pi 3B/3B+, 4 und 5.

## Dienste und Ports

Das offizielle Image `docker.io/pihole/pihole:2026.11.0` läuft mit rootful
Podman und Host-Netzwerk unter `qspot-pihole.service`. Kein Docker-Daemon,
keine Bridge, keine automatisch eingefügten Container-NAT-Regeln. systemd
startet den Dienst beim Booten und nach Abstürzen erneut. Das Image wird bei
Installation und `sudo pi-hotspot update` automatisch geladen. Versionswechsel
erfolgen kontrolliert durch eine im Repository angehobene Image-Version;
kein unbeaufsichtigter Wechsel auf `latest`. Blocklisten aktualisiert Pi-holes
eigener Scheduler. Updates benötigen Internet; bereits geladene Images und
Blocklisten bleiben offline nutzbar.

| Dienst | Bindung | Aufgabe |
| --- | --- | --- |
| Pi-hole FTL | TCP/UDP 5354 | DNS, Filter, Gerätezuordnung |
| bisheriger dnsmasq | Gast-IP:53, UDP 67 | DHCP; lokale Notfallauflösung |
| Pi-hole v6 API | 127.0.0.1:8081 | ausschließlich Backend |
| Portal / Dashboard | 8080 / 8443 | unverändert |

Der Installer prüft belegte Pi-hole-Ports. nftables leitet DNS-Anfragen an
Gast-Port 53 direkt auf FTL um, **ohne Proxy und ohne Änderung der Quell-IP**.
Der Gast sieht weiterhin seine Router-IP als DNS-Server. FTL erhält die echte
Geräte-IP und kann über die lokale Nachbartabelle MAC-Regeln zuordnen. FTL-Port
5354 ist vom Uplink gesperrt, die API nur über Loopback zugänglich. DHCP bleibt
beim bisherigen Dienst. Pi-holes DHCP und NTP-Server sind deaktiviert.

Portal-Domain und `<hostname>.local` werden in beiden Resolvern explizit
hinterlegt. Globale Namensänderungen aktualisieren auch Pi-hole. Zugriff per
Gast-IP funktioniert unabhängig von DNS.

## VPN und Ausfälle

Bei aktivem Mullvad nutzt FTL ausschließlich die DNS-Adressen des ausgewählten
VPN-Profils. Die vorhandenen Host-Routen und der nftables-Ausgangsschutz
verhindern deren direkten Versand über den Uplink. **Auch Geräte mit
VPN-Ausnahme verwenden diesen gemeinsamen VPN-DNS**; nur ihr übriger Verkehr
geht direkt. Eine Filterausnahme deaktiviert die Filterung, nicht den VPN-DNS.
Es gibt keinen öffentlichen Ersatz-DNS bei einem VPN-Ausfall.

Alle fünf Sekunden prüft die Routersteuerung API und eine echte lokale
DNS-Antwort. Bei FTL-/API-Ausfall wird auf den lokalen dnsmasq umgeleitet und
DNS-Conntrack gelöscht. Dieser Resolver hat bei installiertem Pi-hole **keine
externen Upstreams**: Portalnamen bleiben verfügbar, externe Domains werden
nicht ungefiltert aufgelöst. Nach Wiederanlauf wird FTL wieder verwendet. Bis
zur Erkennung kann eine Anfrage fehlschlagen; die Verwaltung ist per IP sofort
erreichbar. Bei abgewähltem Modul erhält dnsmasq wieder seine bisherigen
Upstreams. Filter ausschalten oder pausieren lässt FTL weiterlaufen.

## Dashboard und Daten

**DNS-Schutz** bietet Filter-Schalter, feste Fünf-Minuten-Pause, Tageszähler,
Domain erlauben/sperren, Filter pro Gerät sowie ein farbiges Domain-Log mit
Suche. Geräte ohne eigene Regel erhalten die Standardfiltergruppe; ausgenommene
MACs erhalten keine Filtergruppe. Neue zufällige MACs sind neue Geräte.
Pausenfrist und gewünschter Schaltzustand werden rootgeschützt gespeichert;
ein Neustart verlängert die Pause nicht. Lokale Portal-Domains können über
diese Oberfläche nicht gesperrt werden.

Zugangspasswort wird auf dem Pi zufällig erzeugt, nur rootgeschützt abgelegt
und nie über unsere API ausgegeben. Pi-hole-Sitzungen bleiben im Backend.
Es gibt keine zweite Anmeldung und kein eingebettetes Pi-hole-Frontend.
Statusabfragen werden fünf Sekunden gemeinsam zwischengespeichert, maximal
200 Logzeilen pro Antwort. Browser-Polling und Änderungen laufen nacheinander.

DNS-Logging bleibt standardmäßig aus. Dann gilt Pi-hole-Privatsphäre 3 und
es werden keine Domain-/Client-Logs angezeigt. Bei Aktivierung gibt es nur
FTLs flüchtige RAM-Historie; persistente Query-Datenbank und alle drei
Pi-hole-Logdateien sind deaktiviert. Die Historie reicht höchstens 24 Stunden,
auch bei länger gewählter Aufbewahrung. Für kürzere Fristen wird die gesamte
RAM-Historie vor Ablauf der Frist gelöscht; sie ist dadurch teilweise kürzer
als die gewählte Frist. Bei nicht erreichbarer API erzwingt ein Dienstneustart
die Löschung. Alte dnsmasq-Logs werden beim Modulwechsel beseitigt.

Nur anonyme Tageszähler ohne Domains oder Geräte werden dauerhaft gespeichert;
sie werden etwa alle 30 Sekunden aktualisiert und beim Tageswechsel ersetzt.
Sie sind Betriebsstatistiken, keine revisionssichere Abrechnung; Abstürze oder
rollierende FTL-Zähler können kleine Abweichungen verursachen. Browser zeigt
Domains, keine vollständigen HTTPS-Adressen. DoH/DoT kann DNS-Filter umgehen;
HTTPS wird nicht entschlüsselt.

## Sicherung und Diagnose

CLI-Sicherungen enthalten unter `/var/lib/qspot` Pi-hole-Konfiguration,
Gravity-Datenbank, API-Passwort und Schaltzustand sowie die systemd-Unit.
Ein laufender Container wird für die Archivierung kurz eingefroren, damit
SQLite-Dateien einschließlich WAL konsistent bleiben. Wiederherstellung hält
FTL zuerst an und stellt Dienstzustand und Dateien wieder her; ältere
Sicherungen ohne Pi-hole bleiben kompatibel. Sicherungen sind rootgeschützt
und können Zugangsdaten und frühere Konfigurationsstände enthalten.
Installierte Podman-Pakete und heruntergeladene Images bleiben nach Rollback
vorhanden; sie ändern ohne aktiven Dienst kein Routing.

`sudo pi-hotspot doctor` zeigt Dienst-/Autostartstatus, Listener und
Image-Version, keine API-Passwörter. Zusätzlich:
`sudo journalctl -u qspot-pihole --no-pager -n 50`.

## Validierung

Unit-Tests prüfen Auswahl, lokale DNS-Notlösung, VPN-Firewall, MAC-Regeln,
Eingabevalidierung, Cache, feste Pause, Neustart-Wiederaufnahme und
RAM-Logbereinigung. Linux-CI startet das echte offizielle Image und prüft die
v6-API. Der Podman-Test verwendet systemd und einen eigenen Netzwerk-Namespace
für Client-IP/MAC, DNS-Umleitung, Filterung und Ausfall/Wiederanlauf.
Playwright prüft die vorhandenen Funktionen sowie DNS-Steuerung, Geräteschalter
und Suche bei Desktop- und Mobilbreite mit kontrollierten API-Fixtures.

Diese Prüfungen ersetzen **keinen realen Pi-Kaltstart**, WLAN-Treiber-/Funk-Test,
Mullvad-Tunneltest oder Leistungstest auf Pi 3. Pi-Hardware war für diese
Integration nicht angeschlossen.

Offizielle Quellen:
[Docker-Konfiguration](https://docs.pi-hole.net/docker/configuration/),
[FTL-Konfiguration](https://docs.pi-hole.net/ftldns/configfile/),
[API](https://docs.pi-hole.net/api/),
[API-Authentifizierung](https://docs.pi-hole.net/api/auth/),
[API-Spezifikation](https://github.com/pi-hole/FTL/tree/master/src/api/docs/content/specs).
