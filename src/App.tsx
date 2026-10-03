import { useEffect, useState, type FormEvent } from 'react'
import { onAuthStateChanged, signInWithEmailAndPassword, signOut, type User } from 'firebase/auth'
import { changePoint, demoMatches, fetchMatches, verifyAdmin, type LiveMatch } from './api'
import { firebaseAuth } from './firebase'

type Language = 'cs' | 'en'

const copy = {
  cs: {
    public: 'VEŘEJNÝ PŘEHLED',
    demo: 'UKÁZKOVÁ DATA',
    live: 'PROBÍHÁ',
    club: 'Českomoravský klub veteránů',
    category: 'KATEGORIE',
    location: 'MÍSTO',
    event: 'TURNAJ',
    liveNow: 'Právě se hraje',
    matches: 'ZÁPASY',
    group: 'SKUPINA',
    table: 'STŮL',
    set: 'SET',
    player: 'HRÁČ',
    sets: 'SETY',
    currentSet: 'AKTUÁLNÍ SET',
    footer: 'UKÁZKOVÝ TURNAJ · PRAHA',
    admin: 'ADMIN',
    adminLogin: 'Přihlášení administrátora',
    email: 'E-mail',
    password: 'Heslo',
    signIn: 'Přihlásit se',
    signOut: 'Odhlásit',
    adminActive: 'ADMIN REŽIM',
    notAdmin: 'Tento účet nemá oprávnění administrátora.',
    firebaseMissing: 'Firebase Auth není nakonfigurovaný.',
    loginFailed: 'Přihlášení se nepodařilo. Zkontroluj údaje.',
    apiOffline: 'API není dostupné. Zobrazuji demo data; skóre nelze měnit.',
    tablesActive: 'STOLY V PROVOZU',
    addPoint: 'Přidat bod',
    removePoint: 'Odečíst bod',
    scoreError: 'Změnu skóre se nepodařilo uložit.',
    scoreConflict: 'Skóre mezitím změnil někdo jiný. Data se obnovila.',
    completed: 'DOHRÁNO',
  },
  en: {
    public: 'PUBLIC SCOREBOARD',
    demo: 'SAMPLE DATA',
    live: 'LIVE',
    club: 'Czech-Moravian Veterans Club',
    category: 'CATEGORY',
    location: 'LOCATION',
    event: 'EVENT',
    liveNow: 'Playing now',
    matches: 'MATCHES',
    group: 'GROUP',
    table: 'TABLE',
    set: 'SET',
    player: 'PLAYER',
    sets: 'SETS',
    currentSet: 'CURRENT SET',
    footer: 'SAMPLE TOURNAMENT · PRAGUE',
    admin: 'ADMIN',
    adminLogin: 'Administrator sign in',
    email: 'Email',
    password: 'Password',
    signIn: 'Sign in',
    signOut: 'Sign out',
    adminActive: 'ADMIN MODE',
    notAdmin: 'This account is not authorized as an administrator.',
    firebaseMissing: 'Firebase Auth is not configured.',
    loginFailed: 'Sign in failed. Check your credentials.',
    apiOffline: 'API unavailable. Showing demo data; scores cannot be changed.',
    tablesActive: 'TABLES IN PLAY',
    addPoint: 'Add point',
    removePoint: 'Remove point',
    scoreError: 'Score could not be saved.',
    scoreConflict: 'The score changed elsewhere. Data has been refreshed.',
    completed: 'FINISHED',
  },
} as const

function App() {
  const [language, setLanguage] = useState<Language>('cs')
  const [matches, setMatches] = useState<LiveMatch[]>(demoMatches)
  const [apiOnline, setApiOnline] = useState(false)
  const [adminPanelOpen, setAdminPanelOpen] = useState(false)
  const [adminUser, setAdminUser] = useState<User | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [authMessage, setAuthMessage] = useState('')
  const [scoreMessage, setScoreMessage] = useState('')
  const [pendingMatchId, setPendingMatchId] = useState<string | null>(null)
  const text = copy[language]

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const liveMatches = await fetchMatches()
        if (active) {
          setMatches(liveMatches)
          setApiOnline(true)
        }
      } catch {
        if (active) setApiOnline(false)
      }
    }

    void refresh()
    const timer = window.setInterval(() => void refresh(), 4000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!firebaseAuth) return
    let active = true
    const unsubscribe = onAuthStateChanged(firebaseAuth, async (user) => {
      if (!active) return
      setAdminUser(user)
      setIsAdmin(false)
      if (!user) return

      try {
        const authorized = await verifyAdmin(await user.getIdToken())
        if (active) {
          setIsAdmin(authorized)
          setAuthMessage(authorized ? '' : text.notAdmin)
        }
      } catch {
        if (active) setAuthMessage(text.apiOffline)
      }
    })

    return () => {
      active = false
      unsubscribe()
    }
  }, [text.apiOffline, text.notAdmin])

  async function handleSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthMessage('')
    if (!firebaseAuth) {
      setAuthMessage(text.firebaseMissing)
      return
    }

    try {
      await signInWithEmailAndPassword(firebaseAuth, email, password)
      setPassword('')
    } catch {
      setAuthMessage(text.loginFailed)
    }
  }

  async function handleSignOut() {
    if (firebaseAuth) await signOut(firebaseAuth)
    setAdminPanelOpen(false)
    setAuthMessage('')
  }

  async function handleScoreChange(match: LiveMatch, playerIndex: number, delta: -1 | 1) {
    if (!adminUser) return
    setPendingMatchId(match.id)
    setScoreMessage('')
    try {
      const token = await adminUser.getIdToken()
      const updatedMatch = await changePoint(match, playerIndex, delta, token)
      setMatches((current) => current.map((item) => item.id === updatedMatch.id ? updatedMatch : item))
    } catch (error) {
      setScoreMessage(error instanceof Error && error.message === 'score_conflict' ? text.scoreConflict : text.scoreError)
      try {
        setMatches(await fetchMatches())
      } catch {
        setApiOnline(false)
      }
    } finally {
      setPendingMatchId(null)
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="TTTS, úvodní stránka">
          <span className="wordmark-mark" aria-hidden="true">T</span>
          <span>TTTS</span>
        </a>
        <div className="topbar-actions">
          <span className="topbar-label">{text.public}</span>
          {isAdmin ? (
            <button className="admin-toggle is-admin" onClick={() => setAdminPanelOpen((open) => !open)} type="button">
              {text.adminActive}
            </button>
          ) : (
            <button className="admin-toggle" onClick={() => setAdminPanelOpen((open) => !open)} type="button">
              {text.admin}
            </button>
          )}
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

      {adminPanelOpen && (
        <section className="admin-panel" aria-label={text.adminLogin}>
          {isAdmin ? (
            <div className="admin-session">
              <p><strong>{text.adminActive}</strong><span>{adminUser?.email}</span></p>
              <button className="text-button" onClick={() => void handleSignOut()} type="button">{text.signOut}</button>
            </div>
          ) : (
            <form className="admin-form" onSubmit={(event) => void handleSignIn(event)}>
              <div className="admin-form-title">
                <p className="eyebrow">{text.admin}</p>
                <h2>{text.adminLogin}</h2>
              </div>
              <label>
                <span>{text.email}</span>
                <input autoComplete="username" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
              </label>
              <label>
                <span>{text.password}</span>
                <input autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
              </label>
              <button className="sign-in-button" disabled={!apiOnline || !firebaseAuth} type="submit">{text.signIn}</button>
              {!firebaseAuth && <p className="form-message">{text.firebaseMissing}</p>}
              {authMessage && <p className="form-message" role="alert">{authMessage}</p>}
              {!apiOnline && <p className="form-message">{text.apiOffline}</p>}
            </form>
          )}
        </section>
      )}

      <section className="tournament-overview" aria-labelledby="tournament-title">
        <div className="event-copy">
          <div className="event-flags">
            <span className="live-badge"><span className="live-dot" />{text.live}</span>
            <span className="demo-badge">{text.demo}</span>
          </div>
          <p className="eyebrow">{text.event} / 001</p>
          <h1 id="tournament-title">CMKV <span>40+</span></h1>
          <p className="club-name">{text.club}</p>
        </div>

        <div className="event-details">
          <div className="detail-item">
            <span className="detail-label">{text.category}</span>
            <strong>40+</strong>
          </div>
          <div className="detail-item">
            <span className="detail-label">{text.location}</span>
            <strong>{language === 'cs' ? 'Praha' : 'Prague'}</strong>
          </div>
          <div className="tables-summary">
            <span className="detail-label">{text.tablesActive}</span>
            <div className="table-chips">
              {matches.filter((match) => match.status === 'live').map((match) => (
                <span className="table-chip" key={match.table}>{String(match.table).padStart(2, '0')}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="matches-section" aria-labelledby="matches-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{text.live}</p>
            <h2 id="matches-title">{text.liveNow}</h2>
          </div>
          <span className="match-count"><strong>{matches.length}</strong> {text.matches}</span>
        </div>
        {!apiOnline && <p className="api-notice">{text.apiOffline}</p>}
        {scoreMessage && <p className="score-notice" role="status">{scoreMessage}</p>}

        <div className="match-list">
          {matches.map((match) => (
            <article className="match-row" key={match.table}>
              <div className="match-context">
                <span className="table-number"><span>{text.table}</span>{match.table}</span>
                <span className="group-label">{text.group} {match.group}</span>
              </div>
              <div className="scoreboard">
                <div className="scoreboard-head">
                  <span>{text.player}</span>
                  <span>{text.sets}</span>
                  <span>{text.set} {match.currentSet}</span>
                </div>
                {match.players.map((player, index) => (
                  <div className={index === 0 ? 'player-score' : 'player-score player-score-last'} key={player.name}>
                    <span className="player-name">
                      {index === 0 && <span className="service-dot" aria-label={language === 'cs' ? 'Podává' : 'Serving'} />}
                      {player.name}
                    </span>
                    <strong className="sets-score">{player.sets}</strong>
                    <span className="points-cell">
                      <strong className="points-score">{player.points}</strong>
                      {isAdmin && (
                        <span className="score-controls">
                          <button
                            aria-label={`${text.removePoint}: ${player.name}`}
                            disabled={pendingMatchId === match.id || player.points === 0 || !apiOnline}
                            onClick={() => void handleScoreChange(match, index, -1)}
                            type="button"
                          >−</button>
                          <button
                            aria-label={`${text.addPoint}: ${player.name}`}
                            disabled={pendingMatchId === match.id || !apiOnline}
                            onClick={() => void handleScoreChange(match, index, 1)}
                            type="button"
                          >+</button>
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              <span className={match.status === 'live' ? 'match-state' : 'match-state is-complete'}>
                <span className="live-dot" />{match.status === 'live' ? text.live : text.completed}
              </span>
            </article>
          ))}
        </div>
      </section>

      <footer className="footer">
        <span>TTTS <span className="footer-separator">/</span> {text.demo}</span>
        <span>{text.footer}</span>
      </footer>
    </main>
  )
}

export default App