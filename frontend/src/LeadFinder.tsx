import React, { useState, useEffect, useRef } from "react";
import SearchBar from "./components/SearchBar";
import ProgressBar from "./components/ProgressBar";
import ResultsTable from "./components/ResultsTable";

// API base: during dev the frontend runs on port 3000 and backend on 8000
const API_BASE = ((): string => {
  if (typeof window === 'undefined') return '';
  const host = window.location.hostname;
  const port = window.location.port;
  // when developing with the frontend dev server on 3000, point to backend on 8000
  if (host === 'localhost' && port === '3000') return 'http://localhost:8000';
  return 'https://leads-59wq.onrender.com';
})();

export type Lead = {
  email?: string;
  phone?: string;
  profile_url?: string;
  linkedin_url?: string;
  location_hq?: string;
  rank?: number;
  title?: string;
  url?: string;
  all_emails?: string[];
  all_phones?: string[];
  all_linkedin?: string[];
  error?: string;
};

function isLinkedInProfileUrl(u?: string): boolean {
  if (!u) return false;
  try {
    const parsed = new URL(u);
    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();
    return host === 'linkedin.com' && parsed.pathname.includes('/in/');
  } catch {
    return false;
  }
}

function isProfileUrl(u?: string): boolean {
  if (!u) return false;
  try {
    const parsed = new URL(u);
    const host = parsed.hostname.replace(/^www\./, '').toLowerCase();
    const path = parsed.pathname.toLowerCase();
    const profileTokens = ['/in/', '/people/', '/person/', '/staff/', '/team/', '/profile/', '/users/', '/~', '/pub/', '/author'];
    const hostTokens = ['orcid.org', 'researchgate.net', 'scholar.google.com'];
    if (hostTokens.some(t => host.includes(t))) return true;
    if (profileTokens.some(t => path.includes(t))) return true;
    return false;
  } catch {
    return false;
  }
}

export function LeadFinder() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Lead[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Google auth/profile state
  const [profile, setProfile] = useState<any | null>(null);
  // If the user pressed "Export to Google Sheets" but wasn't logged in, we set this
  // flag to true and start the auth flow; once the popup completes we'll resume export.
  const [pendingSheetExport, setPendingSheetExport] = useState(false);

  // Progress bar state (simulated while backend request is running)
  const [progress, setProgress] = useState<number>(0);
  const progressTimerRef = useRef<number | null>(null);

  // Settings
  const [maxResults, setMaxResults] = useState<number>(200);
  const [domains, setDomains] = useState<string>("pubmed,linkedin");
  const [pubmedChecked, setPubmedChecked] = useState<boolean>(true);
  const [linkedinChecked, setLinkedinChecked] = useState<boolean>(true);
  const [customDomains, setCustomDomains] = useState<string>("");
  const [activeTab, setActiveTab] = useState<'search' | 'settings'>('search');

  useEffect(() => {
    // Load settings from localStorage
    const savedMaxResults = localStorage.getItem('maxResults');
    if (savedMaxResults) {
      setMaxResults(parseInt(savedMaxResults, 10));
    }
    const savedDomains = localStorage.getItem('domains');
    const savedCustomDomains = localStorage.getItem('customDomains');
    if (savedCustomDomains) {
      setCustomDomains(savedCustomDomains);
    }
    if (savedDomains) {
      setDomains(savedDomains);
      setPubmedChecked(savedDomains.includes('pubmed'));
      setLinkedinChecked(savedDomains.includes('linkedin'));
    } else {
      // Set default domains including custom ones
      const defaultDomains = ['pubmed', 'linkedin'];
      if (savedCustomDomains) {
        defaultDomains.push(...savedCustomDomains.split(',').map(d => d.trim()).filter(d => d));
      }
      const domainStr = defaultDomains.join(',');
      setDomains(domainStr);
      setPubmedChecked(true);
      setLinkedinChecked(true);
    }

    // Listen for the popup message from the OAuth callback window
    const handler = (e: MessageEvent) => {
      try {
        const data = e.data;
        if (data && data.success && data.profile) {
          setProfile(data.profile);
          // If we were waiting to export to sheets, continue the export now
          if (pendingSheetExport) {
            setPendingSheetExport(false);
            void doGoogleSheetExport();
          }
        }
      } catch (err) {
        // ignore
      }
    };

    window.addEventListener("message", handler);

    // On mount, check existing session
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/auth/session`);
        if (r.ok) {
          const j = await r.json();
          if (j.logged_in) setProfile(j.profile);
        }
      } catch (err) {
        // ignore
      }
    })();

    return () => {
      window.removeEventListener("message", handler);
      if (progressTimerRef.current) {
        clearInterval(progressTimerRef.current);
        progressTimerRef.current = null;
      }
      // Close any open SSE connection
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  function openGoogleAuth() {
    const popup = window.open(`${API_BASE}/auth/google`, 'google_oauth', 'width=500,height=600');
    // Poll the popup to close and then refresh session
    const tid = setInterval(async () => {
      if (!popup || popup.closed) {
        clearInterval(tid);
        try {
          const r = await fetch(`${API_BASE}/auth/session`);
          if (r.ok) {
            const j = await r.json();
            if (j.logged_in) setProfile(j.profile);
          }
        } catch (err) {}
      }
    }, 500);
  }

  async function logout() {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
    setProfile(null);
  }

  // Start a simulated progress animation while a long-running request is in progress
  const startProgress = () => {
    setProgress(3);
    if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    progressTimerRef.current = window.setInterval(() => {
      setProgress((p) => {
        if (p >= 90) return p;
        const inc = Math.floor(Math.random() * 10) + 5;
        return Math.min(90, p + inc);
      });
    }, 500);
  };

  const stopProgress = () => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    setProgress(100);
    // Reset after a short delay so the UI shows completion briefly
    setTimeout(() => setProgress(0), 700);
  };

  const esRef = useRef<EventSource | null>(null);

  const search = async () => {
    setLoading(true);
    setError(null);
    setResults([]);
    setProgress(0);

    // Prefer SSE streaming if available
    if (typeof window !== 'undefined' && 'EventSource' in window) {
      const esUrl = `${API_BASE}/scrape/stream?input=${encodeURIComponent(query)}&max_results=${maxResults}&domains=${encodeURIComponent(domains)}`;
      try {
        if (esRef.current) {
          esRef.current.close();
          esRef.current = null;
        }
        const es = new EventSource(esUrl);
        esRef.current = es;

        // Debug hooks to help diagnose progress streaming issues
        es.onopen = () => {
          console.debug('SSE connection opened for', esUrl);
        };

        es.onmessage = (ev) => {
          // log raw payload to help diagnose parse / format issues
          console.debug('SSE raw message:', ev.data);
          try {
            const data = JSON.parse(ev.data);
            console.debug('SSE parsed message:', data);
            if (data.type === 'progress') {
              setProgress(typeof data.percent === 'number' ? data.percent : 0);
            } else if (data.type === 'search_results') {
              // Merge incoming search hit candidates into results, avoiding duplicates by URL
              // Detect profile-like URLs (not just LinkedIn) and populate `profile_url` when appropriate.
              const incoming = (data.results || []).map((r: any) => ({
                url: r.href || r.url || '',
                title: r.title || r.name || '',
                linkedin_url: isLinkedInProfileUrl(r.href || r.url) ? (r.href || r.url) : '',
                profile_url: isProfileUrl(r.href || r.url) ? (r.href || r.url) : '',
              }));
              setResults((prev) => {
                const seen = new Set(prev.map((p) => p.url));
                const merged = [...prev];
                for (const item of incoming) {
                  if (item.url && !seen.has(item.url)) {
                    merged.push(item);
                    seen.add(item.url);
                  }
                }
                return merged;
              });
            } else if (data.type === 'item') {
              setProgress(typeof data.percent === 'number' ? data.percent : 0);
              setResults((prev) => {
                // Avoid duplicating a previously-added search result: replace if same url
                const itemUrl = data.item.url || data.item.href || '';
                // populate profile_url for any profile-like links and linkedin_url for LinkedIn specifically
                if (itemUrl && !data.item.profile_url && isProfileUrl(itemUrl)) {
                  data.item.profile_url = itemUrl;
                }
                if (itemUrl && !data.item.linkedin_url && isLinkedInProfileUrl(itemUrl)) {
                  data.item.linkedin_url = itemUrl;
                }
                if (!itemUrl) return [...prev, data.item];
                const idx = prev.findIndex((p) => p.url === itemUrl);
                if (idx !== -1) {
                  const copy = [...prev];
                  copy[idx] = { ...copy[idx], ...data.item };
                  return copy;
                }
                return [...prev, data.item];
              });
            } else if (data.type === 'done') {
              setProgress(100);
              // final results may be included
              if (Array.isArray(data.results)) setResults(data.results);
              setLoading(false);
              // keep the completion visible briefly
              setTimeout(() => setProgress(0), 700);
              es.close();
              esRef.current = null;
            } else if (data.type === 'error') {
              const base = data.msg || 'Error during scrape';
              const where = data.url ? ` at ${data.url}` : '';
              const phase = data.phase ? ` (${data.phase})` : '';
              setError(`${base}${where}${phase}`);
              setLoading(false);
              es.close();
              esRef.current = null;
            }
          } catch (e) {
            console.error('Failed to parse SSE data', e, ev.data);
          }
        };

        es.onerror = (ev) => {
          console.error('SSE connection error', ev);
          setError('Connection error while streaming progress');
          setLoading(false);
          if (esRef.current) {
            esRef.current.close();
            esRef.current = null;
          }
        };

        return; // we're streaming; exit early
      } catch (e) {
        console.warn('SSE failed, falling back to fetch:', e);
        // fallback to previous fetch-based approach below
      }
    }

    // Fallback: fetch single response and use simulated progress
    startProgress();
    try {
      const res = await fetch(`${API_BASE}/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: query }),
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      // expect data.results to be an array of processed leads
      setResults(data.results || []);
    } catch (err: any) {
      setError(String(err));
    } finally {
      setLoading(false);
      stopProgress();
    }
  };

  // Perform the actual export assuming the user is authenticated
  const doGoogleSheetExport = async () => {
    try {
      await fetch(`${API_BASE}/export/sheets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows: results.map(r => [r.rank, r.title, r.url, r.email, r.phone, r.linkedin_url, r.location_hq]) })
      });
    } catch (e) {
      console.log(`/export/sheets endpoint got an error with ${e}`);
      setError(String(e));
    }
  };

  // Public handler called when the "Export to Google Sheets" button is pressed.
  // If the user is not logged in, start the Google auth flow and remember the intent.
  const googleSheetExport = async () => {
    if (!results.length) return;
    if (!profile) {
      // set flag so we continue export after login completes
      setPendingSheetExport(true);
      openGoogleAuth();
      return;
    }
    await doGoogleSheetExport();
  };

  const exportCSV = () => {
    if (!results.length) return;
    const headers = ["rank", "title", "url", "email", "phone", "linkedin_url", "location_hq"];
    const rows = results.map((r) => [
      (r.rank ?? ""),
      (r.title ?? ""),
      (r.url ?? ""),
      (r.email ?? ""),
      (r.phone ?? ""),
      (r.linkedin_url ?? ""),
      (r.location_hq ?? ""),
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leads-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Reset the entire UI state (query, results, filters, errors, progress)
  const resetAll = () => {
    setQuery("");
    setResults([]);
    setFilter("");
    setError(null);
    setProgress(0);
    setLoading(false);
    setPendingSheetExport(false);
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  };

  const callProcess = async (lead: Lead) => {
    try {
      const res = await fetch(`${API_BASE}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: lead }),
      });
      const newLead = await res.json();
      // merge processed fields back into results
      setResults((prev) => prev.map((r) => (r === lead ? { ...r, ...newLead } : r)));
    } catch (err) {
      console.error(err);
      setError(String(err));
    }
  };

  const filtered = results.filter((r) => {
    if (!filter) return true;
    const hay = [r.title, r.url, r.email, r.phone, r.linkedin_url, r.location_hq].join(" ")
      .toLowerCase();
    return hay.includes(filter.toLowerCase());
  });

  return (
    <div className="lead-finder">
      <div className="lead-card">
        <header className="lead-card-header">
          <div>
            <h1>Lead Finder</h1>
            <p className="subtitle">Search and enrich leads from the backend</p>
          </div>
          <div className="header-actions">
            <button type="button" className="btn btn-ghost small reset-card-btn" onClick={resetAll} aria-label="Reset all" title="Reset all">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d="M21 12a9 9 0 1 0-3.3 6.3"></path><polyline points="21 12 21 6 15 6"></polyline></svg>
            </button>
            {profile ? (
              <div className="auth-row">
                {profile.picture && <img src={profile.picture} alt="avatar" className="avatar" />}
                <span className="auth-name">{profile.name || profile.email}</span>
                <button className="btn btn-ghost" onClick={logout}>Logout</button>
              </div>
            ) : (
              // No login button shown here; login will be initiated from the Export to Google Sheets action
              null
            )}
          </div> 
        </header>

        <div className="tabs">
          <button className={`tab-btn ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}>Search</button>
          <button className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>Settings</button>
        </div>

        {activeTab === 'search' && (
          <div className="search-content">
            <SearchBar query={query} setQuery={setQuery} onSearch={search} loading={loading} exportCSV={exportCSV} exportSheets={googleSheetExport} onReset={resetAll} />

            <ProgressBar progress={progress} />

            {error && <div className="error">{error}</div>}
            {pendingSheetExport && <div className="info">Please complete Google login in the popup to finish exporting to Google Sheets...</div>}

            <ResultsTable results={results} filter={filter} setFilter={setFilter} callProcess={callProcess} />

            <div className="card-footer">
              <div className="left-footer">
                <span className="result-summary">{results.length} leads</span>
              </div>
              <div className="right-footer">
                <button className="btn btn-ghost" onClick={exportCSV} disabled={!results.length}>Export CSV</button>
                <button className="btn btn-ghost" onClick={googleSheetExport} disabled={!results.length}>Export to Google Sheets</button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="settings">
            <h2>Settings</h2>
            <div className="setting-item">
              <label htmlFor="maxResults">Max Results:</label>
              <input
                id="maxResults"
                type="number"
                value={maxResults}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  setMaxResults(val);
                  localStorage.setItem('maxResults', val.toString());
                }}
                min="1"
                max="1000"
              />
              <p>Maximum number of leads to fetch and process (default: 200).</p>
            </div>
            <div className="setting-item">
              <label>Search Domains:</label>
              <label>
                <input
                  type="checkbox"
                  checked={pubmedChecked}
                  onChange={(e) => {
                    setPubmedChecked(e.target.checked);
                    const newDomains = [];
                    if (e.target.checked) newDomains.push('pubmed');
                    if (linkedinChecked) newDomains.push('linkedin');
                    if (customDomains) {
                      newDomains.push(...customDomains.split(',').map(d => d.trim()).filter(d => d));
                    }
                    const domainStr = newDomains.join(',');
                    setDomains(domainStr);
                    localStorage.setItem('domains', domainStr);
                  }}
                />
                PubMed
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={linkedinChecked}
                  onChange={(e) => {
                    setLinkedinChecked(e.target.checked);
                    const newDomains = [];
                    if (pubmedChecked) newDomains.push('pubmed');
                    if (e.target.checked) newDomains.push('linkedin');
                    if (customDomains) {
                      newDomains.push(...customDomains.split(',').map(d => d.trim()).filter(d => d));
                    }
                    const domainStr = newDomains.join(',');
                    setDomains(domainStr);
                    localStorage.setItem('domains', domainStr);
                  }}
                />
                LinkedIn
              </label>
              <div style={{ marginTop: '10px' }}>
                <label htmlFor="customDomains" style={{ display: 'block', marginBottom: '5px' }}>Additional Domains:</label>
                <input
                  id="customDomains"
                  type="text"
                  value={customDomains}
                  onChange={(e) => {
                    const value = e.target.value;
                    setCustomDomains(value);
                    localStorage.setItem('customDomains', value);
                    
                    // Update domains string
                    const newDomains = [];
                    if (pubmedChecked) newDomains.push('pubmed');
                    if (linkedinChecked) newDomains.push('linkedin');
                    if (value) {
                      newDomains.push(...value.split(',').map(d => d.trim()).filter(d => d));
                    }
                    const domainStr = newDomains.join(',');
                    setDomains(domainStr);
                    localStorage.setItem('domains', domainStr);
                  }}
                  placeholder="e.g., researchgate.net, orcid.org"
                  style={{ width: '100%', padding: '5px' }}
                />
              </div>
              <p>Select domains to search for leads (default: both). Add custom domains separated by commas.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default LeadFinder;
