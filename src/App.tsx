import { useEffect, useState } from 'react'

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
  },
} as const

const matches = [
  {
    group: 'A',
    table: 1,
    set: 4,
    players: [
      { name: 'Ladislav Novák', sets: 2, points: 8 },
      { name: 'Petr Svoboda', sets: 1, points: 6 },
    ],
  },
  {
    group: 'A',
    table: 2,
    set: 3,
    players: [
      { name: 'Jiří Dvořák', sets: 1, points: 10 },
      { name: 'Milan Král', sets: 1, points: 9 },
    ],
  },
  {
    group: 'B',
    table: 3,
    set: 1,
    players: [
      { name: 'Karel Černý', sets: 0, points: 5 },
      { name: 'Pavel Marek', sets: 0, points: 7 },
    ],
  },
]

function App() {
  const [language, setLanguage] = useState<Language>('cs')
  const text = copy[language]

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="TTTS, úvodní stránka">
          <span className="wordmark-mark" aria-hidden="true">T</span>
          <span>TTTS</span>
        </a>
        <div className="topbar-actions">
          <span className="topbar-label">{text.public}</span>
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
          <div className="table-illustration" role="img" aria-label="Table tennis table, top view">
            <span className="table-doubles-line table-doubles-line-left" />
            <span className="table-doubles-line table-doubles-line-right" />
            <span className="table-net" />
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
                  <span>{text.set} {match.set}</span>
                </div>
                {match.players.map((player, index) => (
                  <div className={index === 0 ? 'player-score' : 'player-score player-score-last'} key={player.name}>
                    <span className="player-name">
                      {index === 0 && <span className="service-dot" aria-label="Podává" />}
                      {player.name}
                    </span>
                    <strong className="sets-score">{player.sets}</strong>
                    <strong className="points-score">{player.points}</strong>
                  </div>
                ))}
              </div>
              <span className="match-state"><span className="live-dot" />{text.live}</span>
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