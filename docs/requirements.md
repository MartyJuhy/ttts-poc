# TTTS – Table Tennis Tournament System — Požadavky (draft v0.9)

> Status: DRAFT — probíhá diskuze a upřesňování. Vše označené `[K OVĚŘENÍ]` je předpoklad, který je potřeba potvrdit nebo upravit.

## 1. Přehled

TTTS je PoC platforma pro řízení turnajů ve stolním tenise a poskytování historických dat pro analytiku. Skládá se z těchto částí:

1. **Webová aplikace** — veřejná část pro sledování turnajů a přihlášená admin část pro správu hráčů, turnajů a zápasů.
2. **Mobilní aplikace pro rozhodčí** (Android + iOS) — u stolu pouze sledování a editace přiděleného zápasu, zejména přidávání bodů.
3. **Analytická AI/ML část** — historie utkání, statistiky hráčů, vzájemné zápasy a predikce budoucích zápasů.
4. **Samostatná sázková webová aplikace** — oddělený PoC klient s vlastním přihlášením, který zobrazuje vybrané zápasy/predikce a umožňuje uživateli vytvořit sázku.
5. **Experimentální multi-agentní AI část** — sada spolupracujících agentů pro dotazy nad historií, statistikami a predikcemi, orchestrated pomocí Semantic Kernel.

Součástí platformy je také centrální registr hráčů v rámci organizací. Hráč má dlouhodobý profil, který lze použít ve více turnajích; turnaj se nesmí účastnit anonymní nebo pouze jednorázově zadaný hráč.

TTTS a analytická část běží jako distribuovaný cloud-native systém na GCP. Backend je v .NET/C# a je rozdělený do doménových mikroservis. Každá služba se sestavuje a nasazuje samostatně jako Docker image do Kubernetes/GKE. Sázková aplikace je samostatný projekt, který s TTTS komunikuje pouze přes definované integrační rozhraní.

### 1.1 Architektonické principy

- Jednotlivé domény jsou oddělené samostatnými mikroservisami s jasnými API kontrakty.
- Každá mikroservisa vlastní svá data a svou business logiku; jiná služba nesmí obcházet její API přímým zápisem do její databáze.
- Služby spolu komunikují synchronně přes interní API pouze tam, kde je nutná okamžitá odpověď; doménové události a analytická data se předávají asynchronně přes Pub/Sub.
- Každá služba má vlastní Docker image, konfiguraci, health-checky, logování, metriky a Kubernetes deployment.
- Systém musí tolerovat dočasný výpadek jednotlivé nedůležité služby; analytika nesmí blokovat zápis skóre a sázkový systém nesmí blokovat turnajový provoz.
- Multi-agentní AI je experimentální a není v kritické cestě turnaje, zápisu skóre ani vypořádání sázky.

### 1.2 Hranice PoC

- PoC ověřuje tok dat od zápisu bodu přes výsledek utkání a historickou analytiku až po zobrazení predikce v oddělené sázkové aplikaci.
- Oficiální výsledek zápasu vzniká pouze v TTTS; predikce AI/ML je pouze odhad a nemůže výsledek změnit.
- Sázková aplikace je pro PoC oddělená od TTTS. Peníze, skutečné vypořádání sázek, platební brána, kurzy, KYC/AML, věkové ověření a regulatorní provoz jsou mimo aktuální rozsah a musí být vyřešeny před jakýmkoli produkčním provozem.

### 1.3 Prostředí a data

Systém musí podporovat oddělená prostředí s vlastní konfigurací, nasazením a daty:

- **Local** — kompletní vývojářské prostředí spustitelné na macOS přes Docker; bez závislosti na produkčním GCP projektu.
- **Test** — automatizované testy a integrační testování mikroservis; data se mohou kdykoli resetovat a znovu seedovat.
- **Staging** — prostředí co nejbližší produkci pro end-to-end testy, testování deploymentu, migrací, observability a release kandidáta.
- **Production** — ostré prostředí s reálnými daty, oddělenými oprávněními, zálohami, monitoringem a řízeným přístupem.

Každé prostředí musí mít oddělené databáze/schémata, Firestore namespace, Pub/Sub topics/subscriptions, secrets, identity konfiguraci a integrační credentials. Produkční data se nesmí používat pro lokální ani testovací vývoj bez anonymizace.

Test a local musí podporovat opakovatelný **seed dat**: organizace, registrovaní hráči, profily, historické turnaje, rozehraný turnaj, skupiny, pavouky, zápasy, point-by-point skóre, statistiky a predikce. Seed scénáře musí mít verzi, být idempotentní a umožnit čistý reset prostředí.

Nasazení stejného Docker image do testu, stagingu a produkce se liší pouze konfigurací, secrets a environment-specific resources. Změny prostředí musí procházet CI/CD a nesmí se provádět ručními zásahy přímo v produkčních kontejnerech.

### 1.4 CI/CD a rozpočtový režim PoC

- Zdrojový kód je uložený v GitHubu; každý pull request musí projít buildem, testy, lintem, kontrolou Docker image a validací Kubernetes/Terraform konfigurace.
- GitHub Actions je hlavní CI/CD nástroj. Přístup do GCP používá OIDC/Workload Identity Federation bez dlouhodobých service-account JSON klíčů uložených v GitHubu.
- Vývoj probíhá ve feature branchích. Pull Request do `main` je standardní cesta; přímý push do `main` je zakázaný s výjimkou nouzové administrace.
- Lokální Git hooky kontrolují formátování, lint a rychlé testy; GitHub Actions provádí stejné kontroly znovu v čistém prostředí.
- CI sestaví Docker images jednou, označí je immutable tagem podle commitu a uloží do Artifact Registry. CD nasazuje přes Helm/Kustomize a propaguje stejný image do testu, stagingu a produkce.
- Po merge do `main` se image nasadí do testu a po úspěšných smoke/E2E testech se stejný image digest propaguje do stagingu a produkce.
- Deployment do testu může probíhat automaticky, staging vyžaduje schválení a production vyžaduje explicitní ruční approval a chráněnou GitHub environment.
- Terraform nebo jiný deklarativní IaC nástroj spravuje GCP projekty/služby, Artifact Registry, GKE, service accounts, Pub/Sub, Firestore a secrets reference; změny infrastruktury procházejí pull requestem.
- PoC má rozpočtové limity, billing alerts a možnost zastavit nebo odstranit cloudové workloady. Lokální Docker Compose je výchozí režim pro vývoj, aby GCP neběželo zbytečně.
- Bezplatné nebo nízkonákladové služby se používají tam, kde dávají smysl (Artifact Registry, Cloud Storage/Firebase Hosting, Firestore, Pub/Sub a Cloud Logging v rámci kvót). GKE, Cloud SQL, BigQuery a Vertex AI se zapínají pouze podle skutečné potřeby a jejich limity musí být explicitně nastavené.
- Systém nesmí předpokládat, že GCP nebo GKE jsou trvale zdarma. Před nasazením musí být ověřené aktuální ceny, free tier, region, quota limity a billing alerty.

## 2. Aktéři

| Role | Popis |
|---|---|
| **Divák** | Anonymní/veřejný uživatel webu, pouze čtení. |
| **Rozhodčí** | Používá mobilní app u stolu, zapisuje průběh zápasu (body, sety, podání). |
| **Pořadatel / Admin** | Zakládá turnaj, spravuje startovní listinu, losování, pitch/harmonogram, může i sám zadávat/opravovat skóre přes web pod admin právy. |
| **Organizace / správce organizace** | Spravuje registr hráčů organizace, jejich profily, oprávnění a účast v turnajích. |
| **Registrovaný hráč** | Má profil v systému a může být přihlášen do turnajů, ke kterým má organizace oprávnění. |
| **Externí analytický / sázkový systém** | Samostatný odběratel schválených historických a statistických dat přes integrační API nebo události; není součástí TTTS. |
| **Uživatel sázkové aplikace** | Přihlašuje se do samostatné sázkové aplikace, prohlíží dostupné zápasy a predikce a v PoC může vytvořit testovací sázku. |

## 3. Životní cyklus turnaje

1. **Založení turnaje** — název, datum, místo a počet používaných stolů. Turnaj může trvat maximálně jeden kalendářní den; počet stolů je nastavitelný pro každý turnaj zvlášť a nesmí překročit 32.
2. **Startovní listina (přihlášky)** — vybírá se z registrovaných hráčů organizace. Na účasti se uloží snapshot údajů potřebných pro turnaj a **pořadové číslo nasazení** (1 = nejlepší, N = nejhorší; přiděluje organizátor při přihlašování).
3. **Losování do skupin** — podle počtu přihlášených (1–32 hráčů → 1–8 skupin po max. 4 hráčích). Při `G` skupinách se nasadí prvních `2G` hráčů podle pořadí nasazení: do skupiny `i` patří hráč s pořadím `i` a hráč s pořadím `2G-i+1`. Například při 4 skupinách vzniknou dvojice `1+8`, `2+7`, `3+6` a `4+5`. Ostatní hráči se náhodně dolosují do zbývajících míst.
4. **Skupinová fáze** — round robin (každý s každým) v rámci skupiny.
5. **Vyhodnocení skupiny** — pořadí 1.–4. místo.
   - 1.–2. místo ze skupiny → postup do **play-off** (hlavní pavouk, K.O. systém).
   - 3.–4. místo ze skupiny → postup do **útěchy** (vedlejší pavouk, také K.O.).
6. **Play-off / útěcha** — vyřazovací pavouk až do finále.
7. **Konečné výsledky** — celkové pořadí turnaje.
8. **Archivace** — turnaj (rozlosování, výsledky, statistiky) se uloží do archivu, dostupné zpětně na webu.

**Přiřazení stolů**: ruční, volitelné (organizátor nemusí vyplňovat). Pokud je vyplněné, může se pro každý zápas lišit (hráč hraje každý zápas klidně na jiném stole) a zobrazuje se i na webu (divák vidí, na kterém stole se který zápas hraje).

**Validace turnaje**: datum/čas konce nesmí přesáhnout datum/čas začátku o více než jeden kalendářní den, počet stolů musí být v rozsahu 1–32 a žádný zápas nesmí být přiřazen ke stolu mimo deklarovanou kapacitu turnaje.

**Bodování a pořadí ve skupině**:
- Za každý vyhraný zápas získá hráč 2 tabulkové body; za prohraný zápas získá 0 bodů.
- Tabulka zobrazuje minimálně tabulkové body, počet odehraných a vyhraných zápasů, skóre setů, skóre míčků/bodů a pořadí.
- Při stejném počtu tabulkových bodů dvou hráčů rozhoduje jejich vzájemný zápas; vítěz vzájemného zápasu je v tabulce výše.
- Při stejném počtu tabulkových bodů tří hráčů se vytvoří minitabulka pouze z jejich vzájemných zápasů. Pro pořadí se použije vzájemné skóre v této minitabulce, zejména počet tabulkových bodů a následně skóre setů a míčků podle výsledků mezi těmito hráči.
- Pokud ani minitabulka neurčí pořadí jednoznačně, použije se jako další kritérium celkové skóre setů a míčků ve skupině; případný zbytkový nerozhodný stav řeší organizátor potvrzeným ručním rozhodnutím, které se auditně uloží.

## 4. Pravidla zápasu / skóre

- Zápas se hraje na **3 vítězné sety** (výsledek 3:0, 3:1, 3:2).
- Set se hraje do **11 bodů**, ale musí být vyhraný rozdílem nejméně 2 bodů; při 10:10 se pokračuje, dokud jeden hráč nezíská dvoubodový rozdíl.
- Ukládá se skóre každého jednotlivého setu, například `11:9`, `3:12`, `14:12`, `12:10`. Z tohoto skóre se odvodí výsledek zápasu `3:1` na sety.
- Ukládá se také celkový počet bodů a vyhraných setů každého hráče; oficiální výsledek se nesmí redukovat pouze na výsledek zápasu na sety.
- Rozhodčí u stolu rozhoduje o **prvním podání** — informace o tom, kdo právě podává, se zobrazuje i na webu (např. tečka u jména hráče), a mění se po každém bodě/výměně podle pravidel stolního tenisu.
- Každý bod (ukončení výměny) se zaznamenává a přenáší jako live update — **point-by-point**, ne jen souhrn setu.
- Mimo skóre `[K OVĚŘENÍ]`: zaznamenávají se time-outy, karty, přerušení zápasu? Zatím předpoklad: **ne**, jen skóre a podání.

## 5. Funkční požadavky podle modulu

### 5.0 Registr hráčů a profily
- Každá organizace má vlastní seznam registrovaných hráčů.
- Profil hráče obsahuje minimálně jméno, příjmení, zobrazované jméno, oddíl/organizaci, rok narození a stav registrace; citlivější údaje pouze v rozsahu nutném pro provoz systému `[K OVĚŘENÍ]`.
- Hráč se může při prvním přihlášení/pozvání zaregistrovat a profil se tím vytvoří trvale v systému; následně jej lze vybírat do dalších turnajů.
- Organizátor může hráče vyhledat, zobrazit jeho profil a přidat jej do startovní listiny konkrétního turnaje.
- Jeden hráč nesmí být v jednom turnaji přihlášen vícekrát; systém musí podporovat jednoznačnou identitu hráče i při shodě jmen.
- Správce organizace může profil deaktivovat nebo anonymizovat. Fyzické smazání je možné pouze tehdy, pokud na hráče neodkazují historické turnaje; jinak se použije deaktivace/anonymizace kvůli zachování výsledků a statistik.
- Hráč může požádat o opravu nebo odstranění svého profilu `[K OVĚŘENÍ: rozsah a proces žádosti]`.
- Profil obsahuje přehled účastí, zápasů, výsledků a statistik pouze v rozsahu povoleném oprávnění a nastavením viditelnosti.

Profil hráče navíc zpřístupňuje analytický přehled výkonu: bilanci výher a proher, výsledky podle turnajů a období, poměr vyhraných setů a bodů, formu a seznam soupeřů. Z profilu lze otevřít historii konkrétních utkání i vzájemné zápasy s vybraným soupeřem včetně chronologické bilance. Tyto statistiky jsou odvozená data; oficiálním zdrojem výsledku zůstává archivovaný zápas v TTTS.

### 5.1 Divácký web (read-only)
- Přehled **všech souběžně běžících turnajů** napříč platformou (kdokoliv si může kdekoliv v ČR založit turnaj, více turnajů běží současně) + archivovaných turnajů.
- Startovní listina turnaje.
- Rozlosování skupin + rozpis zápasů, včetně čísla stolu, pokud je vyplněné.
- Průběžné pořadí ve skupinách.
- Pavouk play-off a útěchy s průběžnými výsledky.
- **Live score** aktuálně hraných zápasů napříč všemi běžícími turnaji (skóre setů, aktuální set bod po bodu, kdo podává, stůl a hráči u něj).
- Historie/archiv dokončených turnajů a výsledků.
- Archiv umožňuje vyhledat turnaj podle názvu, data, místa nebo organizace a zobrazit startovní listinu, rozlosování, pavouky, konečné pořadí a jednotlivé výsledky.
- Archivované turnaje jsou oddělené od právě probíhajících turnajů a po uzavření se jejich oficiální výsledky nemění běžnou editací.
- Veřejný uživatel může otevřít veřejný profil hráče a jeho povolené statistiky.
- Web obsahuje samostatný přehled statistik hráčů a vzájemných zápasů s filtrem podle hráče, soupeře, období a turnaje.
- Veřejná část webové aplikace neumožňuje měnit hráče, turnaje, zápasy ani skóre.

### 5.2 Admin / organizátorský web
- Vše z diváckého webu +
- Přihlášení admina (autentizace/autorizace).
- CRUD turnaje (založení, editace, datum, název, místo, ukončení/uzamčení).
- Správa registru organizace (seznam, vyhledání, vytvoření, úprava, deaktivace/anonymizace a případné smazání hráče).
- Zobrazení profilu hráče a jeho historie v rámci organizace.
- Zobrazení analytického profilu hráče, jeho statistik, historie turnajů, všech utkání a vzájemných zápasů.
- Filtrování statistik podle období, turnaje, organizace a soupeře; oprávněný admin může zobrazit i neveřejné údaje podle pravidel organizace.
- Správa startovní listiny výběrem registrovaných hráčů; ruční vytvoření anonymního účastníka není podporováno.
- Losování do skupin (automatické, případně ruční úpravy).
- Generování rozpisu zápasů skupinové fáze.
- Zásah do live skóre — admin může zadávat/opravovat skóre stejně jako rozhodčí v mobilní app (fallback, pokud rozhodčí nemá mobil, nebo oprava chyby).
- Správa pavouku play-off/útěcha (posun vítězů/poražených do dalších kol).
- Uzavření turnaje → archivace.
- Webová admin část je hlavní rozhraní pro správu hráčů, organizací, turnajů, přihlášek, rozpisů a oprávněných zásahů do zápasů.

### 5.3 Mobilní aplikace (rozhodčí, .NET MAUI — Android/iOS)
- Přihlášení rozhodčího `[K OVĚŘENÍ: účet per rozhodčí, nebo jen výběr zápasu bez auth?]`.
- Výběr přiřazeného zápasu / stolu.
- Rozhodčí vidí pouze zápasy a stoly, ke kterým má oprávnění; mobilní aplikace neslouží ke správě hráčů, organizací ani turnajů.
- Rozhodčí může sledovat stav zápasu a upravovat jeho průběh v rozsahu přidělených oprávnění.
- Zápis bodů (přidat bod hráči A/B), oprava posledního bodu (undo).
- Automatické vyhodnocení konce setu (do 11, rozdíl 2) a konce zápasu (3 vítězné sety).
- Zobrazení a přepínání podání (podle pravidel — střídání po 2 bodech, resp. po každém bodě od 10:10).
- Live přenos každého bodu na backend (API), který dál zapisuje do Firestore.
- **Offline chování**: pokud app ztratí připojení, rozhodčí musí moci pokračovat v zápase dál — průběh (body, sety) se ukládá lokálně na zařízení a po obnovení připojení se dosynchronizuje na server. Ztráta připojení se indikuje v UI (např. červený "offline" indikátor/oblak nahoře), případně se akce, které vyžadují server, dočasně zablokují. Detailní návrh offline synchronizace (konflikty, retry) — `[K OVĚŘENÍ, řešit později]`.

### 5.4 API / Backend
- API Gateway/BFF poskytuje veřejný vstupní bod pro web a mobilní klient; směruje požadavky na příslušnou doménovou službu.
- Identity/Organization Service řeší uživatele, organizace, členství, role a tenant kontext.
- Player Service řeší profily hráčů, registrace, deaktivaci/anonymizaci a historii identity.
- Tournament Service řeší turnaje, přihlášky, skupiny, pavouky a pravidla postupu.
- Match/Scoring Service řeší zápasy, validaci bodů, setů, podání, opravy a oficiální výsledky.
- Live Score Service řeší publikaci aktuálního stavu do real-time vrstvy; není zdrojem pravdy pro oficiální výsledek.
- API ověřuje, že hráč přidaný do startovní listiny existuje a patří do organizace/tenant kontextu turnaje.
- Autentizace/autorizace probíhá na vstupu i mezi službami; divácký web má pouze veřejný read-only přístup.

### 5.5 Statistiky, AI/ML a externí integrace
- Systém ukládá historická data zápasů v podobě vhodné pro výpočty statistik (hráči, soupeři, sety, body, forma, vzájemná bilance).
- U každého historického utkání se zachovává minimálně kdo s kým hrál, kdy, v jakém turnaji, výsledek po setech a dostupná point-by-point data.
- Analytická služba poskytuje historii vzájemných zápasů, statistiky hráčů, vývoj formy a další odvozené metriky.
- Analytická služba udržuje čtecí modely pro rychlé zobrazení statistik v analytickém přehledu a v profilu hráče; tyto modely lze znovu vytvořit z archivovaných výsledků.
- Přepočet statistik je idempotentní a po opravě oficiálního výsledku musí označit nebo aktualizovat dotčené agregace.
- ML služba vytváří predikce následujících zápasů na základě historických utkání a dalších schválených vstupů; predikce jsou označené jako odhad, obsahují čas/model/verzi a nesmí měnit oficiální výsledek zápasu.
- Výpočty statistik a predikcí probíhají asynchronně a nesmí blokovat zápis live skóre ani dokončení turnaje.
- Data pro samostatnou sázkovou webovou aplikaci se poskytují přes samostatné, verzované integrační API a/nebo Pub/Sub události s řízeným přístupem. Minimální datový tok obsahuje nabídku zápasu, účastníky, stav zápasu, schválené statistiky a predikci.
- Sázková aplikace má vlastní autentizaci uživatelů a vlastní doménu pro uživatele, sázky a jejich stav; TTTS v ní neprovádí sázky, platby ani vypořádání.
- Integrace musí respektovat oprávnění organizace, ochranu osobních údajů, audit přístupů a možnost revokace přístupu.

### 5.6 Multi-agentní AI a Semantic Kernel (experimentální PoC)
- Agent Orchestration Service je samostatná mikroservisa provozovaná jako Docker image v Kubernetes/GKE.
- Orchestrátor používá Semantic Kernel jako aplikační framework pro registraci nástrojů/plugins, plánování workflow, předávání kontextu a koordinaci agentů.
- PoC obsahuje minimálně Orchestrator, Player History, Head-to-Head, Statistics, Prediction a Explanation agenta.
- Orchestrator Agent rozpozná záměr dotazu a koordinuje ostatní agenty.
- Player History Agent vyhledá účasti hráče, archivované turnaje a historická utkání.
- Head-to-Head Agent sestaví vzájemnou bilanci dvou hráčů a chronologický přehled jejich zápasů.
- Statistics Agent načte nebo spočítá schválené statistiky, formu, sety a body.
- Prediction Agent načte predikci z Analytics/ML služby a nesmí ji vydávat za oficiální výsledek.
- Explanation Agent připraví odpověď včetně zdrojových zápasů, času výpočtu a nejistoty.
- Agentům jsou dostupné pouze explicitně definované read-only nástroje přes API kontrakty, například `getPlayerProfile`, `getMatchHistory`, `getHeadToHead`, `getPlayerStatistics` a `getPrediction`.
- Agenti nesmí přímo zapisovat do databází ani volat mutační operace scoringu, turnajů, hráčů nebo sázek. Každý nástroj musí vynucovat tenant, oprávnění a audit.
- Odpověď agenta musí odlišit historická data, statistický výpočet, ML predikci a jazykové vysvětlení. Při nedostatku dat nesmí agent údaje domýšlet.
- Každé agentní workflow se loguje s identitou uživatele, použitými nástroji, verzí promptu/modelu, časem, výsledkem a případnou chybou.
- První PoC workflow: uživatel otevře profil hráče nebo zápas a požádá o shrnutí formy, vzájemných zápasů a faktorů použitých pro predikci. Výstup je informační, nikoli garance výsledku nebo doporučení sázky.

## 6. Nefunkční požadavky

- **Cloud-native na GCP**, maximální využití nativních managed služeb.
- **Real-time**: aktualizace skóre na webu prakticky okamžitě (řádově sekundy nebo méně) po zápisu bodu rozhodčím.
- **Dostupnost** v den turnaje — výpadek nesmí znemožnit dohrání zápasu (mobilní app musí zvládnout krátkodobý výpadek připojení, viz 5.3 offline chování).
- **Multi-tenancy / škálovatelnost**: platforma musí podporovat **libovolný počet nezávislých, souběžně běžících turnajů** kdekoliv (kdokoliv si může kdykoliv během dne založit vlastní turnaj); diváci na webu vidí přehled a live dění všech aktuálně běžících turnajů zároveň. V rámci jednoho turnaje může běžet více zápasů souběžně (více stolů).
- **Bezpečnost**: admin a rozhodčí operace vyžadují autentizaci a autorizaci; ochrana proti neoprávněné úpravě skóre.
- **Ochrana osobních údajů**: oddělení tenantů, audit změn profilů a výsledků, řízení viditelnosti profilu, deaktivace/anonymizace a omezení exportu osobních údajů.
- **Použitelnost mobilní app**: jednoduché, rychlé ovládání jednou rukou u stolu, minimum kliknutí na bod.
- **Architektura a provoz**: systém je distribuovaný a backend je rozdělen do samostatně nasaditelných doménových mikroservis. Každá služba je distribuována jako Docker image a provozována na Kubernetes v GCP; služby musí mít health-checky, logování, metriky a řízené škálování.
- **Oddělení systémů**: TTTS, analytická část a sázková aplikace mají oddělené odpovědnosti, přístupová oprávnění a integrační kontrakt; sázková aplikace nesmí zapisovat do zdrojových dat turnajů ani skóre.
- **AI bezpečnost**: agenti mají nejmenší nutná oprávnění, read-only přístup k doménovým datům, limity nákladů a času, ochranu proti prompt injection a auditovatelný seznam volání nástrojů.

## 7. Mimo rozsah (zatím)

- Platby / poplatky za turnaj.
- Pokročilé ML modely a garance přesnosti predikcí; první verze může začít deterministickými statistikami.
- Samotný sázkový systém, správa sázek, peněženky, platby, kurzy a regulatorní provoz.
- Vícejazyčnost webu.
- Streamování videa zápasu.

## 8. Otevřené otázky k další diskuzi

1. Pravidla řazení ve skupině při rovnosti (rozdíl setů, míčů, vzájemný zápas).
2. Detailní návrh offline synchronizace mobilní app (řešit později, mimo první iteraci).
3. Autentizace: jeden účet organizátora, nebo per-rozhodčí účty? Preferováno **co nejjednodušší řešení** — konkrétní volba auth provideru zatím otevřená (viz [tech-stack.md](tech-stack.md)).
4. Kdo/co určuje, kdy set/zápas skončil (auto-detekce v mobilní app vs. potvrzení rozhodčím)?
5. Identita hráče: registrace hráčem samotným, pozvánka organizátora, nebo obě varianty? Jaké údaje jsou povinné a co je veřejně viditelné?
6. Je hráč vlastněn jednou organizací, nebo může mít jeden profil členství ve více organizacích?
7. Která data smí odebírat externí analytický/sázkový projekt a jak bude řešen souhlas, anonymizace a audit?
8. Které služby budou samostatné mikroservisy v první iteraci (doporučení: API Gateway, Identity/Organization, Player, Tournament, Match/Scoring, Live Score, Analytics, Integration)?
9. Které části profilu a statistik hráče budou veřejné a které pouze pro organizaci nebo přihlášeného uživatele?
10. Který model provider bude Semantic Kernel v PoC používat: Vertex AI/Gemini, nebo jiný model přes abstrahovaný konektor?
11. Jaký rozsah lokálního prostředí požadujeme: všechny služby včetně emulátorů GCP, nebo zpočátku zjednodušený PoC profil?

## 9. Rozhodnuto (shrnutí)

- Zápis dat jde vždy přes Web API (validace + zápis do Cloud SQL i Firestore); klienti (Angular, MAUI) pouze čtou live data přes Firestore listenery.
- Nasazení do skupin vychází z pořadového čísla hráče na startovní listině.
- Přiřazení stolu k zápasu je ruční a volitelné, může se měnit zápas od zápasu.
- Platforma podporuje libovolné množství souběžně běžících turnajů; divácký web ukazuje přehled/live dění napříč všemi turnaji.
- Hráči jsou dlouhodobě registrovaní v organizaci a do turnajů se vybírají z registru; při prvním přihlášení se nový hráč v systému zaregistruje.
- Historické výsledky zůstávají zachované i při deaktivaci nebo anonymizaci hráče.
- Statistiky a predikce jsou oddělené od transakčního zápisu skóre a externí sázkový projekt komunikuje s TTTS pouze přes řízené integrační rozhraní.
- Distribuovaný systém je rozdělený podle domén; každá doménová služba vlastní svou business logiku, data, Docker image a Kubernetes deployment.
- Dokončené turnaje a oficiální výsledky jsou dostupné v archivu; statistiky hráčů a vzájemné zápasy jsou dostupné v analytickém přehledu i z profilu konkrétního hráče.
- Multi-agentní AI je experimentální samostatná doména; Semantic Kernel koordinuje read-only agenty nad API Analytics a Archive, bez oprávnění měnit zdrojová data.
- Turnaj trvá nejvýše jeden kalendářní den, každý turnaj má vlastní počet stolů v rozsahu 1–32 a nasazení používá dvojice `i` a `2G-i+1`; ostatní hráči se losují.
- Ukládá se skóre každého setu i celého zápasu; set musí být vyhraný rozdílem 2 bodů, za výhru v zápase jsou 2 tabulkové body a shody rozhoduje vzájemná minitabulka nebo vzájemný zápas.
- Local, test, staging a production jsou oddělená prostředí s izolovanými daty a konfigurací; testovací turnaje a hráči se vytvářejí opakovatelným seed procesem.
- Celý PoC lze spustit lokálně na macOS pomocí Dockeru bez přístupu k produkčním datům.
