# OuderApp (Konnect) voor Home Assistant

**0.1.1 — testversie. Nog niet met een echt ouderaccount getest.**

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
- Tijdlijn met dagboektekst en foto's; nieuws en nieuwsbrieven als voorvertoning; overzicht van gesprekken en de laatste berichten uit één gekozen gesprek.

Er worden geen berichten verstuurd, opvangaanvragen gedaan of expliciete markeer-als-gelezen-aanroepen uitgevoerd. Of de leverancier een geopende GET-detailaanroep zelf als gelezen registreert, moet nog in de praktijk worden gecontroleerd.

## Handmatige installatie als alternatief

Vereist: Home Assistant Core **2026.8.3 of hoger**, met Python 3.14.2 of hoger binnen 3.14. Latere HA-versies zijn nog niet getest.

1. Maak een HA-back-up en gebruik voor de eerste proef bij voorkeur een testinstallatie.
2. Pak `ouderapp-0.1.1-candidate-install.zip` uit in de HA-configuratiemap. Controleer dat `custom_components/ouderapp/manifest.json` bestaat.
3. Herstart Home Assistant. Voeg bij **Instellingen → Apparaten en diensten → Integratie toevoegen** de integratie **OuderApp (Konnect)** toe.
4. Vul voor De Eerste Stap het portaal `deeerstestap` in en meld je aan met je ouderaccount. Vul het wachtwoord alleen in deze HA-flow in.
5. Open het nieuwe OuderApp-apparaat en controleer de tellers tegenover de officiële app. Klik op een teller om de inhoud te openen.

De frontendmodule wordt automatisch geregistreerd, ook voor de apparaatpop-ups. Bij een dashboard in YAML-modus voeg je zelf een module-resource toe met URL `/ouderapp/automation-card.js?v=0.1.1`. Een volledig hoofdloze HA-installatie kan de sensoren en beveiligde API gebruiken.

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

`kind` is `timeline`, `news`, `newsletters`, `conversations` of `messages`. Voor `messages` is `conversation` verplicht: de `conversation_id` uit `conversations`. Het antwoord bevat `items`, `returned`, `limit`, `updated_at`, `kind` en `stale`; foto's hebben afgeschermde identifiers, geen downloadadressen.

## Grenzen van deze versie

- Maximaal 20 items per aanvraag, eerste pagina/overzicht; geen volledig archief, kalender of BSO-planning.
- Alleen de geobserveerde tijdlijnsoorten dagboek en foto worden weergegeven. Actie- en toestemmingskaarten worden overgeslagen.
- Nieuws en nieuwsbrieven bevatten de samenvatting van het overzicht; volledige HTML-opmaak, documenten, enquêtes en video's worden niet weergegeven.
- Maximaal drie foto's per item en twaalf zichtbaar per kaart. Alleen ontvangen HTTPS-foto-URL's op `resource.kidskonnect.cloud` worden ondersteund. Andere mediahosts blijven dicht totdat hun echte gebruik is geverifieerd.
- Foto's worden begrensd gedownload, gecontroleerd en omgezet naar JPEG zonder oorspronkelijke metadata. Een verlopen of afwijkende foto verschijnt als niet beschikbaar.
- Inhoud is vijf minuten vers in de cache; bij een tijdelijke netwerkfout kan maximaal één uur oude inhoud met een melding terugkomen. Een authenticatiefout wist de inhoudscaches. Na verbindingsfouten wachten volgende aanvragen oplopend 30 seconden tot vijf minuten voordat ze opnieuw de leverancier benaderen.
- CAPTCHA, verplichte wachtwoordwijziging en afwijkende loginservers vragen afhandeling in het officiële portaal. Een andere gebruikersnaam kan een nieuwe koppeling vereisen.
- Login, langdurige tokenvernieuwing, echte velden, leesstatus, HACS-installatie en bediening in de echte HA-frontend wachten nog op de accountproef. Synthetische tests bewijzen die werking niet.

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
