"""
Expensive Integration Tests for Insurance LLM

These tests use:
1. Real LLM API calls (requires OPENAI_API_KEY on backend)
2. Browser automation (requires Chrome + extension)

RUN SPARINGLY - each test costs money and time.

By default, tests run against PRODUCTION:
  - Frontend: https://cantheyfuckme.com
  - Backend: https://insurance-llm-production.up.railway.app

Usage:
    # Run real LLM tests against production:
    python test_expensive.py --llm

    # Run browser workflow test against production:
    python test_expensive.py --browser

    # Run all expensive tests:
    python test_expensive.py --all

    # Run against localhost instead:
    LOCAL=1 python test_expensive.py --llm
"""

import requests
import json
import sys
import os
import time

# Default to production; use LOCAL=1 to test against localhost
BASE_URL = os.environ.get("API_URL", "https://insurance-llm-production.up.railway.app")
if os.environ.get("LOCAL"):
    BASE_URL = "http://localhost:8081"

# Sample documents for testing
GYM_CONTRACT = """PLANET FITNESS MEMBERSHIP AGREEMENT

Member: John Smith
Location: Brooklyn, NY

MONTHLY DUES: $22.99
ANNUAL FEE: $49.99

CANCELLATION: Must visit club in person or send certified mail.
Notice must be received by the 10th to stop billing on the 17th.

ARBITRATION: All disputes shall be resolved through binding arbitration.
Member waives the right to participate in class actions.

AUTO-RENEWAL: This membership automatically renews month-to-month."""

INFLUENCER_CONTRACT = """BRAND PARTNERSHIP AGREEMENT

Brand: TrendyFashion Inc.
Creator: @StyleGuru
Campaign: Fall 2025 Collection

DELIVERABLES:
- 3 Instagram Reels
- 2 TikTok videos

USAGE RIGHTS:
Brand is granted perpetual, worldwide rights to use all content
in any media now known or hereafter devised, including for
AI training and machine learning model development.

EXCLUSIVITY:
Creator may not promote competing fashion brands for 6 months.

PAYMENT: $5,000 total, Net-60 after posting approval.

FTC: Creator is responsible for compliance."""


def test_real_llm_gym():
    """Test gym analysis with real LLM"""
    print("\n[LLM] Testing Gym Contract Analysis...")

    resp = requests.post(
        f"{BASE_URL}/api/analyze-gym",
        json={"contract_text": GYM_CONTRACT, "state": "NY"},
        timeout=120
    )

    if resp.status_code != 200:
        print(f"  ✗ FAIL: Status {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        return False

    data = resp.json()

    # Verify real analysis quality
    checks = []

    # Should detect arbitration as a red flag
    red_flags = data.get("red_flags", [])
    has_arbitration = any("arbitration" in str(rf).lower() for rf in red_flags)
    checks.append(("arbitration_detected", has_arbitration))

    # Should detect cancellation difficulty
    cancel_difficulty = data.get("cancellation_difficulty", "")
    checks.append(("cancel_difficulty_assessed", cancel_difficulty in ["moderate", "hard", "nightmare"]))

    # Should have a meaningful summary (not empty template)
    summary = data.get("summary", "")
    gym_name = data.get("gym_name", "")
    # Either gym name in summary OR correctly extracted gym_name field
    checks.append(("meaningful_summary", len(summary) > 50 and ("planet fitness" in summary.lower() or "planet fitness" in gym_name.lower())))

    # Should have cancellation guide
    guide = data.get("cancellation_guide", "")
    checks.append(("cancellation_guide", len(guide) > 100))

    failed = [c[0] for c in checks if not c[1]]

    if failed:
        print(f"  ✗ FAIL: {failed}")
        print(f"  Response: {json.dumps(data, indent=2)[:500]}...")
        return False

    print(f"  ✓ PASS: Risk={data.get('overall_risk')}, Score={data.get('risk_score')}")
    print(f"  Summary: {summary[:100]}...")
    return True


def test_real_llm_influencer():
    """Test influencer analysis with real LLM"""
    print("\n[LLM] Testing Influencer Contract Analysis...")

    resp = requests.post(
        f"{BASE_URL}/api/analyze-influencer",
        json={"contract_text": INFLUENCER_CONTRACT, "base_rate": 5000},
        timeout=120
    )

    if resp.status_code != 200:
        print(f"  ✗ FAIL: Status {resp.status_code}")
        return False

    data = resp.json()

    checks = []

    # Should detect perpetual rights
    checks.append(("perpetual_rights", data.get("has_perpetual_rights") == True))

    # Should detect AI training rights
    checks.append(("ai_training_rights", data.get("has_ai_training_rights") == True))

    # Should flag exclusivity as concerning
    red_flags = data.get("red_flags", [])
    has_exclusivity_flag = any("exclusivity" in str(rf).lower() for rf in red_flags)
    checks.append(("exclusivity_flagged", has_exclusivity_flag))

    # Should have negotiation script
    script = data.get("negotiation_script", "")
    checks.append(("negotiation_script", len(script) > 100))

    failed = [c[0] for c in checks if not c[1]]

    if failed:
        print(f"  ✗ FAIL: {failed}")
        print(f"  Response: {json.dumps(data, indent=2)[:500]}...")
        return False

    print(f"  ✓ PASS: Risk={data.get('overall_risk')}, Perpetual={data.get('has_perpetual_rights')}")
    return True


FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://cantheyfuckme.com")
if os.environ.get("LOCAL"):
    FRONTEND_URL = "http://localhost:5173"


def test_browser_workflow():
    """Test full browser workflow using Claude in Chrome MCP"""
    print("\n[BROWSER] Testing Full Workflow...")
    print(f"  Frontend: {FRONTEND_URL}")
    print(f"  Backend: {BASE_URL}")
    print()

    # Verify frontend is accessible
    try:
        resp = requests.get(FRONTEND_URL, timeout=10)
        if resp.status_code == 200:
            print("  ✓ Frontend is accessible")
        else:
            print(f"  ✗ Frontend returned {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Frontend not accessible: {e}")
        return False

    # Verify backend is accessible
    try:
        resp = requests.get(BASE_URL, timeout=10)
        if resp.status_code == 200:
            print("  ✓ Backend is accessible")
        else:
            print(f"  ✗ Backend returned {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Backend not accessible: {e}")
        return False

    print()
    print("  Browser workflow test steps (manual for now):")
    print(f"  1. Navigate to {FRONTEND_URL}")
    print("  2. Paste a gym contract")
    print("  3. Click 'CAN THEY FUCK ME?'")
    print("  4. Type 'not legal advice' in disclaimer")
    print("  5. Verify analysis results display")
    print()
    print("  To automate: Use Claude in Chrome MCP tools")

    return True


def run_llm_tests():
    """Run all real LLM tests"""
    print("\n" + "=" * 60)
    print("EXPENSIVE LLM TESTS")
    print("=" * 60)

    # Check if we're in mock mode
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        if resp.status_code != 200:
            print("ERROR: Backend not running. Start with:")
            print("  cd backend && source venv/bin/activate && uvicorn main:app --port 8081")
            return False
    except:
        print("ERROR: Cannot connect to backend")
        return False

    results = []
    results.append(("Gym Analysis (LLM)", test_real_llm_gym()))
    results.append(("Influencer Analysis (LLM)", test_real_llm_influencer()))

    print("\n" + "-" * 40)
    passed = sum(1 for r in results if r[1])
    print(f"LLM Tests: {passed}/{len(results)} passed")

    return all(r[1] for r in results)


def run_browser_tests():
    """Run browser automation tests"""
    print("\n" + "=" * 60)
    print("BROWSER WORKFLOW TESTS")
    print("=" * 60)

    return test_browser_workflow()


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args:
        print(__doc__)
        sys.exit(0)

    success = True

    if "--llm" in args or "--all" in args:
        success = run_llm_tests() and success

    if "--browser" in args or "--all" in args:
        success = run_browser_tests() and success

    sys.exit(0 if success else 1)
