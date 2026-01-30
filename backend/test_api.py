"""
Insurance LLM API Test Suite
Tests all API endpoints with realistic insurance document samples
"""

import requests
import json
from dataclasses import dataclass
from typing import Optional

BASE_URL = "http://localhost:8081"

# Test Documents
MESSY_COI_EMAIL = """fwd: insurance stuff

hey can u check this out? their coverage looks weird to me lol

---
CERTIFICATE OF LIABILITY INSURANCE
Insured: Artisanal Pickle Co LLC
Policy#: BOP-2024-88821
Carrier: Midwest Mutual Insurance
Eff: 1/15/24 - 1/15/25

GL: $1M per occ / $2M agg
Prod/Comp: $1M
Med Pay: $5k
Damage to Rented: $100k
deductible $2,500

also they have:
- Umbrella: $5M (policy UMB-441)
- Workers comp as required

exclusions: no coverage for fermentation explosions (weird right??)
special endorsement for food spoilage added 3/2024

premium total: $4,250/yr

let me know thx
-mike"""

COMMERCIAL_PROPERTY_QUOTE = """COMMERCIAL PROPERTY QUOTE
=========================

Prepared for: Brooklyn Roasting Company
Date: November 12, 2024
Quote #: CPQ-2024-1182

PROPOSED COVERAGE:
------------------
Building Coverage.............$2,500,000
Business Personal Property....$750,000
Business Income..............$500,000
Equipment Breakdown...........$250,000

Deductible: $5,000 / $25,000 wind/hail

ANNUAL PREMIUM: $12,400

Coverage Notes:
* Agreed value endorsement included
* Ordinance & law 25%
* NO flood coverage - Zone X requires separate
* Coffee roasting equipment schedule attached

Quoted by: Hartford Commercial Lines
Valid thru: 12/15/2024

[signature illegible]"""

POLICY_RENEWAL_NOTICE = """*** RENEWAL NOTICE ***

Dear Valued Policyholder,

Your policy is due for renewal:

Named Insured: Fixie Bike Repair & Custom Frames
                dba "Spoke & Chain"
Policy Number: CGL-NY-2023-44891
Current Term: Feb 1 2024 to Feb 1 2025

RENEWAL TERM CHANGES:
- Premium increase: $3,200 -> $3,850 (+20%)
- General Liability limit: $1M/$2M (unchanged)
- Professional Liability: ADDING $500k sublimit (new)
- Tools & Equipment floater: $75,000

IMPORTANT: Your current product liability sublimit of $500,000
will be REDUCED to $250,000 unless you opt for enhanced
coverage (+$400/yr).

Deductible remains $1,000.

EXCLUSIONS ADDED THIS TERM:
- E-bike battery fires
- Carbon fiber frame defects over $10k

Please respond by January 15, 2025.

Questions? Call 1-800-555-BIKE

Underwritten by: Velocity Insurance Group"""

MINIMAL_DOCUMENT = """Policy for John Smith. GL coverage $500k."""

EMPTY_DOCUMENT = ""

GIBBERISH_DOCUMENT = """asdfkjhasdf 12938471 !!!@@@###
no real insurance info here just noise
random words: banana helicopter submarine"""


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    response_data: Optional[dict] = None


class InsuranceLLMTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: list[TestResult] = []

    def run_all_tests(self):
        """Run all test cases"""
        print("\n" + "=" * 60)
        print("INSURANCE.EXE API TEST SUITE")
        print("=" * 60 + "\n")

        # Health & Connectivity Tests
        self.test_health_check()

        # Extraction Tests
        self.test_extract_messy_coi()
        self.test_extract_property_quote()
        self.test_extract_renewal_notice()
        self.test_extract_minimal_document()
        self.test_extract_empty_document()
        self.test_extract_gibberish()

        # Proposal Generation Tests
        self.test_generate_proposal()

        # Edge Cases
        self.test_invalid_json_payload()
        self.test_missing_text_field()

        # Print Summary
        self.print_summary()

        return self.results

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> tuple[int, dict]:
        """Make HTTP request and return status code and response"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=60)
            elif method == "POST":
                resp = requests.post(url, json=data, timeout=60)
            return resp.status_code, resp.json() if resp.text else {}
        except requests.exceptions.ConnectionError:
            return 0, {"error": "Connection refused - is the server running?"}
        except requests.exceptions.Timeout:
            return 0, {"error": "Request timed out"}
        except json.JSONDecodeError:
            return resp.status_code, {"error": "Invalid JSON response", "raw": resp.text[:500]}

    def _add_result(self, name: str, passed: bool, message: str, data: dict = None):
        """Add a test result"""
        result = TestResult(name, passed, message, data)
        self.results.append(result)
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            print(f"       {message}")
        if data and not passed:
            print(f"       Response: {json.dumps(data, indent=2)[:200]}...")

    # ==================== HEALTH TESTS ====================

    def test_health_check(self):
        """Test that the API is running and responding"""
        status, data = self._make_request("GET", "/")

        if status == 0:
            self._add_result("Health Check", False, data.get("error", "Unknown error"))
            return

        passed = status == 200 and "status" in data
        self._add_result(
            "Health Check",
            passed,
            f"Expected status 200 with 'status' field, got {status}" if not passed else "API is healthy",
            data
        )

    # ==================== EXTRACTION TESTS ====================

    def test_extract_messy_coi(self):
        """Test extraction from a messy forwarded COI email"""
        status, data = self._make_request("POST", "/api/extract", {"text": MESSY_COI_EMAIL})

        if status == 0:
            self._add_result("Extract Messy COI", False, data.get("error", "Connection failed"))
            return

        # Validate response structure
        checks = []

        # Must have insured name
        if data.get("insured_name"):
            checks.append(("insured_name", "Artisanal Pickle" in data["insured_name"]))
        else:
            checks.append(("insured_name", False))

        # Must have policy number
        if data.get("policy_number"):
            checks.append(("policy_number", "BOP-2024-88821" in data["policy_number"]))
        else:
            checks.append(("policy_number", False))

        # Must have carrier
        if data.get("carrier"):
            checks.append(("carrier", "Midwest" in data["carrier"]))
        else:
            checks.append(("carrier", False))

        # Must have coverages array
        checks.append(("coverages", isinstance(data.get("coverages"), list) and len(data.get("coverages", [])) > 0))

        # Must have exclusions mentioning fermentation
        exclusions = data.get("exclusions", [])
        has_fermentation = any("ferment" in str(e).lower() for e in exclusions)
        checks.append(("exclusions_fermentation", has_fermentation))

        # Must have premium
        checks.append(("premium", data.get("total_premium") is not None))

        # Must have risk score between 1-100
        risk = data.get("risk_score")
        checks.append(("risk_score", risk is not None and 1 <= risk <= 100))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Messy COI",
            passed,
            f"Failed checks: {failed}" if not passed else "All fields extracted correctly",
            data
        )

    def test_extract_property_quote(self):
        """Test extraction from a commercial property quote"""
        status, data = self._make_request("POST", "/api/extract", {"text": COMMERCIAL_PROPERTY_QUOTE})

        if status == 0:
            self._add_result("Extract Property Quote", False, data.get("error", "Connection failed"))
            return

        checks = []

        # Must have insured name
        if data.get("insured_name"):
            checks.append(("insured_name", "Brooklyn Roasting" in data["insured_name"]))
        else:
            checks.append(("insured_name", False))

        # Must have coverages with building coverage
        coverages = data.get("coverages", [])
        has_building = any("building" in str(c).lower() for c in coverages)
        checks.append(("building_coverage", has_building))

        # Must identify flood exclusion as compliance issue or in notes
        exclusions = data.get("exclusions", [])
        compliance = data.get("compliance_issues", [])
        all_issues = str(exclusions) + str(compliance) + str(data.get("summary", ""))
        has_flood_note = "flood" in all_issues.lower()
        checks.append(("flood_exclusion_noted", has_flood_note))

        # Must have premium of $12,400
        premium = str(data.get("total_premium", ""))
        checks.append(("premium", "12" in premium and "400" in premium))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Property Quote",
            passed,
            f"Failed checks: {failed}" if not passed else "Property quote extracted correctly",
            data
        )

    def test_extract_renewal_notice(self):
        """Test extraction from a policy renewal notice"""
        status, data = self._make_request("POST", "/api/extract", {"text": POLICY_RENEWAL_NOTICE})

        if status == 0:
            self._add_result("Extract Renewal Notice", False, data.get("error", "Connection failed"))
            return

        checks = []

        # Must have policy number
        if data.get("policy_number"):
            checks.append(("policy_number", "CGL-NY-2023-44891" in data["policy_number"]))
        else:
            checks.append(("policy_number", False))

        # Must have carrier
        if data.get("carrier"):
            checks.append(("carrier", "Velocity" in data["carrier"]))
        else:
            checks.append(("carrier", False))

        # Must identify e-bike exclusion
        exclusions = data.get("exclusions", [])
        has_ebike = any("e-bike" in str(e).lower() or "ebike" in str(e).lower() or "battery" in str(e).lower() for e in exclusions)
        checks.append(("ebike_exclusion", has_ebike))

        # Should flag premium increase as notable
        premium = str(data.get("total_premium", ""))
        checks.append(("premium", "3" in premium and "850" in premium))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Renewal Notice",
            passed,
            f"Failed checks: {failed}" if not passed else "Renewal notice extracted correctly",
            data
        )

    def test_extract_minimal_document(self):
        """Test extraction from a minimal document with very little info"""
        status, data = self._make_request("POST", "/api/extract", {"text": MINIMAL_DOCUMENT})

        if status == 0:
            self._add_result("Extract Minimal Doc", False, data.get("error", "Connection failed"))
            return

        # Should still return valid structure even with minimal data
        checks = []
        checks.append(("has_structure", "coverages" in data))
        checks.append(("coverages_is_list", isinstance(data.get("coverages"), list)))

        # Should extract "John Smith" as insured
        if data.get("insured_name"):
            checks.append(("insured_name", "John Smith" in data["insured_name"]))

        # Should extract GL coverage
        coverages = data.get("coverages", [])
        has_gl = any("500" in str(c) or "liability" in str(c).lower() for c in coverages)
        checks.append(("gl_coverage", has_gl or len(coverages) > 0))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Minimal Doc",
            passed,
            f"Failed checks: {failed}" if not passed else "Minimal doc handled gracefully",
            data
        )

    def test_extract_empty_document(self):
        """Test that empty document returns appropriate error or empty structure"""
        status, data = self._make_request("POST", "/api/extract", {"text": EMPTY_DOCUMENT})

        # Either a 400 error OR an empty but valid structure is acceptable
        if status == 400:
            self._add_result("Extract Empty Doc", True, "Correctly rejected empty document")
            return

        if status == 0:
            self._add_result("Extract Empty Doc", False, data.get("error", "Connection failed"))
            return

        # If 200, should have empty/null fields but valid structure
        checks = []
        checks.append(("has_structure", "coverages" in data))
        checks.append(("coverages_empty_or_list", data.get("coverages") is None or isinstance(data.get("coverages"), list)))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Empty Doc",
            passed,
            f"Failed checks: {failed}" if not passed else "Empty doc handled gracefully",
            data
        )

    def test_extract_gibberish(self):
        """Test that gibberish document doesn't crash and returns valid structure"""
        status, data = self._make_request("POST", "/api/extract", {"text": GIBBERISH_DOCUMENT})

        if status == 0:
            self._add_result("Extract Gibberish", False, data.get("error", "Connection failed"))
            return

        # Should return valid structure even if fields are empty/null
        checks = []
        checks.append(("status_ok", status == 200))
        checks.append(("has_structure", "coverages" in data))
        checks.append(("no_crash", True))  # If we got here, it didn't crash

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Extract Gibberish",
            passed,
            f"Failed checks: {failed}" if not passed else "Gibberish handled gracefully",
            data
        )

    # ==================== PROPOSAL TESTS ====================

    def test_generate_proposal(self):
        """Test proposal generation from extracted data"""
        # First extract a document
        _, extracted = self._make_request("POST", "/api/extract", {"text": MESSY_COI_EMAIL})

        if not extracted or "coverages" not in extracted:
            self._add_result("Generate Proposal", False, "Could not extract document first")
            return

        # Now generate proposal
        status, data = self._make_request("POST", "/api/generate-proposal", extracted)

        if status == 0:
            self._add_result("Generate Proposal", False, data.get("error", "Connection failed"))
            return

        checks = []
        checks.append(("status_ok", status == 200))
        checks.append(("has_proposal", "proposal" in data))

        proposal = data.get("proposal", "")
        checks.append(("proposal_not_empty", len(proposal) > 100))

        # Proposal should mention the insured
        checks.append(("mentions_insured", "pickle" in proposal.lower() or "artisanal" in proposal.lower()))

        failed = [c[0] for c in checks if not c[1]]
        passed = len(failed) == 0

        self._add_result(
            "Generate Proposal",
            passed,
            f"Failed checks: {failed}" if not passed else "Proposal generated successfully",
            {"proposal_length": len(proposal), "preview": proposal[:200] + "..."} if proposal else data
        )

    # ==================== ERROR HANDLING TESTS ====================

    def test_invalid_json_payload(self):
        """Test that invalid JSON is handled gracefully"""
        try:
            resp = requests.post(
                f"{self.base_url}/api/extract",
                data="not valid json {{{",
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            # Should return 422 (Unprocessable Entity) for invalid JSON
            passed = resp.status_code == 422
            self._add_result(
                "Invalid JSON Payload",
                passed,
                f"Expected 422, got {resp.status_code}" if not passed else "Invalid JSON rejected correctly"
            )
        except Exception as e:
            self._add_result("Invalid JSON Payload", False, str(e))

    def test_missing_text_field(self):
        """Test that missing required field returns appropriate error"""
        status, data = self._make_request("POST", "/api/extract", {"wrong_field": "test"})

        # Should return 422 for missing required field
        passed = status == 422
        self._add_result(
            "Missing Text Field",
            passed,
            f"Expected 422, got {status}" if not passed else "Missing field rejected correctly",
            data
        )

    # ==================== SUMMARY ====================

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%")

        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        print("\n" + "=" * 60)

        return failed == 0


if __name__ == "__main__":
    tester = InsuranceLLMTester()
    tester.run_all_tests()
