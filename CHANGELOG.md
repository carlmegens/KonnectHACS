# Wijzigingen

## 0.1.1 — aanmeldcompatibiliteit en diagnose

Antwoorden met een `result`/`payload`-envelop mogen extra metadatavelden bevatten. De identiteit en sessietokens blijven strikt gevalideerd. Afgewezen aanmeldingen in een HTTP 200-antwoord krijgen de juiste aanmeldfout.

De configuratieflow toont bij een afwijkend antwoord een begrensde diagnosecode voor de precieze stap, zoals `login.missing_refresh_token` of `identity.http_status_404`. Log en melding bevatten geen providerwaarden, wachtwoord, tokens of accountgegevens. De oorzaak van de eerste praktijkmelding is nog niet vastgesteld; deze update maakt die gericht vast te stellen.

## 0.1.0 — lokale kandidaat, 9 september 2026

Eerste OuderApp/Konnect-integratie met native HA-aanmelding, sessievernieuwing, accountgebonden sensoren, inhoud op aanvraag, onafhankelijke leesrechten, beveiligde foto's, tellerpop-ups, intern paneel en optionele kaart.

Lokale HA- en Chromium-tests gebruiken uitsluitend synthetische gegevens. Geen live ouderaccount, productie-installatie of publicatie uitgevoerd. Nieuws/nieuwsbrieven zijn voorvertoningen; kalender/planning, video en documenten vallen buiten deze kandidaat.
