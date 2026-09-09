# Wijzigingen

## 0.3.0 — begrensde opvangplanning lezen

Nieuwe beheerderactie `ouderapp.get_planning` voor een expliciete periode van maximaal 31 dagen, met maximaal 100 chronologisch gesorteerde opvangmomenten. De einddatum is exclusief; datums gelden in Europe/Amsterdam. Tijdzone-overgangen, periodegrenzen, lege lijsten en ongeldige brondata worden gecontroleerd.

Afwezige en voorlopige momenten behouden die status; andere statussen blijven onbekend totdat hun betekenis is aangetoond. De providerwaarschuwing over een offline planningskoppeling wordt als booleaanse vlag behouden, zonder ruwe providerberichten door te geven. Kindnamen en planning blijven buiten statusentiteiten en diagnostiek. Toegang en geladen account worden ook na de aanvraag gecontroleerd.

De actie leest uitsluitend opvangtijdsloten. Geen boekingswijzigingen, activiteiten, oudergesprekken, kalenderabonnements-URL of kalenderentiteit. Identifiers blijven stabiel voor ongewijzigde tijdslots; rescheduling heeft nog geen bewezen provideridentiteit. Getest met synthetische data, nog niet met echte planning.

## 0.2.2 — nieuwsoverzicht laden

Het nieuwsoverzicht verwerkt nu de officiële `payload.newsItems`-antwoordvorm. Eerdere versies verwachtten hier een losse lijst en konden daardoor “Berichten konden niet worden geladen” tonen terwijl de nieuwsteller wel werkte. De correctie geldt ook voor de lijstcontrole bij het openen van een nieuwsdetail. Een geldige lege lijst blijft leeg; afwijkende antwoorden blijven herkenbaar als fout.

## 0.2.1 — gespreksselectie op de server controleren

De server controleert vóór het ophalen van een nieuw gespreksdetail of de gekozen verwijzing voorkomt in het begrensde gespreksoverzicht van hetzelfde account. Deze controle geldt ook voor directe WebSocket-, HTTP- en automatiseringsaanvragen; de kaart controleerde de selectie al. Onbekende of verdwenen verwijzingen bereiken de detailroute niet.

## 0.2.0 — nieuws en nieuwsbrieven openen

Titels in de nieuws- en nieuwsbriefweergave halen bij uitklappen de tekst op. De server controleert eerst of de detailverwijzing in het begrensde overzicht van hetzelfde account en dezelfde bron staat. Details gebruiken de bestaande toegangsrechten, cachelimieten en sessieafhandeling. Bij accountwissel, verborgen kaart of ingetrokken toegang worden oude of late antwoorden niet getoond.

Nieuws gebruikt de actuele HTML-inhoudscontainer; nieuwsbrieven gebruiken de gegenereerde nieuwsbrief. Alleen gewone tekst wordt getoond, maximaal 20.000 tekens, met aanduiding bij inkorten. Geen externe embeds, trackingafbeeldingen, expliciete leesmarkeringen of provider-schrijfhandelingen. Detailfouten kunnen opnieuw worden geprobeerd.

De gebruiker bevestigde dat aanmelden werkt na versie 0.1.3. De nieuwe detailweergave is met synthetische HA- en browserproeven gecontroleerd; een live controle per inhoudsbron blijft open.

## 0.1.3 — clientherkenning bij aanmelden

API-aanroepen sturen nu `X-Client-Name: OuderApp` en de protocolversie `3.64.1` mee, overeenkomstig de HTTP-interceptor van de onderzochte officiële app. Deze headers ontbraken bij aanmelden en sessievernieuwing. De integratie blijft via haar User-Agent herkenbaar als Home Assistant.

Dit corrigeert een aangetoonde afwijking van het appcontract na de melding `login.missing_refresh_token`. Of dit de aanmeldfout bij De Eerste Stap oplost, moet de volgende praktijkproef bevestigen. Een ontbrekend vernieuwingstoken blijft een fout; er wordt geen wachtwoord opgeslagen als vervanging.

## 0.1.2 — OuderApp-logo

Het aangeleverde OuderApp-logo wordt meegeleverd als lokaal integratie-icoon voor Home Assistant en staat bovenaan de README. De oorspronkelijke afbeelding is ongewijzigd overgenomen.

## 0.1.1 — aanmeldcompatibiliteit en diagnose

Antwoorden met een `result`/`payload`-envelop mogen extra metadatavelden bevatten. De identiteit en sessietokens blijven strikt gevalideerd. Afgewezen aanmeldingen in een HTTP 200-antwoord krijgen de juiste aanmeldfout.

De configuratieflow toont bij een afwijkend antwoord een begrensde diagnosecode voor de precieze stap, zoals `login.missing_refresh_token` of `identity.http_status_404`. Log en melding bevatten geen providerwaarden, wachtwoord, tokens of accountgegevens. De oorzaak van de eerste praktijkmelding is nog niet vastgesteld; deze update maakt die gericht vast te stellen.

## 0.1.0 — lokale kandidaat, 9 september 2026

Eerste OuderApp/Konnect-integratie met native HA-aanmelding, sessievernieuwing, accountgebonden sensoren, inhoud op aanvraag, onafhankelijke leesrechten, beveiligde foto's, tellerpop-ups, intern paneel en optionele kaart.

Lokale HA- en Chromium-tests gebruiken uitsluitend synthetische gegevens. Geen live ouderaccount, productie-installatie of publicatie uitgevoerd. Nieuws/nieuwsbrieven zijn voorvertoningen; kalender/planning, video en documenten vallen buiten deze kandidaat.
