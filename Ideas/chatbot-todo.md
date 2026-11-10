# Chatbot nad historickými výsledky – TODO

Chat je rule-based (bez LLM). Každý záměr = pravidlo v `history_api/main.py` + test v `history_api/test_api.py` + příklad v nápovědě „Jak hledat“ (`src/HistoryPage.tsx`).

| Záměr | Příklad otázky | Co se udělá | Stav |
|-------|----------------|-------------|------|
| Zápasy hráče | „Jak hrál Hájek?“ | stávající výpis | hotovo |
| Head-to-head | „Hájek vs Beneš“ | zápasy mezi nimi, bilance výher | hotovo |
| Bilance | „Kolikrát vyhrál Novák?“ | počet výher/proher, procento | |
| Vítěz turnaje | „Kdo vyhrál Jarní pohár 2025?“ | vítěz Finále | |
| Finalisté | „Kdo hrál finále 2024?“ | zápasy kola Finále | |
| Výsledky turnaje | „Výsledky Letního turnaje 2023“ | všechny zápasy turnaje | |
| Nejlepší | „Kdo vyhrál nejvíc turnajů?“ | agregace | |
