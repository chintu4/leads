
import LeadFinder from "./LeadFinder";
import "./index.css";



export function App() {
  return (
    <div className="app">
      <div className="logo-container">
        
      </div>

      <h1>Lead Finder</h1>
      <p>
        Use this UI to search and enrich leads from the backend. Edit <code>src/LeadFinder.tsx</code> to customize.
      </p>

      <LeadFinder />

      <hr style={{ margin: "2rem 0" }} />

      
      
    </div>
  );
}

export default App;
