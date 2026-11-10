# Návrh architektury chatbota nad historickými sportovními výsledky

Tohle je ideální a extrémně elegantní projekt pro kombinaci relační databáze (SQL) a LLM. Mnoho lidí má tendenci cpát všechno do vektorové databáze, ale u historických sportovních výsledků, kde se počítá, filtruje, sčítá a hledají se přesné relace, je vektorová databáze slepá ulička.

Zde je návrh architektury, technologického stacku a hlavně konceptu, jak donutit LLM odpovídat na komplexní dotazy, jako například „nejvíc proher za sebou“.

## 1. Návrh architektury (high-level)

Plán s odděleným frontendem a backendem v K8s/Dockeru dává smysl.

```text
[ React frontend – Firebase Hosting ]
           ├── živé skóre → ASP.NET Core API – Cloud Run → Firestore
           └── historie/chat → FastAPI – Cloud Run
                                  └── seedovaná SQLite v Docker image (read-only)
```

Pro první ukázatelný POC se FastAPI nasadí jako samostatná služba na Cloud Run vedle existujícího ASP.NET Core API. SQLite soubor se vytvoří ze seedovacích dat při sestavení Docker image a do Cloud Run se nasadí společně s aplikací. FastAPI může škálovat na nulu; samostatná Cloud SQL instance není pro neměnná ukázková data potřeba. Zápisy za běhu nejsou součástí tohoto POC. Pokud bude později potřeba data měnit nebo sdílet zápisy mezi instancemi, přejde se na PostgreSQL, například Cloud SQL.

První chat může fungovat bez LLM: FastAPI rozpozná omezené typy dotazů, načte data pomocí SQLAlchemy a vrátí odpověď sestavenou z výsledků. API klíč k modelu tedy pro tento POC není potřeba. LangGraph, LangChain a volba cloudového či lokálního modelu jsou navazující rozšíření.

### Klíčové zjištění pro chatbota nad databází

Dotazy typu „kolikrát vyhrál 3:2“ nebo „kolik nejvíc zápasů za sebou prohrál Martin“ nelze efektivně řešit pouhým sémantickým RAGem (vektorovou databází), protože vektorová DB neumí počítat agregace, řadit podle data ani počítat série proher za sebou.

Na backendu jsou dvě hlavní cesty:

## 2. Volba AI přístupu na backendu: Text-to-SQL vs. LangGraph Code Interpreter

### Přístup A: Text-to-SQL (klasický RAG / agent)

**Jak to funguje:** LLM dostane schéma relační databáze (tabulky `players`, `tournaments`, `matches`, `sets`) a dotaz uživatele, například „Jak hrál Jan Novák s Petrem Kašparem letos?“ LLM vygeneruje SQL dotaz, backend ho bezpečně spustí nad relační databází, vrátí výsledky a LLM z nich vytvoří přirozenou odpověď. V navrženém POC se volné generování SQL nepoužije; aplikace nabídne předem definované read-only dotazy nad SQLite.

**Proč je to zrádné:** Složité analytické dotazy, například „kolik nejvíc zápasů za sebou prohrál Martin, řazeno chronologicky“, vyžadují velmi složité SQL (například window functions), ve kterém může LLM chybovat.

### Přístup B: Python / Pandas agent (doporučeno pro složité statistiky typu „série proher“)

**Jak to funguje:** Místo toho, aby LLM psal SQL, backend stáhne relevantní data z databáze (například všechny zápasy daného hráče jako Pandas DataFrame nebo čistý JSON) a předá je agentovi, například přes LangGraph s Python Code Interpreterem. Agent v zabezpečeném sandboxu napíše krátký Python kód, například pro výpočet série proher pomocí pandas, a vrátí výsledek.

**Proč je to lepší:** Pro statistické dotazy typu „série za sebou“ nebo „procentuální úspěšnost v pátých setech“ je Python/Pandas pro LLM přirozenější a méně chybový než psaní složitých SQL joinů.

## 3. Doporučený tech stack pro backend

- **Jazyk a API framework:** Python + FastAPI (pro AI ekosystém velmi vhodná volba).
- **AI orchestrace později:** LangGraph (vhodný pro stavové agenty, kteří nejdřív musí zjistit ID hráče z databáze a pak teprve načíst zápasy). První cloudový POC používá deterministickou logiku bez LLM.
- **Databáze:** pro cloudový POC seedovaná SQLite přibalená do image FastAPI na Cloud Run (read-only, bez Cloud SQL); PostgreSQL/Cloud SQL až při potřebě trvalých zápisů nebo sdílení měněných dat.
- **Vektorová DB:** Tady téměř není potřeba. Může se hodit maximálně pro rychlé vyhledávání jména hráče při překlepu („Petry Kašpar“ místo „Petr Kašpar“); jinak stačí běžné textové hledání v SQL (`LIKE` v SQLite pro POC, `ILIKE` v PostgreSQL).

## 4. Návrh databázového schématu (stručně)

Abychom agentovi LLM usnadnili práci, schéma by mělo být čisté:

- `players` (`id`, `first_name`, `last_name`, `club`)
- `tournaments` (`id`, `name`, `location`, `date_from`, `date_to`)
- `matches` (`id`, `tournament_id`, `player1_id`, `player2_id`, `round_type` [group/playoff], `winner_id`)
- `sets` (`id`, `match_id`, `set_number`, `player1_score`, `player2_score`) – zde jsou přesné výsledky setů.

## 5. Jak to zabalit do Dockeru (microservice architecture)

V dlouhodobém návrhu může být backend rozdělen na dvě části (nebo dvě vnitřní služby v K8s). Pro aktuální POC zůstává existující .NET API beze změny a FastAPI je samostatná služba pro historická data:

- **Core API Service (`/api/...`):** V dlouhodobém návrhu spravuje turnaje, hráče a zápasy. Současné .NET API zatím obsluhuje live skóre; tento POC do něj historická data ani zápisové funkce nepřidává.
- **FastAPI historická data a POC chat:** Samostatný kontejner na Cloud Run s read-only seedovanou SQLite databází v image. V první fázi poskytuje filtry a omezený chat bez LLM; později může obsluhovat LangGraph agenta.

Díky tomu lze při zkoušení jiného chatbota (například přepsání z Pythonu do Node.js/TypeScriptu nebo změně frameworku) vyměnit jen jeden Docker kontejner, aniž by o tom hlavní systém musel vědět.

## 6. Cílový flow s LLM: „Jak hrál Jan Novák tento rok?“

Následující příklad popisuje budoucí cestu dotazu s LLM agentem. Pro přehlednost předpokládá, že aktuální rok je 2026. V prvním POC se kroky rozpoznání záměru a formulace odpovědi provedou pevnou aplikační logikou bez LangGraphu a LLM; data se i tehdy čtou ze stejné seedované SQLite databáze.

### Krok 1: Uživatel odešle dotaz ve frontendu

Uživatel napíše do chatovacího okna „Jak hrál Jan Novák tento rok?“ a klikne na **Odeslat** nebo stiskne Enter. Frontend zobrazí jeho zprávu a indikátor načítání, například „Bot přemýšlí…“, a odešle požadavek na backend:

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "message": "Jak hrál Jan Novák tento rok?",
  "conversation_id": "xyz-123"
}
```

Odpověď lze vrátit najednou, případně ji streamovat přes Server-Sent Events (SSE).

### Krok 2: FastAPI předá požadavek agentovi

FastAPI přijme požadavek, ověří jeho formát a předá zprávu LangGraph agentovi. Agent rozpozná záměr a potřebné údaje:

- **Hráč:** Jan Novák
- **Období:** od 1. ledna 2026 do dnešního dne
- **Požadovaná data:** přehled výsledků zápasů

### Krok 3: Agent vyhledá hráče

Agent zavolá databázový nástroj pro vyhledání hráče, například `search_player(name="Jan Novák")`. Nástroj vrátí odpovídající záznam, například:

```json
{
  "id": 42,
  "name": "Jan Novák"
}
```

Pokud se najde více hráčů se stejným jménem nebo žádná jednoznačná shoda, agent si před načtením výsledků vyžádá upřesnění.

### Krok 4: Backend načte a případně spočítá výsledky

S ID hráče a časovým rozsahem backend načte jeho zápasy z tabulek `matches` a `tournaments` a podle potřeby také výsledky setů z tabulky `sets`. Filtrování a výpočty, například počty výher a proher, provede databáze nebo pevně definovaná aplikační logika. LLM dostane strukturovaná data, ne neověřená čísla odvozená pouze z textu.

Příklad vrácených dat:

```json
[
  {
    "tournament": "O pohár",
    "date": "2026-03-15",
    "opponent": "Petr Kašpar",
    "result": "win",
    "score": "3:1",
    "sets": ["11:9", "8:11", "11:5", "11:7"]
  },
  {
    "tournament": "Turnaj Praha",
    "date": "2026-05-20",
    "opponent": "Martin Veselý",
    "result": "loss",
    "score": "2:3",
    "sets": []
  }
]
```

### Krok 5: LLM sestaví odpověď

LLM přeformuluje dodaná data do srozumitelné češtiny. Neměl by doplňovat výsledky, které v datech nejsou; pokud některý údaj chybí, uvede to nebo jej vynechá.

### Krok 6: Backend vrátí odpověď do frontendu

FastAPI vrátí text odpovědi (případně jej odešle průběžně přes SSE). Frontend skryje indikátor načítání a vykreslí odpověď v chatu, například:

> Jan Novák odehrál v roce 2026 zatím 2 zápasy:  
> - **O pohár (15. 3. 2026)** vs. Petr Kašpar — výhra 3:1 (sety 11:9, 8:11, 11:5, 11:7).  
> - **Turnaj Praha (20. 5. 2026)** vs. Martin Veselý — prohra 2:3.

### Shrnutí toku

1. **Frontend** odešle zprávu a zobrazí stav načítání.
2. **FastAPI** předá požadavek agentovi a vrátí odpověď klientovi.
3. **LangGraph agent** rozpozná záměr, hráče a časové období a koordinuje volání nástrojů.
4. **Databáze a aplikační logika** vyhledají zápasy a provedou přesné výpočty.
5. **LLM** převede ověřená strukturovaná data do přirozené odpovědi.

## 7. API klíč vs. lokální model

Zapojení LLM může při každém dotazu spotřebovávat tokeny. Náklady a požadavky na provoz závisí na tom, zda použijete cloudové API, nebo model spustíte sami.

### Varianta A: Cloudové API

FastAPI komunikuje s poskytovatelem modelu přes jeho API. Přístupový klíč, například `OPENAI_API_KEY` nebo `ANTHROPIC_API_KEY`, se ukládá jako tajná proměnná prostředí nebo do secret manageru. Klíč nepatří do zdrojového kódu ani do frontendu.

**Výhody:** jednoduché nasazení, není potřeba vlastní GPU a snadný přístup k výkonným modelům.  
**Nevýhody:** platíte podle využití, potřebujete připojení k internetu a odesílaná data zpracovává externí poskytovatel.

### Varianta B: Lokální model

Model lze provozovat na vlastním počítači nebo serveru například pomocí Ollamy či vLLM. Aplikace pak volá lokální endpoint; některé nástroje nabízejí rozhraní kompatibilní s OpenAI API. Pro komunikaci mezi kontejnery je potřeba správně nastavit síťovou adresu — `localhost` uvnitř kontejneru obvykle označuje právě tento kontejner, nikoli hostitelský počítač.

**Výhody:** bez poplatku za cloudové tokeny, větší kontrola nad daty a možnost provozu bez odesílání dotazů externímu poskytovateli.  
**Nevýhody:** náklady na hardware, elektřinu a údržbu; rychlost a kvalita závisí na modelu a dostupné paměti/GPU. „Zdarma“ tedy znamená bez poplatku za API, nikoli bez provozních nákladů.

### Orientační spotřeba a výpočet ceny

Jeden dotaz může vyvolat více volání modelu. Například agent nejprve rozpozná záměr a zavolá nástroj a po načtení výsledků vytvoří finální odpověď. Spotřeba závisí na délce systémového promptu, historii konverzace, počtu volání a množství dat vrácených databází. Jako hrubý příklad může jednoduchý dotaz spotřebovat přibližně **1 500–2 500 tokenů celkem**, ale skutečnou spotřebu je potřeba měřit.

U cloudového API se cena obvykle počítá zvlášť pro vstupní a výstupní tokeny:

```text
cena = (vstupní tokeny / 1 000 000 × sazba za vstup)
     + (výstupní tokeny / 1 000 000 × sazba za výstup)
```

Ceníky se liší podle modelu a poskytovatele a mohou se měnit. Starší orientační odhady cen proto před rozhodnutím ověřte v aktuálním ceníku vybraného poskytovatele; náklady lze přesněji odhadnout až po změření skutečných volání.

### Jak omezit spotřebu

- **Používat předpřipravené nástroje:** místo předávání celého schématu a volného generování SQL nabídnout například funkci `get_player_matches(player_name, year)`. Aplikační logika pak spustí předem definovaný parametrizovaný dotaz.
- **Omezit kontext:** posílat jen relevantní část historie a jen výsledky potřebné pro odpověď.
- **Využít cachování promptu:** pokud ho poskytovatel podporuje, stabilní části promptu lze opakovaně využít; podmínky a úsporu ověřte v jeho dokumentaci.
- **Měřit volání:** zaznamenávat počet volání a vstupní/výstupní tokeny, aby šlo náklady sledovat a porovnat cloudový a lokální provoz.

Pro tento typ aplikace je vhodné, aby LLM vybíralo z úzce vymezených nástrojů a databáze či aplikační logika prováděla přesné výpočty. Tím se současně zmenšuje prompt, zlepšuje kontrolovatelnost dotazů a omezuje riziko chybných výsledků.
