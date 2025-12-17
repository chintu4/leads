import unittest
import requests as rq

# ==========================================
# PART 1: The Logic Being Tested
# (Ideally, you import this from your app, e.g., `from logic import calculate_score`)
# ==========================================

def calculate_lead_score(lead_data):
    """
    Calculates the 'Propensity to Buy' score (0-100) based on Assignment Page 2-3.
    """
    score = 0
    title = lead_data.get("title", "").lower()
    
    # [cite_start]1. Role Fit (+30) [cite: 30]
    if any(x in title for x in ["toxicology", "safety", "hepatic", "3d"]):
        score += 30
        
    # [cite_start]2. Scientific Intent (+40) [cite: 45-49]
    if lead_data.get("published_recent_paper"):
        score += 40
        
    # [cite_start]3. Company Intent (+20) [cite: 32]
    if lead_data.get("funding_series") in ["A", "B"]:
        score += 20
        
    # [cite_start]4. Location (+10) [cite: 39]
    hubs = ["Boston", "Cambridge", "Bay Area", "Basel", "UK Golden Triangle"]
    if any(hub in lead_data.get("location", "") for hub in hubs):
        score += 10
        
    return min(score, 100) # Cap at 100

# ==========================================
# PART 2: The Test Suite
# ==========================================

URL = "http://localhost:8000"

class TestLeadGenSystem(unittest.TestCase):

    # --- INTEGRATION TESTS (Requires running server) ---
    
    def test_01_server_status(self):
        """Check if the web agent is running."""
        try:
            response = rq.get(URL + '/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})
            print("\n[Pass] Server is online.")
        except rq.exceptions.ConnectionError:
            self.fail("Server is NOT running. Please start your agent on port 8000.")

    def test_02_scrape_identification(self):
        """
        Tests Stage 1: Identification.
        Sends a keyword and checks if the agent returns relevant biological terms.
        """
        body = {"input": "3D in-vitro models"}
        
        # We assume your API has a '/scrape' endpoint
        response = rq.post(URL + "/scrape", json=body)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Look for relevant keywords in the response; accept 'fields' list or any part of the payload
        # [cite_start]Verify specific keywords from the assignment [cite: 92, 93]
        expected_keywords = [
            "3D cell cultures", 
            "Organoids", 
            "Microfluidic systems", 
            "Director of Toxicology",
            "Drug-Induced Liver Injury"
        ]

        search_space = []
        if isinstance(data.get("fields"), list):
            search_space = data.get("fields")
        else:
            # fall back to scanning all values and the whole response
            search_space = [str(v) for v in data.values()] + [str(data)]

        # Ensure at least one expected keyword was found
        found_keywords = [k for k in expected_keywords if any(k in str(s) for s in search_space)]
        self.assertTrue(len(found_keywords) > 0, "No relevant biology keywords found in response.")
        print(f"[Pass] Identification returned valid keywords: {found_keywords}")

    def test_03_enrichment_output_structure(self):
        """
        Tests Stage 2: Enrichment.
        Checks if the output contains the required columns (Email, Phone, Location).
        """
        # Send an object for 'response' (Pydantic expects an object/dict)
        body = {"response": {}, "ok": "", "wow": ""}
        
        response = rq.post(URL + "/process", json=body)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # [cite_start]Assignment requires specific fields for the dashboard [cite: 56]
        required_fields = ["email", "phone", "linkedin_url", "location_hq","rank"]
        
        # Verify the JSON structure contains these keys (even if empty)
        for field in required_fields:
            self.assertIn(field, data)
        print("[Pass] Output structure contains all required dashboard columns.")

    # --- UNIT TESTS (Pure Logic - No Server Needed) ---

    def test_04_ranking_logic_high_score(self):
        """
        Tests Stage 3: Ranking Logic for a High Value Target.
        [cite_start]Example: Director of Safety at Series B company in Cambridge[cite: 52].
        """
        high_value_lead = {
            "title": "Director of Safety Assessment", # Matches 'Safety' (+30)
            "funding_series": "B",                    # Matches Series B (+20)
            "published_recent_paper": True,           # Matches Paper (+40)
            "location": "Cambridge, MA"               # Matches Hub (+10)
        }
        
        score = calculate_lead_score(high_value_lead)
        self.assertEqual(score, 100, "High value lead did not score 100/100")
        print(f"[Pass] High Value Lead scored: {score}")

    def test_05_ranking_logic_low_score(self):
        """
        Tests Stage 3: Ranking Logic for a Low Value Target.
        [cite_start]Example: Junior Scientist at non-funded startup[cite: 51].
        """
        low_value_lead = {
            "title": "Junior Scientist",    # No match
            "funding_series": "None",       # No match
            "published_recent_paper": False,# No match
            "location": "Texas"             # No match
        }
        
        score = calculate_lead_score(low_value_lead)
        self.assertLess(score, 20, "Low value lead scored too high!")
        print(f"[Pass] Low Value Lead scored: {score}")

if __name__ == '__main__':
    unittest.main()