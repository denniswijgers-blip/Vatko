# Vakto draaien op een echte server

Dit bestand gaat over stap 9: van "hij draait op mijn laptop" naar "er
werken twee mensen op". Alles hieronder is één keer instellen en daarna
nooit meer aankomen.

Voor de duidelijkheid vooraf: **je hebt hier geen VPS voor nodig zolang
je de enige gebruiker bent.** Een oude laptop in de meterkast doet het
ook. Wat wél moet zodra er een klant op zit, staat hieronder.

---

## De korte versie

```bash
# eenmalig
sudo -u postgres createdb vakto
cd /srv/vakto/server
bash opzetten.sh                      # schema, configuratie, alle tests
pip install -r requirements.txt

# starten
python3 -m vakto.web --adres 127.0.0.1 --poort 8000 --https
```

De eerste keer dat je het scherm opent vraagt hij om een beheerder aan
te maken. Daarna is die weg dicht (R-GEB-08).

Vier dingen moeten er nog omheen, en die staan hieronder:

| | Waarom |
|---|---|
| **https** | zonder gaan wachtwoorden leesbaar over de lijn |
| **systemd** | anders is hij weg zodra je je terminal sluit |
| **back-up** | de enige verzekering die je hebt |
| **een firewall** | poort 8000 en 5432 horen niet open te staan |

---

## https, met nginx ervoor

De webserver van Vakto praat http en dat blijft zo. Er staat een nginx
voor die https doet en het doorzet — dat is de gewone manier, en het
scheelt dat er geen certificaatafhandeling in de applicatie zit.

**Zonder https zijn wachtwoorden leesbaar** voor iedereen tussen de
tablet op de vloer en de server. Op een bedrijfsnetwerk is dat niet
theoretisch: een wifi-punt in het magazijn is een wifi-punt.

```nginx
server {
    listen 443 ssl;
    server_name vakto.jouwklant.nl;

    ssl_certificate     /etc/letsencrypt/live/vakto.jouwklant.nl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vakto.jouwklant.nl/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Alles wat op http binnenkomt gaat naar https.
server {
    listen 80;
    server_name vakto.jouwklant.nl;
    return 301 https://$host$request_uri;
}
```

Het certificaat is gratis: `sudo certbot --nginx -d vakto.jouwklant.nl`.
Certbot vernieuwt het daarna zelf.

**Start Vakto dan met `--https`.** Dat zet de vlag `Secure` op het
sessiekoekje, zodat de browser hem nooit over een onversleutelde
verbinding stuurt. Zonder die vlag zou één verkeerd getypte `http://`
het koekje alsnog over de lijn sturen.

En laat `--adres` op `127.0.0.1` staan. De nginx zit op dezelfde machine
en heeft niet meer nodig; wie het rechtstreeks op poort 8000 probeert,
komt er dan niet in.

---

## systemd: hij moet blijven draaien

`/etc/systemd/system/vakto.service`:

```ini
[Unit]
Description=Vakto WMS
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=vakto
WorkingDirectory=/srv/vakto/server
Environment=PGDATABASE=vakto
ExecStart=/usr/bin/python3 -m vakto.web --adres 127.0.0.1 --poort 8000 --https
Restart=always
RestartSec=5

# De applicatie hoeft nergens te schrijven behalve in de database.
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vakto
sudo systemctl status vakto        # draait hij?
sudo journalctl -u vakto -f        # wat zegt hij?
```

`Restart=always` is het belangrijkste regeltje: gaat er iets mis, dan
staat hij vijf seconden later weer aan en heeft niemand het gemerkt.

Draai hem onder een eigen gebruiker (`vakto`), niet onder `root`. Dan is
een fout in de applicatie hooguit een fout in de applicatie.

---

## Back-up

```bash
bash db/backup.sh                  # een dump wegschrijven
bash db/backup.sh --proef          # én meteen toetsen of hij terug kan
```

In een cron, elke nacht:

```cron
0 3 * * *   cd /srv/vakto/server && bash db/backup.sh >> /var/log/vakto-backup.log 2>&1
0 4 1 * *   cd /srv/vakto/server && bash db/backup.sh --proef >> /var/log/vakto-backup.log 2>&1
```

Twee dingen die vaak misgaan, en waar dit script iets aan doet:

1. **De dump staat op dezelfde schijf als de database.** Die schijf gaat
   een keer stuk en neemt allebei mee — precies het geval waar je een
   back-up voor hebt. Zet er een regel achter die hem naar een andere
   machine kopieert, en zet `VAKTO_BACKUP` naar een gekoppelde schijf.
2. **Niemand heeft hem ooit teruggezet.** `--proef` doet dat wél: hij
   zet de verse dump terug in een wegwerpdatabase en telt na of de
   rijen en de `vakto_`-functies er nog zijn. Eén keer per maand, en je
   weet het in plaats van dat je het hoopt.

Terugzetten voor het echie:

```bash
bash db/backup.sh --terugzetten backups/vakto-2026-08-23_0300.dump vakto
```

---

## Een firewall

Alleen 80 en 443 horen open te staan. Poort 8000 (de applicatie) en 5432
(PostgreSQL) horen alleen van de machine zelf bereikbaar te zijn.

```bash
sudo ufw default deny incoming
sudo ufw allow 22/tcp        # ssh — sluit jezelf niet buiten
sudo ufw allow 80,443/tcp
sudo ufw enable
```

En zet in `postgresql.conf` `listen_addresses = 'localhost'`. Een
PostgreSQL die van buiten bereikbaar is, is een kwestie van tijd.

---

## Wat je maandelijks nakijkt

Vijf minuten, en het is precies de lijst waar je spijt van krijgt als je
hem overslaat:

| | Hoe |
|---|---|
| Draait hij nog? | `systemctl status vakto` |
| Zijn er back-ups van vannacht? | `ls -lt backups/ \| head` |
| Kan er één terug? | `bash db/backup.sh --proef` |
| Wie probeert er in te loggen? | `SELECT * FROM event_log WHERE bron='inloggen' AND niveau='WARN' ORDER BY at DESC LIMIT 20;` |
| Werkt er nog iemand die weg is? | `SELECT * FROM v_gebruikers WHERE actief;` |
| Is er ruimte over? | `df -h` |

Die vierde regel is de moeite waard. Een reeks mislukte pogingen op een
naam die niet bestaat is het enige signaal dat je krijgt dat er iemand
aan het proberen is.

---

## Als er iets misgaat

**Het scherm doet niets.** `systemctl status vakto`. Staat er `failed`,
dan zegt `journalctl -u vakto -n 50` waarom.

**"could not connect to server".** PostgreSQL ligt eruit:
`systemctl status postgresql`.

**Iedereen is uitgelogd.** Dat kan niet door een herstart komen —
sessies staan in de database (R-GEB-05). Kijk of iemand `app_session`
heeft leeggegooid, of dat de klok van de server verkeerd staat.

**Iemand is zijn wachtwoord kwijt.** Een beheerder zet het opnieuw via
het gebruikersscherm. Is de énige beheerder zijn wachtwoord kwijt, dan
moet het met de hand:

```bash
python3 -c "from vakto.gebruikers import versleutel; print(versleutel('eennieuwlangwachtwoord'))"
psql -d vakto -c "UPDATE app_user SET wachtwoord='<plak de afdruk hier>' WHERE gebruikersnaam='dennis';"
```

Er is met opzet geen "wachtwoord vergeten"-knop met een mailtje: dat is
een tweede weg naar binnen, en die moet je onderhouden en beveiligen. In
een magazijn met vijftien mensen loopt de beheerder gewoon langs.

---

## Wat er níét in zit, en waarom

Eerlijk zijn over de grenzen is goedkoper dan er later achter komen.

* **Geen tweefactorauthenticatie.** Voor een systeem dat alleen binnen
  het bedrijfsnetwerk bereikbaar is, is dat verdedigbaar. Komt hij open
  te staan op het internet, dan is dit het eerste wat erbij moet.
* **Geen wachtwoordherstel per e-mail.** Zie hierboven.
* **Eén verbinding tegelijk naar de database.** Genoeg voor één magazijn
  met een handvol schermen. Loopt dat vast op drukte, dan is een
  verbindingspoel het vervangen van één functie in `web.py`
  (`Vaktoserver.verbinding`).
* **De scanstand staat in het geheugen van de server.** Bij een herstart
  begint iemand die middenin een scan zat opnieuw bij de eerste stap.
  De inlog zelf overleeft het wél, want die staat in de database.
