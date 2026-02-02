# PoC Validation Plan — AI-Generated Test Reliability (Leandro Demo)

Owner: David Erik García Arenas (QA, Paradox Cat)

Purpose: Demonstrate whether AI can generate *reliable* Python-based test cases when provided with a strict structure (feature file + page object + locator rules). This is a controlled, reproducible PoC with measurable results.

---

## 1) Scope (keep it small and stable)

Pick **1–2 stable screens** only. Recommended:

- **Media → Radio** (stable flow, consistent layout)
- Optional: **Media → Source Selector**

Define a **single device/profile** for the demo (same resolution, same software build). Consistency is mandatory.

---

## 2) Baseline Test (human-written, gold standard)

Create a single, clean baseline test for the flow. This test is the **source of truth**.

### Example Test Structure (Python)

```
# tests/test_radio_baseline.py
# High-level scenario: Open Media → Radio, validate radio tile exists

def test_open_radio_app(device, media_page):
    media_page.open_media_from_home()
    media_page.open_radio()
    media_page.assert_radio_visible()
```

### Page Object Skeleton (Python)

```
# pages/media_page.py

class MediaPage:
    def open_media_from_home(self):
        # click Media icon on Home
        pass

    def open_radio(self):
        # open source selector, tap Radio
        pass

    def assert_radio_visible(self):
        # assert Radio title text exists
        pass
```

**Rule:** This baseline must pass 10/10 runs before starting AI generation.

---

## 3) Provide AI a strict template

Create a template that is **non-negotiable**. The AI must follow it. The goal is to remove ambiguity.

### Template: Feature File

```
Feature: Media - Radio

  Scenario: Open Radio from Media
    Given the device is on Home
    When I open Media
    And I select Radio source
    Then the Radio screen is visible
```

### Template: Step Definitions (Python)

```
# steps/media_steps.py

@given("the device is on Home")
 def step_home(device):
     device.go_home()

@when("I open Media")
 def step_open_media(media_page):
     media_page.open_media_from_home()

@when("I select Radio source")
 def step_select_radio(media_page):
     media_page.open_radio()

@then("the Radio screen is visible")
 def step_assert_radio(media_page):
     media_page.assert_radio_visible()
```

### Locator Rules (must be in prompt)

- Use **resource-id** when available
- Otherwise use **text + class + parent context**
- Avoid global text search (scope to container)
- Prefer stable container IDs for source selector

---

## 4) AI Prompt (copy/paste, do not improvise)

Use this exact prompt for generating test variations:

```
You are generating Python test cases using the existing framework.
Follow the exact structure below. Do NOT create new helpers.
Use only MediaPage methods: open_media_from_home(), open_radio(), assert_radio_visible(), open_source_selector(), assert_source_selector_visible().

Create 10 scenarios that are variations of opening the Radio app or switching sources.
Output only:
1) Feature file scenarios (Gherkin)
2) Step definitions calling the methods above (Python)

Rules:
- Do not add new methods
- Do not change step wording
- Do not use raw XPath in steps
```

---

## 5) Generate 10–20 AI tests

- Generate 10 at first.
- Review quickly for structure compliance.
- Reject any that violate the template.

---

## 6) Run Tests + Collect Metrics

Measure *reliability*, not creativity.

**Metrics to record:**
- Pass rate on first run (e.g., 7/10)
- Fix effort (number of edits per failing test)
- Average time to fix a failing test
- Re-run pass rate (e.g., 10/10 after fixes)

Keep results in a simple table:

| Metric | Result |
| --- | --- |
| Tests generated | 10 |
| Passed first run | 7 |
| Avg fixes/test | 1.3 |
| Avg fix time | 6 min |
| Final pass rate | 10/10 |

---

## 7) Demo Script (Leandro)

1. Show **baseline test** running clean.
2. Show **AI prompt** and generated tests.
3. Run tests and show initial pass rate.
4. Fix 1 failing test live (quick edit).
5. Re-run to show improved stability.
6. Present the metrics table.

Deliverables to show:
- Baseline test + page object
- AI-generated scenarios + steps
- Test report summary (pass rate)
- Short video or screenshots

---

## 8) Acceptance Criteria (PoC success)

PoC is **valid** if:

- AI outputs follow the strict structure
- ≥70% pass rate without edits
- All failures are fixable with small, deterministic edits
- Final pass rate reaches 100%

If it fails: clearly document why (e.g., unstable locators, UI variance, unclear steps).

---

## 9) Optional: Add a one-page PDF summary

Title: “AI-Generated Test Reliability — PoC Summary”

Include:
- Scope, baseline, AI prompt
- Metrics table
- Key conclusion: *AI helps accelerate test creation when structure is enforced*
