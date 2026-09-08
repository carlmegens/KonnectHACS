# Wijzigingen

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
