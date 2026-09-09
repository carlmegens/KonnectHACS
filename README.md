<img src="custom_components/ouderapp/brand/icon.png" alt="OuderApp-logo" width="96" height="96">

# OuderApp (Konnect) voor Home Assistant

**0.5.0 — testversie. Aanmelden bij De Eerste Stap is door de gebruiker bevestigd; nieuwsdetails met foto’s en de planningactie moeten nog in de praktijk worden gecontroleerd.**

Voor Konnect/Ovivio-ouderportalen, met De Eerste Stap als eerste beoogde praktijkproef. De integratie volgt de openbare ouderwebapp. Zij is onofficieel en gebruikt geen browserprofiel of opgeslagen wachtwoord.

[![Open OuderApp in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=carlmegens&repository=KonnectHACS&category=integration)

Repository: [carlmegens/KonnectHACS](https://github.com/carlmegens/KonnectHACS).

## Installeren via HACS

Vereist: Home Assistant Core **2026.8.3 of hoger**, HACS en je OuderApp-account. Maak voor deze eerste testversie een HA-back-up.

1. Klik op **Open OuderApp in HACS** hierboven. Kies zo nodig het adres van je Home Assistant-installatie.
2. Voeg de repository toe en kies **Downloaden**. Handmatig toevoegen in HACS kan via **Aangepaste repositories**, adres `https://github.com/carlmegens/KonnectHACS`, type **Integratie**.
3. Herstart Home Assistant.
4. Ga naar **Instellingen → Apparaten en diensten → Integratie toevoegen**, zoek **OuderApp (Konnect)** en meld je aan. Voor De Eerste Stap vul je bij **Portaal** `deeerstestap` in.
5. Herlaad je browser en open het nieuwe **OuderApp-apparaat**. Klik op een teller om de tijdlijn, het nieuws of de gesprekken te openen.

De integratie en de bijbehorende kaart/pop-ups worden samen geïnstalleerd. Een apart dashboard is niet nodig. Deze aangepaste HACS-repository gebruikt de bestanden op `main`; opname in de standaardcatalogus is niet aangevraagd. Zie ook de [HACS-instructies voor aangepaste repositories](https://www.hacs.xyz/docs/faq/custom_repositories/).

## Wat is gebouwd?

- Aanmelden vanuit Home Assistant, sessievernieuwing, heraanmelden en meerdere accounts.
- Aantal actieve kinderen, ongelezen gesprekken en nieuwsitems, verbinding en laatste geslaagde synchronisatie. Ontbrekende aantallen blijven onbekend.
- Pop-ups vanaf de tellers: kinderen opent de tijdlijn, berichten opent gesprekken, nieuws opent nieuws.
- Intern paneel met tijdlijn, nieuws, nieuwsbrieven en gesprekken; teruglink naar het HA-apparaat.
- Optionele kaart met visuele instellingen, accountkeuze, gesprekskeuze, titel, aantallen en foto-optie. Nederlands en Engels, licht en donker, desktop en mobiel.
- Tijdlijn met dagboektekst en foto's; nieuws en nieuwsbrieven met tekst op aanvraag; overzicht van gesprekken en de laatste berichten uit één gekozen gesprek.

Klik op de titel van een nieuwsitem of nieuwsbrief om de tekst te laden. Alleen het gekozen item wordt opgehaald, nadat de integratie heeft gecontroleerd dat het in het overzicht van dit account en deze bron staat. De tekstweergave bevat geen externe embeds, video's of trackingafbeeldingen. Bij een ontbrekende ondersteunde detailverwijzing blijft de voorvertoning zichtbaar. Lange tekst wordt begrensd tot 20.000 tekens en als ingekort aangeduid.

Er worden geen berichten verstuurd, opvangaanvragen gedaan of expliciete markeer-als-gelezen-aanroepen uitgevoerd. Of de leverancier een geopende GET-detailaanroep zelf als gelezen registreert, moet nog in de praktijk worden gecontroleerd.

## Handmatige installatie als alternatief

Vereist: Home Assistant Core **2026.8.3 of hoger**, met Python 3.14.2 of hoger binnen 3.14. Latere HA-versies zijn nog niet getest.

1. Maak een HA-back-up en gebruik voor de eerste proef bij voorkeur een testinstallatie.
2. Pak `ouderapp-0.5.0-candidate-install.zip` uit in de HA-configuratiemap. Controleer dat `custom_components/ouderapp/manifest.json` bestaat.
3. Herstart Home Assistant. Voeg bij **Instellingen → Apparaten en diensten → Integratie toevoegen** de integratie **OuderApp (Konnect)** toe.
4. Vul voor De Eerste Stap het portaal `deeerstestap` in en meld je aan met je ouderaccount. Vul het wachtwoord alleen in deze HA-flow in.
5. Open het nieuwe OuderApp-apparaat en controleer de tellers tegenover de officiële app. Klik op een teller om de inhoud te openen.

De frontendmodule wordt automatisch geregistreerd, ook voor de apparaatpop-ups. Bij een dashboard in YAML-modus voeg je zelf een module-resource toe met URL `/ouderapp/automation-card.js?v=0.5.0`. Een volledig hoofdloze HA-installatie kan de sensoren en beveiligde API gebruiken.

Terugrollen: verwijder de OuderApp-koppeling bij Apparaten en diensten, verwijder vervolgens uitsluitend `custom_components/ouderapp` en herstart HA. Verwijder een eventueel achtergebleven dashboardresource voor `/ouderapp/automation-card.js`. Andere integraties hoeven niet te worden gewijzigd.

## Toegang voor gezinsleden

Beheerders hebben standaard toegang. Geef andere actieve HA-gebruikers per gekoppeld account toegang via **Configureren**:

- **Lezers tijdlijn en nieuws:** tijdlijn, foto's, nieuws en nieuwsbrieven.
- **Lezers gesprekken:** gesprekslijst, berichten en gespreksfoto's.

Deze rechten zijn onafhankelijk. Ook bestaande verbindingen worden bij iedere leesaanvraag opnieuw gecontroleerd. Inhoud staat uitsluitend in afgeschermde geheugencaches en de geopende kaart, niet in sensorattributes of diagnostiek. De sensoren bevatten alleen tellers, tijdstempels en de verwijzing naar het juiste account/scherm.

Home Assistant bewaart de noodzakelijke sessietokens in de config entry. HA-back-ups kunnen die tokens bevatten. Het oorspronkelijke wachtwoord en providercookies worden niet opgeslagen.

## Optionele dashboardkaart

De kaart verschijnt als **OuderApp** in de kaartkiezer. Kies het account en de bron in de visuele instellingen. YAML kan ook:

```yaml
type: custom:ouderapp-card
config_entry_id: VUL_HET_ACCOUNT_ID_IN
source: timeline  # timeline, news, newsletters of messages
limit: 10
show_images: true
```

Bij `source: messages` kies je het gesprek in de kaart. De optionele `chatroom_id` legt één gesprek vast; gebruik de `conversation_id` uit het gespreksantwoord. Deze naam is een kaartinstelling en geen Konnect-endpoint.

## Leesactie voor automatiseringen

`ouderapp.get_content` retourneert een begrensd antwoord. Alleen beheerders en vertrouwde HA-automatiseringen mogen deze actie gebruiken. Inhoud die je zelf in automatiseringen opslaat, kan in HA-traces of meldingen terechtkomen.

```yaml
action: ouderapp.get_content
data:
  config_entry_id: VUL_HET_ACCOUNT_ID_IN
  kind: timeline
  limit: 10
response_variable: ouderapp_result
```

`kind` is `timeline`, `news`, `newsletters`, `conversations` of `messages`. Voor `messages` is `conversation` verplicht: de `conversation_id` uit `conversations`. Ook de server controleert voor een nieuwe detaillezing of dit gesprek in het begrensde overzicht van hetzelfde account voorkomt. Het antwoord bevat `items`, `returned`, `limit`, `updated_at`, `kind` en `stale`; foto's hebben afgeschermde identifiers, geen downloadadressen.

Voor één nieuwsitem of nieuwsbrief geef je daarnaast `article` mee: gebruik daarvoor de `article_id` uit hetzelfde account en dezelfde bron (`news` of `newsletters`). Het antwoord heeft `detail: true` en één item met gewone tekst; `truncated` geeft aan of de tekst is ingekort. Nieuwsdetails kunnen daarnaast maximaal drie foto’s bevatten. Die verschijnen bij uitklappen en worden via de beveiligde HA-fotoroute geladen; de optie **Foto’s tonen** geldt ook hier. Alleen expliciete foto-elementen uit de ondersteunde nieuwsindelingen worden gebruikt.

## Planning bekijken en downloaden

Open **OuderApp** via het apparaat en kies als Home Assistant-beheerder de tab **Opvangplanning**. Kies een begin- en einddatum en druk op **Planning ophalen**. De einddatum telt niet mee; maximaal 31 dagen en 100 opvangmomenten. De lijst gebruikt Nederlandse datums en tijden en vermeldt **Voorlopig**, **Afwezig** of **Status onbekend**, met de eventuele noodzaak om in OuderApp te bevestigen.

Met **Kalender downloaden** haal je een verse momentopname als `.ics`-bestand op. De knop is niet beschikbaar bij lege, afgekorte of offline planning. Gebruik voor import een aparte vervangbare kalender: latere wijzigingen worden niet automatisch verwerkt. Dit is geen kalenderabonnement en wijzigt geen opvangboekingen. Wisselen van account, periode of tab wist de eerdere planning; verborgen of gesloten weergaven bewaren geen late antwoorden. Er wordt alleen na een klik opgehaald, zonder automatisch verversen.

De tab is alleen voor beheerders zichtbaar; de server controleert die rechten ook bij iedere aanvraag. Planning komt niet in statusentiteiten of diagnostiek terecht. Na downloaden valt het bestand buiten de HA-toegangscontrole. De paneelwerking is synthetisch getest; een live controle in de eigen HA en eventuele mobiele downloadafhandeling blijft nodig.

## Opvangplanning lezen

De actie `ouderapp.get_planning` leest opvangmomenten voor één account. Kies een begindatum en een **exclusieve einddatum**, maximaal 31 dagen later. Datums gelden in **Europe/Amsterdam**; zomer- en wintertijd worden meegenomen. Alleen beheerders en vertrouwde automatiseringen mogen deze actie uitvoeren. Kindnamen en planning komen niet in de gewone sensoren of diagnostiek; bewaar antwoorden en eventuele automatiseringstraces privé.

```yaml
action: ouderapp.get_planning
data:
  config_entry_id: VUL_HET_ACCOUNT_ID_IN
  start_date: "2026-09-09"
  end_date: "2026-09-16"
  limit: 50
response_variable: opvangplanning
```

Dit voorbeeld leest de periode van 9 september tot aan 16 september. Het antwoord bevat `events`, `returned`, `limit`, `truncated`, de datums en `time_zone`. De selectie bestaat uit opvangmomenten die de periode overlappen. Elk moment heeft `id`, `child`, `start`, `end`, `status` en `confirmation_required`. De begin- en eindtijd hebben een tijdzone-offset; een gebeurtenis die de periodegrens kruist wordt niet afgeknipt.

- Maximaal 100 momenten, standaard 50, chronologisch gesorteerd. `truncated: true` betekent dat meer momenten buiten de antwoordlimiet vallen.
- `status` is `absent`, `tentative` of `unknown`. Een onbekende providerstatus wordt nadrukkelijk niet als bevestigde opvang geïnterpreteerd. `confirmation_required` is waar/onwaar als de bron dit geeft, anders onbekend (`null`).
- `data_connector_offline: true` betekent dat de leverancier waarschuwt voor mogelijk onjuiste of verouderde planning. Gebruik die gegevens niet als definitieve bevestiging.
- Identifiers blijven gelijk voor hetzelfde ongewijzigde tijdslot van hetzelfde kind/account. Een verschoven begin- of eindtijd krijgt een andere identifier; er is nog geen stabiele provider-ID voor verplaatsingen aangetoond.
- Deze actie doet per aanvraag een begrensde nieuwe lezing; geen terugval op een oude planningcache. Plan aanvragen met een redelijk interval, bijvoorbeeld hetzelfde halfuur als de tellers.
- Alleen opvangtijdsloten worden geprojecteerd. Activiteiten, oudergesprekken, contracten en aanvragen vallen buiten deze actie. Er worden geen afspraken of opvangboekingen gewijzigd. Een kalenderentiteit of abonnement is nog niet meegeleverd. Een ICS-momentopname is beschikbaar zoals hieronder beschreven.

## Kalenderexport voor automatiseringen

Geef dezelfde actie `format: ics` mee om naast de planning ook een kalendertekst terug te krijgen:

```yaml
action: ouderapp.get_planning
data:
  config_entry_id: VUL_HET_ACCOUNT_ID_IN
  start_date: "2026-09-09"
  end_date: "2026-09-16"
  limit: 100
  format: ics
response_variable: opvangplanning
```

Het antwoord bevat extra `calendar` (de ICS-tekst), `filename` en `content_type`. Een eigen automatisering kan de waarde `opvangplanning.calendar` gebruiken om een UTF-8-bestand met de opgegeven `.ics`-naam te bewaren. Deze actie schrijft zelf geen bestand. Voor handmatig gebruik biedt het OuderApp-paneel de knop **Kalender downloaden**. Gebruik de gedecodeerde tekstwaarde, niet het volledige JSON-antwoord of een letterlijk gekopieerde string met `\r\n`-escapes. Zonder `format` blijft het bestaande JSON-antwoord behouden.

De export is een **momentopname**, zonder automatische synchronisatie. Importeer deze in een aparte kalender die je bij een volgende import vervangt: verplaatste of verwijderde opvangmomenten worden niet automatisch uit eerdere imports verwijderd, en kalenderapps kunnen bij herhaalde import duplicaten maken. Identifiers zijn stabiel voor ongewijzigde tijdsloten, ook als alleen de status verandert.

Titels vermelden altijd **Voorlopig**, **Afwezig** of **Status onbekend**, plus de beschikbare kindnaam. De momenten blokkeren geen beschikbaarheid in je agenda. De omschrijving vermeldt wanneer volgens de bron bevestiging nodig is. Tijden worden als UTC opgeslagen zodat kalenderapps de juiste lokale tijd kunnen tonen, ook bij zomer-/wintertijd. De export gebruikt [iCalendar (RFC 5545)](https://www.rfc-editor.org/rfc/rfc5545.html).

Een lege of afgekorte selectie en een offlinewaarschuwing leveren bij ICS een duidelijke fout op; JSON blijft die toestand wel teruggeven. Kies bij afkappen een kortere periode of een hogere limiet (maximaal 100). Bewaar of deel het bestand bewust: het bevat kindnamen en planning, en de HA-toegangscontrole geldt niet meer voor een eenmaal gekopieerd bestand.

Berichtdatums ondersteunen ISO-tekst en gehele milliseconden sinds de Unix-epoch, overeenkomstig de officiële datumverwerking. Een datum zonder tijd blijft dezelfde kalenderdag; tijdstippen worden in de browsertijdzone getoond. Ongeldige datums blijven zonder label.

## Grenzen van deze versie

- Inhoudsoverzichten: maximaal 20 items per aanvraag, eerste pagina; geen volledig archief. De aparte planningactie leest maximaal 31 dagen/100 opvangmomenten. Een kalenderabonnements-URL zoals bij Parro is niet aangetoond; het paneel biedt een planninglijst en ICS-download voor beheerders, zonder kalenderentiteit.
- Alleen de geobserveerde tijdlijnsoorten dagboek en foto worden weergegeven. Actie- en toestemmingskaarten worden overgeslagen.
- Nieuws en nieuwsbrieven tonen eerst een samenvatting; uitklappen leest de beschikbare tekst. Nieuwsdetails tonen maximaal drie ondersteunde foto-elementen. Volledige HTML-opmaak, documenten, enquêtes, video's, afbeeldingen uit vrije HTML en nieuwsbriefafbeeldingen worden niet weergegeven.
- Maximaal drie foto's per item en twaalf zichtbaar per kaart. Alleen ontvangen HTTPS-foto-URL's op `resource.kidskonnect.cloud` worden ondersteund. Andere mediahosts blijven dicht totdat hun echte gebruik is geverifieerd.
- Foto's worden begrensd gedownload, gecontroleerd en omgezet naar JPEG zonder oorspronkelijke metadata. Een verlopen of afwijkende foto verschijnt als niet beschikbaar.
- Inhoud is vijf minuten vers in de cache; bij een tijdelijke netwerkfout kan maximaal één uur oude inhoud met een melding terugkomen. Een authenticatiefout wist de inhoudscaches. Na verbindingsfouten wachten volgende aanvragen oplopend 30 seconden tot vijf minuten voordat ze opnieuw de leverancier benaderen.
- CAPTCHA, verplichte wachtwoordwijziging en afwijkende loginservers vragen afhandeling in het officiële portaal. Een andere gebruikersnaam kan een nieuwe koppeling vereisen.
- Aanmelden bij De Eerste Stap is door de gebruiker bevestigd na 0.1.3. Langdurige tokenvernieuwing, iedere inhoudsbron, foto's, leesstatus en bediening met een tweede HA-gebruiker moeten nog afzonderlijk in de praktijk worden gecontroleerd. Synthetische tests vervangen die controles niet.

## Ontwikkelen

Vanuit de ontwikkelmap, met Python 3.14:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests scripts
.venv/bin/ruff format --check custom_components tests scripts
.venv/bin/python scripts/prepare_repository.py
```

De browsertests in `tests/frontend` gebruiken Playwright en uitsluitend verzonnen gegevens. De productiekaart heeft geen Node-afhankelijkheid. `scripts/prepare_repository.py` maakt reproduceerbare installatie- en repositoryarchieven met SHA-256-inventaris; het publiceert niets. Testbestanden en interne voortgangsverslagen worden niet in het installatiepakket opgenomen.

## Ontwikkelen en controleren

GitHub voert bij een push naar `main` en bij pull requests de Home Assistant-tests, codecontrole, pakketopbouw en synthetische Chromium-proeven uit. De workflow gebruikt alleen leesrechten en geen ouderaccount of productie-HA. De integratieversie blijft 0.5.0; deze wijziging betreft de ontwikkelcontroles.

Lokaal: gebruik Python 3.14 met `requirements-test.txt`, voer `python -m pytest --tb=short` uit en bouw pakketten met `python scripts/prepare_repository.py`. De browserproeven staan beschreven in `tests/frontend/README.md`. Action-commits en de npm-lockfile zijn vastgelegd; de Python-testplugin legt onder meer de geteste HA-versie vast. Transitive Python-afhankelijkheden met een versie-interval zijn niet volledig vergrendeld.
