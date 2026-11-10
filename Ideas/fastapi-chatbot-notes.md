# FastAPI chatbot – poznámky k POC

## Cíl

Připravit malý proof of concept (POC) pro prohlížení historických výsledků TTTS a jednoduché dotazování v chatovacím panelu. První verze má ověřit uživatelské rozhraní, datový model, API a seedování dat. Zatím nebude používat LLM ani placené modelové API, takže nebude potřeba API klíč.

## Současný stav TTTS

Současná aplikace je React + Vite frontend a ASP.NET Core Web API. Web je hostovaný přes Firebase Hosting, API podle konfigurace repozitáře běží na Google Cloud Run a používá Firestore pro živé skóre. Lokální vývoj .NET API používá seedovaná data v paměti.

Živé skóre a historické výsledky jsou odlišné oblasti:

- **Živé skóre:** zůstane v současném .NET API a Firestore.
- **Historické výsledky:** nová read-only část se seedovanou SQLite databází. Pro cloudový POC bude databázový soubor připraven při sestavení image FastAPI a nasazen společně s aplikací na Cloud Run; samostatná Cloud SQL instance nebude potřeba.
- **Chat:** v první verzi zavolá deterministickou aplikační logiku nad historickými daty. Později lze k této službě přidat LLM.

Současný model `LiveMatch` reprezentuje aktuální stav rozehraných zápasů, proto není vhodné do něj přidávat archivní výsledky.

## Návrh UI

Vedle sekce nebo stránky **„Probíhá“** přidat odkaz **„Historické výsledky“**, který otevře například `/history`.

Stránka historických výsledků bude mít tři hlavní oblasti:

```text
┌────────────────────┬─────────────────────────────┬─────────────────────┐
│ Roky               │ Historické výsledky         │ Chat                │
│ 2026               │ Hledat hráče                │ Zeptejte se na      │
│ 2025               │ Turnaj [všechny ▾]          │ historické zápasy…  │
│ 2024               │ Hráč [vyberte ▾]            │                     │
│ …                  │ Soupeř [vyberte ▾]          │ zprávy              │
│                    │ seznam zápasů a výsledků    │ vstup + Odeslat     │
└────────────────────┴─────────────────────────────┴─────────────────────┘
```

- Levý sloupec zobrazí dostupné roky. Výběr roku omezí turnaje a zápasy.
- Hlavní sloupec zobrazí hledání hráče, výběr turnaje, hráče a soupeře a seznam odpovídajících zápasů.
- Pravý sloupec bude chatovací okno. Dotaz může využít aktuálně vybraný rok, turnaj nebo hráče jako kontext.
- Na menších obrazovkách lze chat zobrazit jako vysouvací panel nebo samostatnou záložku.
- Rozhraní má zobrazovat načítání, prázdné výsledky, chyby API a možnost vymazat filtry.

Případné další filtry, například město nebo fáze turnaje, lze přidat až podle potřeb dat.

## Datový model

Pro POC stačí hráči, turnaje, zápasy a sety. Samostatnou tabulku „výsledky“ navíc není nutné vytvářet: dokončený zápas s vítězem a sety sám reprezentuje výsledek.

### `players`

- `id`
- `first_name`
- `last_name`
- `birth_year`
- `club` (pro POC může představovat aktuální oddíl)

### `tournaments`

- `id`
- `name`
- `city`
- `date_from`
- `date_to`

Jeden záznam bude představovat konkrétní konání turnaje, tedy i ročník.

### `matches`

- `id`
- `tournament_id`
- `played_at`
- `player1_id`
- `player2_id`
- `winner_id`
- `round` (například skupina, čtvrtfinále, semifinále nebo finále)

### `match_sets`

- `id`
- `match_id`
- `set_number`
- `player1_score`
- `player2_score`

Celkové skóre zápasu (například 3:2) lze odvodit z vyhraných setů a není nutné je při POC ukládat duplicitně. Databázová omezení mají zajistit, že číslo setu je v rámci zápasu unikátní a že `winner_id` odpovídá jednomu ze dvou hráčů zápasu.

### Historie oddílu hráče

Oddíl se může v čase změnit. Pokud je důležité zobrazit oddíl platný v době turnaje, samotné `club` v tabulce `players` nestačí. Pro POC lze uložit současný oddíl; při potřebě historické přesnosti se doplní vazební tabulka s časovou platností nebo údaj o oddílu při účasti hráče v turnaji.

## API a backend

Historická data obsluhuje samostatná FastAPI služba s SQLAlchemy, nezávisle na současném .NET API. FastAPI vlastní historickou SQLite databázi a pro první verzi nabízí pouze čtecí operace. Lokálně i v Cloud Run používá stejný databázový formát a seedovaná data.

Návrh endpointů:

- `GET /api/history/years` — dostupné roky
- `GET /api/history/tournaments?year=2025` — turnaje v daném roce
- `GET /api/history/players?search=Jan` — hledání hráčů pro vyhledávání a dropdown
- `GET /api/history/matches?year=2025&tournament_id=...&player_id=...&opponent_id=...` — filtrovaný seznam zápasů
- `GET /api/history/players/{id}/matches?year=2025` — zápasy konkrétního hráče
- `POST /api/history/chat` — jednoduchý chatový dotaz nad historickými daty

Endpoint chatu může v POC přijmout text dotazu a volitelný kontext filtrů. Odpověď sestaví z dat získaných přes stejné aplikační/query funkce jako běžné API; chatbot nemá zapisovat ani měnit výsledky.

Pro lokální vývoj lze Vite nakonfigurovat tak, aby například `/api/history` přesměrovával na FastAPI. Tím se zachová stávající `/api` pro .NET API a frontend se vyhne přímé konfiguraci různých lokálních adres a CORS.

## Chat bez API klíče (první fáze)

První chat nebude volný LLM chatbot. FastAPI rozpozná podporovaný typ dotazu, například:

> „Jaké zápasy odehrál Jan Novák?“

Backend vyhledá hráče, načte jeho zápasy a vytvoří odpověď z šablony. Při nenalezeném nebo nejednoznačném jméně požádá o upřesnění. SQLAlchemy použije parametrizované databázové dotazy; žádné dotazy ani Python kód generované modelem se nebudou spouštět.

Tento postup ověří UI, dotazovací API a strukturu dat bez nákladů na model. V první fázi je přesnější označovat funkci jako **vyhledávání nad výsledky** než jako plnohodnotného AI chatbota.

Později lze nad stejnými read-only aplikačními funkcemi přidat LLM. Model by vybíral vhodný nástroj a formuloval odpověď, zatímco přesné SQL dotazy a výpočty zůstanou v backendu.

## Databáze, seed a prostředí

- **Databáze POC:** SQLite se SQLAlchemy. Historická data jsou pro tuto ukázku neměnná; uživatelské dotazy pouze čtou data.
- **Seed:** připraví předvídatelné hráče, turnaje, zápasy a sety. Seed se spustí při sestavení image (ne při každém startu instance) a výsledný SQLite soubor se přibalí do image FastAPI.
- **Lokální vývoj a testy:** lokálně lze databázi vytvořit ze stejného opakovatelného seed skriptu. Databázový soubor se negeneruje ručně ani se neudržuje jako samostatný produkční zdroj pravdy; zdrojem seed dat je verzovaný kód.
- **Cloud Run:** FastAPI poběží jako samostatná služba se škálováním na nulu. Každá instance používá seedovaný SQLite soubor z vlastní neměnné image. Nezapisuje se do něj, takže není potřeba sdílený persistentní disk ani Cloud SQL. Po úpravě seed dat se vytvoří a nasadí nová image.
- **Omezení:** změny provedené za běhu v lokálním souborovém systému Cloud Run nejsou trvalé a nejsou sdílené mezi instancemi; proto jsou mutační endpointy i zápis do SQLite mimo rozsah POC.
- **Testy:** ověřit vytvoření seedu, hledání hráče, seznam zápasů, filtry, nenalezené a nejednoznačné jméno i odpověď chatu.
- **Pozdější rozšíření:** pokud bude potřeba měnit data za běhu, sdílet zápisy mezi instancemi nebo spravovat živý archiv, přejít na PostgreSQL, například Cloud SQL, a přidat migrace a zabezpečený zápisový proces.

## Nasazení

Současný deployment publikuje React frontend na Firebase Hosting a ASP.NET Core API na Cloud Run. POC přidá vedle něj samostatnou FastAPI službu na Cloud Run; stávající API ani Firestore pro živé skóre se nemění.

FastAPI bude nasazené s minimálním počtem instancí 0 a maximálním počtem instancí nastaveným na rozumný limit pro demo. Pro historické dotazy použije pouze read-only SQLite databázi přibalenou do image. Cloud SQL se pro tuto fázi nezřizuje. Firebase Hosting může požadavky `/api/history/**` přesměrovat na FastAPI, případně může frontend volat Cloud Run URL přímo s odpovídajícím CORS nastavením.

1. Přidat Dockerfile a testy pro FastAPI službu; při sestavení image vytvořit a naplnit SQLite databázi seedem.
2. Rozšířit GitHub Actions o instalaci Pythonu, testy a sestavení FastAPI image.
3. Nasadit samostatnou FastAPI službu na Cloud Run se škálováním na nulu.
4. Zpřístupnit ji frontendu přes Firebase Hosting rewrite/proxy nebo přímo přes URL Cloud Run; při přímém volání správně nakonfigurovat CORS.
5. Nastavit Cloud Run limity instancí a rozpočtová upozornění. Cloud Run se účtuje podle využití a bez provozu může škálovat na nulu; případné náklady závisí na aktuální kvótě a nastavení.

## Doporučený rozsah implementace POC

1. Založit FastAPI projekt a SQLite databázi se SQLAlchemy.
2. Definovat tabulky `players`, `tournaments`, `matches` a `match_sets`.
3. Připravit opakovatelný seed a krok sestavení image, který vytvoří předvyplněný databázový soubor.
4. Implementovat read-only endpointy pro roky, turnaje, hráče a zápasy.
5. Přidat React stránku `/history` se seznamem roků, filtry a výsledky.
6. Přidat pravý chat panel s jedním nebo několika jasně vymezenými typy dotazů bez LLM.
7. Doplnit testy backendu a ověřit build frontendu.
8. Nasadit ukázkovou verzi Reactu a FastAPI na stávající Firebase Hosting a Cloud Run; databáze bude součástí image, bez Cloud SQL.

## Otevřené otázky

- Potřebujeme zobrazovat oddíl hráče historicky podle roku, nebo pro POC stačí aktuální oddíl?
- Jaké fáze turnaje se mají rozlišovat v `round`?
- Jaký počet realistických hráčů, turnajů a výsledků má seed obsahovat?

## Shrnutí doporučení

Oddělit živé skóre od historických výsledků. První ukázatelný POC poběží na veřejném webu: React stránka `/history` na Firebase Hosting bude volat samostatné FastAPI na Cloud Run. FastAPI bude škálovat na nulu a používat read-only SQLite databázi se seedovanými daty, vytvořenou při sestavení a přibalenou do image. Cloud SQL není pro tuto neměnnou ukázkovou databázi potřeba. PostgreSQL/Cloud SQL se doplní až při požadavku na zápis a trvalé změny dat za běhu.
