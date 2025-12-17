import React, { useState, useEffect } from "react";

// API base: during dev the frontend runs on port 3000 and backend on 8000
const API_BASE = ((): string => {
  if (typeof window === 'undefined') return '';
  const host = window.location.hostname;
  const port = window.location.port;
  // when developing with the frontend dev server on 3000, point to backend on 8000
  if (host === 'localhost' && port === '3000') return 'http://localhost:8000';
  return '';
})();

type Lead = {
  email?: string;
  phone?: string;
  linkedin_url?: string;
  location_hq?: string;
  rank?: number;
  title?: string;
  url?: string;
  all_emails?: string[];
  all_phones?: string[];
  all_linkedin?: string[];
};

export function LeadFinder() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Lead[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Google auth/profile state
  const [profile, setProfile] = useState<any | null>(null);

  useEffect(() => {
    // Listen for the popup message from the OAuth callback window
    const handler = (e: MessageEvent) => {
      try {
        const data = e.data;
        if (data && data.success && data.profile) {
          setProfile(data.profile);
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

    return () => window.removeEventListener("message", handler);
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

  const search = async () => {
    setLoading(true);
    setError(null);
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
    }
  };

  const googleSheetExport=async ()=>{
    try{
  await fetch(`${API_BASE}/export/sheets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows: results.map(r => [r.rank, r.title, r.url, r.email, r.phone, r.linkedin_url, r.location_hq]) })
  });}
  catch(e){
    console.log(` /export/sheets endpoint got an error with ${e}`)
  }
}

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
      <div className="search-row">
        <input
          className="search-input"
          placeholder="Enter search query (e.g., site:pfizer.com toxicology 3D in vitro)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="search-button" onClick={search} disabled={loading || !query.trim()}>
          {loading ? "Searching..." : "Search"}
        </button>
        <button className="export-button" onClick={exportCSV} disabled={!results.length}>
          Export CSV
        </button>
      </div>
      <div className="filter-row">
        <input className="filter-input" placeholder="Filter results" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>

      {error && <div className="error">{error}</div>}

      <div className="table-wrap">
        <table className="results-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Title</th>
              <th>URL</th>
              <th>Email</th>
              <th>Phone</th>
              <th>LinkedIn</th>
              <th>Location</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={i}>
                <td>{r.rank ?? ""}</td>
                <td>{r.title}</td>
                <td>
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noreferrer">
                      link
                    </a>
                  ) : (
                    ""
                  )}
                </td>
                <td>{r.email}</td>
                <td>{r.phone}</td>
                <td>
                  {r.linkedin_url ? (
                    <a href={r.linkedin_url} target="_blank" rel="noreferrer">
                      profile
                    </a>
                  ) : (
                    ""
                  )}
                </td>
                <td>{r.location_hq}</td>
                <td>
                  <button onClick={() => callProcess(r)} className="process-button">
                    Re-process
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={exportCSV} disabled={!results.length}>
          Export CSV
        </button>

        {profile ? (
          <div className="auth-row">
            {profile.picture && <img src={profile.picture} alt="avatar" style={{ width: 32, height: 32, borderRadius: 16, marginRight: 8 }} />}
            <span style={{ marginRight: 8 }}>{profile.name || profile.email}</span>
            <button onClick={logout}>Logout</button>
          </div>
        ) : (
          <button onClick={openGoogleAuth}>Login with Google</button>
        )}

        <button onClick={googleSheetExport} disabled={!results.length}>
          Export to Google Sheets
        </button>
    </div>
  );
}

export default LeadFinder;
