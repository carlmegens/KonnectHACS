# Wijzigingen

## 0.5.6 — planning met tekstidentificaties herstellen

De planning accepteert nu begrensde tekstidentificaties voor kinderen, naast positieve numerieke identifiers. Voorheen werd de validator voor gespreksnummers hergebruikt; daardoor kon een geldig planningantwoord falen met `planning.child`. De fix is vóór deze release gericht in Home Assistant toegepast en het ophalen van JSON-planning is daar bevestigd.

Bestaande numerieke gebeurtenisidentiteit blijft behouden. Kindidentificaties worden alleen lokaal gehasht, blijven accountgebonden en komen niet in het antwoord of provideradressen terecht. Planningsfouten geven uitsluitend begrensde diagnosecodes; ruwe exceptiongegevens blijven verborgen. De integratie presenteert de slots als Opvang, zonder BSO-classificatie uit tijden of aanwezigheidsstatus af te leiden.

## 0.5.5 — dubbele tijdlijnfoto’s weglaten

Losse foto’s die al bij een dagboekbericht in de opgehaalde selectie staan, worden op bron-ID ontdubbeld. Een volledig dubbele fotokaart verdwijnt; overige foto’s blijven staan. Dit volgt de filtering in de officiële app, begrensd tot foto’s die de integratie ondersteunt en de eerste drie foto-posities per dagboek.

Foto’s zonder bruikbare ID of met een niet-ondersteunde dagboekvariant worden niet op basis van een gok verwijderd. De oorspronkelijke bronlijsten blijven ongewijzigd en er komen geen extra aanvragen bij. De actuele officiële tijdlijnrenderer kent journal, photo en trigger; de fotoboekactiekaart blijft buiten deze leesintegratie.

## 0.5.4 — gerichte diagnose bij inhoudsfouten

Kaart en nieuwsdetails tonen bij een niet-ondersteund antwoord een korte diagnosecode met kaartversie. Die onderscheidt onder meer een afwijkend antwoordformaat, ongeldige JSON en onverwachte lokale verwerking. De melding wordt gewist bij opnieuw laden, accountwissel en geslaagd herstel.

Alleen vaste toegestane codes worden weergegeven; ruwe foutberichten, accountwaarden en providerinhoud worden niet gebruikt. Onbekende waarden krijgen een algemene code. Bestaande aanmeld-, toegangs- en verbindingsmeldingen blijven behouden. Dit verbetert onderzoek van een volgende praktijkmelding en claimt geen nieuwe oorzaak of oplossing voor de eerdere screenshot.

## 0.5.3 — bijlagen herkennen

Dagboekberichten en berichten in een gekozen gesprek tonen nu maximaal vijf bestandsnamen uit de officiële bijlagenlijst. De namen verschijnen bij uitklappen, met een verwijzing naar OuderApp om de bestanden te bekijken. Berichten met alleen een bijlage zijn daardoor herkenbaar.

Alleen gewone tekstnamen worden doorgegeven; downloadadressen, bestandstypen en overige brongegevens blijven buiten het antwoord. De bestaande bronrechten, accountwissels en verborgen-kaartafhandeling gelden ook voor deze vermelding. Er wordt geen bijlage opgehaald en geen downloadknop gesuggereerd. Het transport gebruikt volgens de officiële app awsUrl, maar een ondersteunde vaste bestandshost is nog niet aangetoond.

## 0.5.2 — dagritme in het dagboek

Dagboekkaarten tonen nu ook de door de opvang aangeleverde dagritmetekst, vóór de dagboektekst, zoals in de officiële app. Een kaart met alleen dagritme blijft daardoor niet langer zonder tekst. Beide velden worden afzonderlijk naar gewone tekst omgezet; afwijkende HTML in het ene veld verbergt het andere niet. De gezamenlijke tekst blijft begrensd op 20.000 tekens.

Geen extra aanvragen of opslag in sensoren. Nieuwsbriefmedia blijven ongewijzigd: de onderzochte officiële renderer biedt een HTML-document, zonder aangetoonde afzonderlijke mediavelden. Dagritme is met synthetische gegevens getest; echte opvanginhoud blijft nog te controleren.

## 0.5.1 — geplande opvang herkennen

De officiële planningstatus `attend` wordt nu behouden en als **Gepland** getoond in het paneel en de kalenderexport. Deze code en de Nederlandse vertaling zijn bevestigd in de openbare officiële app. Eerdere versies toonden hiervoor Status onbekend.

Gepland is geen bewijs van fysieke aanwezigheid of afgehandelde bevestiging. `confirmation_required` blijft onafhankelijk zichtbaar; de export verzint geen CONFIRMED-status. Ongewijzigde tijdsloten behouden dezelfde identifier bij statuswissels. Nieuwe of onbekende codes blijven Status onbekend.

De installatiehulp beschrijft nu ook de situatie waarin de nieuwsteller werkt maar de berichten niet laden. De bestaande correctie uit 0.2.2 is extra gecontroleerd via de volledige route van het officiële nieuwsantwoord naar het Home Assistant-nieuwsoverzicht.

## 0.5.0 — planning in het OuderApp-paneel

Nieuwe beheerdertab **Opvangplanning** met datumkeuze, een lijst per dag, expliciet ophalen en ICS-download. De tab gebruikt de bestaande native Home Assistant-beheerderactie. Standaard wordt een week gekozen; datumgrenzen, Nederlandse tijdzone, opvangstatussen en bronwaarschuwingen blijven behouden.

Downloaden haalt een verse momentopname op. Lege, afgekorte of offline planning kan niet worden gedownload. Wisselen van periode/account/tab, intrekken van beheerderrechten of verbergen/sluiten wist privédata en verwerpt late antwoorden; download-URL’s worden opgeruimd. Geen automatische verversing, kalenderimport, abonnement of opvangwijziging. Browserproeven gebruiken synthetische gegevens; echte planning en mobiele HA-downloadafhandeling moeten nog in de praktijk worden gecontroleerd.

## 0.4.1 — berichtdatums behouden

Getalsdatums in milliseconden worden nu als gecontroleerde ISO-tijdstippen doorgegeven voor tijdlijn, nieuws, nieuwsbrieven en gesprekken. Die datums verdwenen eerder doordat alleen tekst werd geaccepteerd. ISO-datums en tijdstippen blijven ondersteund; ongeldige of buitenbereikwaarden leveren geen datumlabel op.

Een datum zonder tijd blijft dezelfde kalenderdag in iedere browsertijdzone en krijgt geen verzonnen tijdstip. Tijdstippen met een offset worden naar UTC genormaliseerd en in de lokale browsertijd weergegeven. Een ISO-tijdstip zonder offset behoudt de lokale betekenis; er wordt geen serverzone aangenomen. Het contract is gebaseerd op de officiële Date/DayJs-verwerking en met synthetische data gecontroleerd.

## 0.4.0 — foto’s in nieuwsdetails

Uitklappen van een nieuwsbericht toont naast tekst maximaal drie ondersteunde foto-elementen uit de officiële nieuwsindelingen. De bestaande gescheiden rechten, afgeschermde fotoverwijzingen, hostcontrole en afbeeldingsverwerking gelden ook voor deze foto’s. Video-elementen, afgeschermde portretten, onbekende indelingen en niet-ondersteunde hosts worden overgeslagen. Nieuwsbrieven en vrije HTML-afbeeldingen blijven tekstweergave.

Foto’s laden pas wanneer ze zichtbaar zijn. Inklappen verwijdert hun browser-URL’s; late fotodownloads voor verborgen elementen worden weggegooid. De optie Foto’s tonen en de totale limiet van twaalf zichtbare foto’s blijven gelden. Het broncontract is gecontroleerd in de openbare officiële app; echte nieuwsfoto’s zijn nog niet in de gebruikers-HA getest.

## 0.3.1 — kalenderexport voor automatiseringen

De beheerderactie `ouderapp.get_planning` ondersteunt `format: ics`. Het antwoord bevat naast de bestaande velden een begrensde kalendertekst, bestandsnaam en inhoudstype. Standaard blijft de actie JSON teruggeven. Geen bestand wordt automatisch opgeslagen; geen abonnements-URL of downloadroute toegevoegd.

UTC-tijden, UTF-8-regelvouwen en tekstescaping worden met een onafhankelijke kalenderparser gecontroleerd. Titels behouden voorlopige, afwezige of onbekende status en de beschikbare kindnaam; er wordt geen bevestiging of annulering aangenomen. De momenten blokkeren geen beschikbaarheid. Lege/afgekorte selecties en offlinewaarschuwingen leveren bij export een duidelijke fout op.

De export is een momentopname. Herhaalde import kan duplicaten geven en verplaatste/verwijderde momenten ruimen eerdere imports niet op; gebruik een vervangbare aparte kalender. Toegangscontrole is gelijk aan JSON, inclusief hercontrole na het ophalen. Synthetisch getest; nog geen praktijkbewijs met een ouderaccount of kalenderapp.

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
