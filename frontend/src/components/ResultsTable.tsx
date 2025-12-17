import React from "react";
import type { Lead } from "../LeadFinder";

type Props = {
  results: Lead[];
  filter: string;
  setFilter: (v: string) => void;
  callProcess: (lead: Lead) => void;
};

export default function ResultsTable({ results, filter, setFilter, callProcess }: Props) {
  const filtered = results.filter((r) => {
    if (!filter) return true;
    const hay = [r.title, r.url, r.email, r.phone, r.linkedin_url, r.location_hq].join(" ")
      .toLowerCase();
    return hay.includes(filter.toLowerCase());
  });

  return (
    <div>
      <div className="filter-row">
        <input className="filter-input" placeholder="Filter results" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <div className="result-count">{filtered.length} results</div>
      </div>

      {filtered.length === 0 ? (
        <div className="no-results">No results yet — try running a search.</div>
      ) : (
        <div className="table-wrap">
          <table className="results-table">
            <thead>
              <tr>
                <th>Site</th>
                <th>Rank</th>
                <th>Title</th>
                <th>URL</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Profile</th>
                <th>Location</th>
                <th>Error</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => {
                const getHostname = (u?: string) => {
                  try {
                    if (!u) return '';
                    const parsed = new URL(u);
                    return parsed.hostname;
                  } catch (e) {
                    return '';
                  }
                };
                const hostname = getHostname(r.url);
                const ddgFavicon = hostname ? `https://icons.duckduckgo.com/ip3/${hostname}.ico` : '';
                const googleFavicon = hostname ? `https://www.google.com/s2/favicons?domain=${hostname}&sz=64` : '';
                const placeholder = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" rx="8" fill="%233b2a20"/><text x="50%" y="50%" font-size="18" text-anchor="middle" fill="%23f6efe6" dy="6">?</text></svg>';

                const primaryLink = r.linkedin_url || r.url;

                return (
                  <tr key={i} className={i % 2 === 0 ? "row-even" : "row-odd"}>
                    <td className="col-site">
                      {hostname ? (
                        <img
                          src={ddgFavicon}
                          alt={hostname}
                          className="favicon"
                          onError={(e) => {
                            const img = e.target as HTMLImageElement;
                            if (googleFavicon && img.src !== googleFavicon) {
                              img.src = googleFavicon;
                            } else {
                              img.src = placeholder;
                            }
                          }}
                        />
                      ) : (
                        <img src={placeholder} alt="site" className="favicon" />
                      )}
                    </td>
                    <td className="col-rank">{r.rank ?? ""}</td>
                    <td className="col-title">{r.title}</td>
                    <td className="col-url">{primaryLink ? <a href={primaryLink} target="_blank" rel="noreferrer">link</a> : ""}</td>
                    <td className="col-email">{r.email}</td>
                    <td className="col-phone">{r.phone}</td>
                    <td className="col-profile">{(r.profile_url || r.linkedin_url) ? <a href={r.profile_url || r.linkedin_url} target="_blank" rel="noreferrer">profile</a> : ""}</td>
                    <td className="col-location">{r.location_hq}</td>
                    <td className="col-error">{r.error ? <span className="error">{r.error}</span> : ""}</td>
                    <td className="col-action">
                      <button onClick={() => callProcess(r)} className="btn btn-ghost small">
                        Re-process
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
