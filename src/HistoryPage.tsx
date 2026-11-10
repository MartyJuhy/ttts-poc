import { useEffect, useState, type FormEvent } from 'react'

interface Player {
  id: number
  name: string
  birth_year: number
  club: string
}

interface Tournament {
  id: number
  name: string
  city: string
  year: number
}

interface MatchSet {
  set_number: number
  player1_score: number
  player2_score: number
}

interface HistoricalMatch {
  id: number
  played_at: string
  tournament_id: number
  tournament: string
  city: string
  round: string
  player1: Player
  player2: Player
  winner_id: number
  score: string
  sets: MatchSet[]
}

interface MatchesResponse {
  items: HistoricalMatch[]
  total: number
}

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  matches?: HistoricalMatch[]
}

type Translation = { [Key in keyof typeof translations.cs]: string }

const translations = {
  cs: {
    live: 'Probíhá',
    history: 'Historické výsledky',
    title: 'Historické výsledky',
    intro: 'Procházejte turnaje, hráče a odehrané zápasy.',
    years: 'ROKY',
    allYears: 'Všechny roky',
    search: 'Hledat hráče, soupeře nebo turnaj',
    tournament: 'Turnaj',
    allTournaments: 'Všechny turnaje',
    player: 'Hráč',
    choosePlayer: 'Všichni hráči',
    opponent: 'Soupeř',
    anyOpponent: 'Libovolný soupeř',
    clear: 'Vymazat filtry',
    resultCount: 'ZÁPASŮ',
    loading: 'Načítám historické výsledky…',
    noResults: 'Pro zvolené filtry jsme nenašli žádné zápasy.',
    apiError: 'Historické API není dostupné. Spusť FastAPI na http://localhost:8000.',
    winner: 'VÍTĚZ',
    round: 'FÁZE',
    chatTitle: 'Chat nad výsledky',
    chatIntro: 'Zeptejte se například: „Jaké zápasy odehrál Jan Novák?“',
    chatPlaceholder: 'Napište dotaz k výsledkům…',
    send: 'Odeslat',
    thinking: 'Hledám v historických výsledcích…',
    chatError: 'Dotaz se nepodařilo zpracovat. Zkontrolujte připojení k API.',
    emptyChat: 'Zatím žádné zprávy. Zkuste se zeptat na zápasy hráče.',
    sets: 'Sety',
  },
  en: {
    live: 'Live',
    history: 'Historical results',
    title: 'Historical results',
    intro: 'Browse tournaments, players, and completed matches.',
    years: 'YEARS',
    allYears: 'All years',
    search: 'Search player, opponent, or tournament',
    tournament: 'Tournament',
    allTournaments: 'All tournaments',
    player: 'Player',
    choosePlayer: 'All players',
    opponent: 'Opponent',
    anyOpponent: 'Any opponent',
    clear: 'Clear filters',
    resultCount: 'MATCHES',
    loading: 'Loading historical results…',
    noResults: 'No matches found for these filters.',
    apiError: 'Historical API is unavailable. Start FastAPI at http://localhost:8000.',
    winner: 'WINNER',
    round: 'ROUND',
    chatTitle: 'Results chat',
    chatIntro: 'Try asking: “Which matches did Jan Novak play?”',
    chatPlaceholder: 'Ask about match results…',
    send: 'Send',
    thinking: 'Searching historical results…',
    chatError: 'Could not process the question. Check the API connection.',
    emptyChat: 'No messages yet. Ask about a player’s matches.',
    sets: 'Sets',
  },
} as const

function apiUrl(path: string): string {
  return `${import.meta.env.VITE_HISTORY_API_BASE_URL ?? ''}/api/history${path}`
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiUrl(path), { signal })
  if (!response.ok) throw new Error(`History API returned ${response.status}`)
  return response.json() as Promise<T>
}

function MatchCard({ match, labels }: { match: HistoricalMatch; labels: Translation }) {
  return (
    <article className="history-match">
      <div className="history-match-meta">
        <strong>{match.tournament}</strong>
        <span>{match.city} · {new Date(`${match.played_at}T00:00:00`).toLocaleDateString('cs-CZ')}</span>
      </div>
      <div className="history-match-score">
        <span className={match.winner_id === match.player1.id ? 'history-player is-winner' : 'history-player'}>
          {match.player1.name}
        </span>
        <strong>{match.score}</strong>
        <span className={match.winner_id === match.player2.id ? 'history-player is-winner' : 'history-player'}>
          {match.player2.name}
        </span>
      </div>
      <div className="history-match-footer">
        <span>{labels.round}: {match.round}</span>
        <span>{labels.sets}: {match.sets.map((set) => `${set.player1_score}:${set.player2_score}`).join(', ')}</span>
      </div>
    </article>
  )
}

export default function HistoryPage() {
  const [language, setLanguage] = useState<'cs' | 'en'>('cs')
  const [years, setYears] = useState<number[]>([])
  const [players, setPlayers] = useState<Player[]>([])
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [matches, setMatches] = useState<MatchesResponse>({ items: [], total: 0 })
  const [selectedYear, setSelectedYear] = useState('')
  const [selectedTournament, setSelectedTournament] = useState('')
  const [selectedPlayer, setSelectedPlayer] = useState('')
  const [selectedOpponent, setSelectedOpponent] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const text = translations[language]

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      fetchJson<number[]>('/years', controller.signal),
      fetchJson<Player[]>('/players', controller.signal),
    ])
      .then(([availableYears, availablePlayers]) => {
        setYears(availableYears)
        setPlayers(availablePlayers)
        if (availableYears.length > 0) setSelectedYear(String(availableYears[0]))
        setError(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const yearQuery = selectedYear ? `?year=${selectedYear}` : ''
    fetchJson<Tournament[]>(`/tournaments${yearQuery}`, controller.signal)
      .then(setTournaments)
      .catch(() => {
        if (!controller.signal.aborted) setError(true)
      })
    return () => controller.abort()
  }, [selectedYear])

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams()
    if (selectedYear) params.set('year', selectedYear)
    if (selectedTournament) params.set('tournament_id', selectedTournament)
    if (selectedPlayer) params.set('player_id', selectedPlayer)
    if (selectedOpponent) params.set('opponent_id', selectedOpponent)
    if (search.trim()) params.set('search', search.trim())

    setLoading(true)
    fetchJson<MatchesResponse>(`/matches?${params.toString()}`, controller.signal)
      .then((result) => {
        setMatches(result)
        setError(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [selectedYear, selectedTournament, selectedPlayer, selectedOpponent, search])

  function clearFilters() {
    setSelectedYear('')
    setSelectedTournament('')
    setSelectedPlayer('')
    setSelectedOpponent('')
    setSearch('')
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = chatInput.trim()
    if (!message || chatLoading) return

    setMessages((current) => [...current, { role: 'user', text: message }])
    setChatInput('')
    setChatLoading(true)
    try {
      const response = await fetch(apiUrl('/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          year: selectedYear ? Number(selectedYear) : null,
          tournament_id: selectedTournament ? Number(selectedTournament) : null,
          player_id: selectedPlayer ? Number(selectedPlayer) : null,
        }),
      })
      if (!response.ok) throw new Error(`History API returned ${response.status}`)
      const result = await response.json() as { reply: string; matches: HistoricalMatch[] }
      setMessages((current) => [...current, { role: 'assistant', text: result.reply, matches: result.matches }])
    } catch {
      setMessages((current) => [...current, { role: 'assistant', text: text.chatError }])
    } finally {
      setChatLoading(false)
    }
  }

  return (
    <main className="page-shell history-page">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="TTTS, home">
          <span className="wordmark-mark" aria-hidden="true">T</span>
          <span>TTTS</span>
        </a>
        <div className="topbar-actions">
          <span className="topbar-label">{text.history.toUpperCase()}</span>
          <div className="language-switch" role="group" aria-label="Language">
            {(['cs', 'en'] as const).map((option) => (
              <button
                aria-pressed={language === option}
                className={language === option ? 'language-button is-active' : 'language-button'}
                key={option}
                onClick={() => setLanguage(option)}
                type="button"
              >
                {option.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </header>

      <nav className="section-nav" aria-label="TTTS sections">
        <a href="/">{text.live}</a>
        <a aria-current="page" className="is-active" href="/history">{text.history}</a>
      </nav>

      <section className="history-heading">
        <div>
          <p className="eyebrow">TTTS / ARCHIV</p>
          <h1>{text.title}</h1>
          <p>{text.intro}</p>
        </div>
        <span className="history-total"><strong>{matches.total}</strong> {text.resultCount}</span>
      </section>

      <section className="history-layout">
        <aside className="history-years" aria-label={text.years}>
          <p className="eyebrow">{text.years}</p>
          <button
            aria-pressed={!selectedYear}
            className={!selectedYear ? 'year-button is-active' : 'year-button'}
            onClick={() => {
              setSelectedYear('')
              setSelectedTournament('')
            }}
            type="button"
          >
            {text.allYears}
          </button>
          {years.map((year) => (
            <button
              aria-pressed={selectedYear === String(year)}
              className={selectedYear === String(year) ? 'year-button is-active' : 'year-button'}
              key={year}
              onClick={() => {
                setSelectedYear(String(year))
                setSelectedTournament('')
              }}
              type="button"
            >
              {year}
            </button>
          ))}
        </aside>

        <section className="history-results" aria-label={text.title}>
          <div className="history-filters">
            <label className="history-search">
              <span className="visually-hidden">{text.search}</span>
              <input onChange={(event) => setSearch(event.target.value)} placeholder={text.search} value={search} />
            </label>
            <div className="history-selects">
              <label>
                <span>{text.tournament}</span>
                <select onChange={(event) => setSelectedTournament(event.target.value)} value={selectedTournament}>
                  <option value="">{text.allTournaments}</option>
                  {tournaments.map((tournament) => (
                    <option key={tournament.id} value={tournament.id}>{tournament.name} · {tournament.city}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>{text.player}</span>
                <select onChange={(event) => setSelectedPlayer(event.target.value)} value={selectedPlayer}>
                  <option value="">{text.choosePlayer}</option>
                  {players.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}
                </select>
              </label>
              <label>
                <span>{text.opponent}</span>
                <select onChange={(event) => setSelectedOpponent(event.target.value)} value={selectedOpponent}>
                  <option value="">{text.anyOpponent}</option>
                  {players
                    .filter((player) => String(player.id) !== selectedPlayer)
                    .map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}
                </select>
              </label>
            </div>
            <button className="text-button history-clear" onClick={clearFilters} type="button">{text.clear}</button>
          </div>

          <div className="history-match-list" aria-live="polite">
            {loading && <p className="history-notice">{text.loading}</p>}
            {!loading && error && <p className="history-notice is-error" role="alert">{text.apiError}</p>}
            {!loading && !error && matches.items.length === 0 && <p className="history-notice">{text.noResults}</p>}
            {!loading && matches.items.map((match) => <MatchCard key={match.id} labels={text} match={match} />)}
          </div>
        </section>

        <aside className="history-chat" aria-label={text.chatTitle}>
          <div className="history-chat-heading">
            <p className="eyebrow">TTTS / CHAT</p>
            <h2>{text.chatTitle}</h2>
          </div>
          <div className="history-chat-messages" aria-live="polite">
            {messages.length === 0 && <p className="chat-empty">{text.emptyChat}<span>{text.chatIntro}</span></p>}
            {messages.map((message, index) => (
              <div className={`chat-message is-${message.role}`} key={`${message.role}-${index}`}>
                <p>{message.text}</p>
                {message.matches?.map((match) => <MatchCard key={match.id} labels={text} match={match} />)}
              </div>
            ))}
            {chatLoading && <p className="chat-thinking">{text.thinking}</p>}
          </div>
          <form className="history-chat-form" onSubmit={(event) => void sendMessage(event)}>
            <textarea
              aria-label={text.chatPlaceholder}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder={text.chatPlaceholder}
              rows={2}
              value={chatInput}
            />
            <button className="sign-in-button" disabled={!chatInput.trim() || chatLoading} type="submit">{text.send}</button>
          </form>
        </aside>
      </section>
    </main>
  )
}
