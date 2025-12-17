import React from "react";

type Props = {
  query: string;
  setQuery: (v: string) => void;
  onSearch: () => void;
  loading: boolean;
  exportCSV: () => void;
  exportSheets: () => void;
  onReset?: () => void;
};

export default function SearchBar({ query, setQuery, onSearch, loading, exportCSV, exportSheets, onReset }: Props) {
  return (
    <form className="search-row" onSubmit={(e) => { e.preventDefault(); if (!loading && query.trim()) onSearch(); }}>
      <label htmlFor="lead-query" className="visually-hidden">Search query</label>
      <input
        id="lead-query"
        className="search-input"
        placeholder="Enter search query (e.g., site:pfizer.com toxicology 3D in vitro)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search query"
      />
      <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
        {loading ? "Searching..." : "Search"}
      </button>
      <button type="button" className="btn btn-ghost" onClick={exportCSV} disabled={loading}>
        Export CSV
      </button>
      <button type="button" className="btn btn-ghost" onClick={exportSheets} disabled={loading}>
        Sheets
      </button>
    </form>
  );
}
