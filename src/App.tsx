function App() {
  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="TTTS, úvodní stránka">
          <span className="wordmark-mark" aria-hidden="true">T</span>
          <span>TTTS</span>
        </a>
        <span className="topbar-label">VEŘEJNÝ PŘEHLED</span>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <div className="intro-copy">
          <p className="eyebrow"><span className="status-dot" />TABLE TENNIS TOURNAMENT SYSTEM</p>
          <h1 id="page-title">Turnaj začíná<br />tady.</h1>
          <p className="intro-description">Jedno místo pro přehled turnajů, zápasů a výsledků.</p>
        </div>
        <div className="court-art" aria-hidden="true">
          <div className="court court-back"><span className="court-net" /><span className="court-center" /></div>
          <div className="court court-front"><span className="court-net" /><span className="court-center" /></div>
          <span className="ball ball-coral" />
          <span className="ball ball-lime" />
        </div>
      </section>

      <section className="live-section" aria-labelledby="live-title">
        <div className="section-heading">
          <div><p className="eyebrow">NAŽIVO</p><h2 id="live-title">Právě se hraje</h2></div>
          <span className="count-label">0 ZÁPASŮ</span>
        </div>
        <div className="empty-state">
          <div className="empty-icon" aria-hidden="true"><span /><span /></div>
          <div>
            <h3>Zatím žádný rozehraný turnaj</h3>
            <p>Jakmile budou dostupná turnajová data, zobrazí se tady.</p>
          </div>
          <span className="empty-state-index">TTTS / 001</span>
        </div>
      </section>

      <footer className="footer">
        <span>TTTS <span className="footer-separator">/</span> POČÁTEČNÍ VERZE</span>
        <span>STOLNÍ TENIS, PŘEHLEDNĚ.</span>
      </footer>
    </main>
  )
}

export default App