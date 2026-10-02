import { FormEvent, useEffect, useState } from 'react';
import { Activity, ArrowRight, AudioLines, Bot, Check, ChevronDown, CircleHelp, Command, Cpu, Eye, Fingerprint, LockKeyhole, LogOut, MessageSquareText, Mic2, Monitor, Send, ShieldCheck, Sparkles, X } from 'lucide-react';

type Status = {
  status: string;
  authenticated: boolean;
  public_demo: boolean;
  web_login_configured: boolean;
  gemini_configured: boolean;
  capabilities: string[];
  desktop_only: string[];
};

type ChatLine = { role: 'user' | 'assistant'; content: string };

const api = async (path: string, body?: unknown) => {
  const response = await fetch(path, {
    method: body ? 'POST' : 'GET',
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail?.message || 'The request could not be completed.');
  return data;
};

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [activeNav, setActiveNav] = useState('Agent workspace');
  const [showCapabilities, setShowCapabilities] = useState(false);

  useEffect(() => {
    api('/api/status')
      .then((health: Status & { authenticated: boolean }) => {
        setStatus(health);
        setAuthenticated(health.authenticated || health.public_demo);
        if (health.public_demo) setUsername('Public demo');
      })
      .catch(() => setError('The Intent OS API is not reachable. Start the backend and refresh this page.'));
  }, []);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api('/api/login', { username, password });
      setAuthenticated(true);
      setUsername(result.username);
      setChat([{ role: 'assistant', content: `Welcome to Intent OS, ${result.username}. I can help with text questions and web-safe workflows. I cannot view or control your device from this web session.` }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Sign in failed.');
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const clean = message.trim();
    if (!clean || busy) return;
    const next = [...chat, { role: 'user' as const, content: clean }];
    setChat(next);
    setMessage('');
    setBusy(true);
    setError('');
    try {
      const result = await api('/api/chat', { message: clean, history: next.slice(-12, -1) });
      setChat([...next, { role: 'assistant', content: result.reply }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The message failed.');
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try { await api('/api/logout', {}); } catch { /* Clear this browser view even if the API is offline. */ }
    setAuthenticated(false);
    setPassword('');
    setChat([]);
  }

  if (!status) {
    return <main className="signin-shell"><section className="signin-panel startup-state"><header className="brand-lockup"><div className="brand-mark"><Command size={19} /></div><span>INTENT <b>OS</b></span></header><div className="signin-content"><span className="eyebrow"><span className="live-dot" /> WEB WORKSPACE</span><h1>{error ? 'Workspace unavailable.' : 'Preparing your workspace.'}</h1><p className="signin-copy">{error || 'Connecting securely to Intent OS…'}</p></div></section></main>;
  }

  if (!authenticated) {
    return (
      <main className="signin-shell">
        <div className="signin-art" aria-hidden="true">
          <div className="art-grid" />
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div className="art-core"><Command size={46} strokeWidth={1.25} /></div>
          <span className="art-caption">AWARE BY DESIGN <i /> READY WHEN YOU ARE</span>
          <span className="art-index">01 <b>/</b> 03</span>
        </div>
        <section className="signin-panel">
          <header className="brand-lockup"><div className="brand-mark"><Command size={19} /></div><span>INTENT <b>OS</b></span><span className="web-label">WEB WORKSPACE</span></header>
          <div className="signin-content">
            <span className="eyebrow"><span className="live-dot" /> PRIVATE CLOUD SESSION</span>
            <h1>Make intent<br /><em>operational.</em></h1>
            <p className="signin-copy">Your focused workspace for clear thinking and practical AI assistance.</p>
            <form className="signin-form" onSubmit={signIn}>
              <label htmlFor="username">Username</label>
              <div className="input-wrap"><Fingerprint size={17} /><input id="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} placeholder="Your account name" required /></div>
              <label htmlFor="password">Password</label>
              <div className="input-wrap"><LockKeyhole size={17} /><input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" required /></div>
              {error && <p className="error-note" role="alert">{error}</p>}
              <button className="primary-button" disabled={busy || !status?.web_login_configured}>
                {busy ? 'Checking credentials…' : 'Sign in to Intent OS'} <ArrowRight size={17} />
              </button>
              {!status?.web_login_configured && <p className="form-hint">Web sign-in needs WEB_DEMO_USERNAME, WEB_DEMO_PASSWORD, and WEB_SESSION_SECRET configured on the server.</p>}
            </form>
            <div className="signin-assurance"><ShieldCheck size={16} /><span>Protected session</span><span className="assurance-rule" /><span>Desktop agent remains local</span></div>
          </div>
          <footer className="signin-footer"><span>INTENT OS · WEB EDITION</span><span>01.0.0</span></footer>
        </section>
      </main>
    );
  }

  const navItems = [
    { name: 'Overview', icon: Activity },
    { name: 'Agent workspace', icon: Bot },
    { name: 'Capabilities', icon: Eye },
  ];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <header className="brand-lockup"><div className="brand-mark"><Command size={18} /></div><span>INTENT <b>OS</b></span></header>
        <div className="sidebar-kicker">WORKSPACE</div>
        <nav aria-label="Workspace navigation">
          {navItems.map(item => {
            const Icon = item.icon;
            return <button key={item.name} className={`nav-item ${activeNav === item.name ? 'selected' : ''}`} onClick={() => setActiveNav(item.name)}><Icon size={17} /><span>{item.name}</span>{activeNav === item.name && <span className="nav-marker" />}</button>;
          })}
        </nav>
        <div className="sidebar-spacer" />
        <section className="desktop-link"><div className="desktop-link-icon"><Monitor size={17} /></div><div><strong>Desktop Agent</strong><span>Local hardware control</span></div><span className="local-tag">LOCAL</span><p>Camera, gestures, voice and desktop automation run on your own machine.</p></section>
        {status.public_demo ? <div className="profile-row public-profile"><div className="avatar">J</div><span className="profile-text"><strong>Judge demo</strong><small>Public session</small></span></div> : <button className="profile-row" onClick={signOut}><div className="avatar">{username.slice(0, 1).toUpperCase()}</div><span className="profile-text"><strong>{username}</strong><small>Web session</small></span><LogOut size={16} /></button>}
      </aside>

      <section className="main-area">
        <header className="topbar"><div className="breadcrumb">Intent OS <span>/</span> {activeNav}</div><div className="topbar-right"><span className="api-pill"><span className={`status-dot ${status?.gemini_configured ? '' : 'muted'}`} />{status?.gemini_configured ? 'AI configured' : 'AI setup required'}</span><button className="icon-button" title="Web capabilities information" onClick={() => setShowCapabilities(v => !v)}><CircleHelp size={18} /></button></div></header>
        {activeNav === 'Agent workspace' ? (
          <div className="workspace-content">
            <div className="page-heading"><div><span className="eyebrow">INTENT OS · WEB AGENT</span><h1>Agent workspace</h1><p>Reasoning and conversation, with device boundaries made explicit.</p></div><div className="agent-status"><span className="status-dot" /><div><strong>Ready</strong><small>Text agent · Cloud</small></div><ChevronDown size={15} /></div></div>
            <div className="agent-grid">
              <section className="conversation-panel">
                <header className="panel-header"><div className="panel-title-icon"><MessageSquareText size={17} /></div><div><strong>Conversation</strong><small>{status.public_demo ? 'Public demo conversation' : 'Private to this browser session'}</small></div><span className="panel-live"><span className="status-dot" /> LIVE</span></header>
                <div className="conversation-log" aria-live="polite">
                  {chat.length === 0 && <div className="empty-state"><div className="empty-symbol"><Sparkles size={23} /></div><h2>Where should we begin?</h2><p>Ask a question, explore an idea, or work through a web-safe task.</p><div className="suggestion-row"><button onClick={() => setMessage('Help me plan a project')}>Plan a project <ArrowRight size={13} /></button><button onClick={() => setMessage('Explain how Intent OS works')}>Explain Intent OS <ArrowRight size={13} /></button></div></div>}
                  {chat.map((line, index) => <article className={`chat-line ${line.role}`} key={`${index}-${line.role}`}><div className="chat-avatar">{line.role === 'assistant' ? <Bot size={16} /> : username.slice(0, 1).toUpperCase()}</div><div className="chat-body"><span>{line.role === 'assistant' ? 'INTENT OS' : 'YOU'}</span><p>{line.content}</p></div></article>)}
                  {busy && <div className="thinking-row"><span className="typing-dots"><i /><i /><i /></span> Intent OS is thinking</div>}
                </div>
                {error && <div className="inline-error" role="alert"><X size={15} />{error}</div>}
                <form className="composer" onSubmit={sendMessage}><textarea value={message} onChange={e => setMessage(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} placeholder="Message Intent OS…" rows={2} maxLength={4000} /><div className="composer-bottom"><span><span className="enter-key">↵</span> Send · Shift + ↵ for a new line</span><button type="submit" aria-label="Send message" disabled={busy || !message.trim()}><Send size={17} /></button></div></form>
              </section>

              <aside className="insight-column">
                <section className="status-panel"><header><span className="section-icon green"><Activity size={16} /></span><h2>System status</h2></header><div className="status-row"><span>Web API</span><strong><i className="status-dot" /> Online</strong></div><div className="status-row"><span>Gemini reasoning</span><strong className={status?.gemini_configured ? '' : 'status-warn'}><i className={`status-dot ${status?.gemini_configured ? '' : 'muted'}`} />{status?.gemini_configured ? 'Configured' : 'Needs setup'}</strong></div><div className="status-row"><span>Session</span><strong><i className="status-dot" /> Authenticated</strong></div></section>
                <section className="status-panel capability-panel"><header><span className="section-icon blue"><Cpu size={16} /></span><h2>Web capabilities</h2></header><div className="capability-item"><MessageSquareText size={16} /><div><strong>Text conversation</strong><span>AI reasoning with Gemini</span></div><Check size={15} /></div><div className="capability-item"><ShieldCheck size={16} /><div><strong>Safe by default</strong><span>No remote device actions</span></div><Check size={15} /></div><button className="text-action" onClick={() => setShowCapabilities(v => !v)}>View capability boundaries <ArrowRight size={14} /></button></section>
                <section className="device-panel"><div className="device-panel-top"><div className="device-orb"><Monitor size={20} /></div><span className="local-tag">LOCAL ONLY</span></div><h2>Full multimodal control</h2><p>Camera, microphone, screen intelligence, gesture input and mouse automation are available in the Windows desktop app.</p><div className="desktop-features"><span><Eye size={14} /> Vision</span><span><AudioLines size={14} /> Voice</span><span><Mic2 size={14} /> Gestures</span></div></section>
                <div className="privacy-note"><LockKeyhole size={14} /><span>Do not send passwords, API keys, or private credentials in chat.</span></div>
              </aside>
            </div>
          </div>
        ) : (
          <div className="workspace-content alternate-page"><span className="eyebrow">INTENT OS · WORKSPACE</span><h1>{activeNav}</h1><p>{activeNav === 'Overview' ? 'Your web session is ready. Open Agent workspace to start a text conversation.' : 'Browser-safe features are available here. Camera, gestures, voice and device control remain local to the Desktop Agent.'}</p><button className="primary-button compact" onClick={() => setActiveNav('Agent workspace')}>Open agent workspace <ArrowRight size={16} /></button></div>
        )}
        <footer className="bottom-bar"><span><span className="status-dot" /> Intent OS Web · Connected</span><span>WEB AGENT IS TEXT-ONLY <b>·</b> DESKTOP CONTROLS STAY LOCAL</span></footer>
        {showCapabilities && <div className="modal-backdrop" onClick={() => setShowCapabilities(false)}><section className="capability-modal" onClick={e => e.stopPropagation()}><button className="icon-button modal-close" title="Close" onClick={() => setShowCapabilities(false)}><X size={18} /></button><span className="eyebrow">CAPABILITY BOUNDARIES</span><h2>Web and desktop are separate by design.</h2><p>The cloud agent handles text, reasoning and web-safe workflows. It cannot inspect your screen or control your machine.</p><div className="boundary-columns"><div><strong>WEB SESSION</strong><span>Text chat</span><span>Gemini reasoning</span><span>Dashboard and status</span></div><div><strong>DESKTOP AGENT</strong><span>Camera and gestures</span><span>Microphone and voice</span><span>Screen, mouse and keyboard</span></div></div><button className="primary-button compact" onClick={() => setShowCapabilities(false)}>Understood <Check size={16} /></button></section></div>}
      </section>
    </main>
  );
}
