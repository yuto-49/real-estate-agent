# Single-Page UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the multi-page app (11 routes, 40+ components) with a single-page experience: sign in, search/select a property, get AI analysis + simulation results — all on one screen.

**Architecture:** One authenticated page with 3 vertical panels: (1) property input/search, (2) AI analysis results with rent comps, (3) simulation + stress test. Sign-in is a full-screen gate. No navigation bar, no routing complexity.

**Tech Stack:** React 18, TypeScript, Vite, Supabase Auth, existing FastAPI backend (unchanged)

---

## Current vs New UX

```
CURRENT (11 routes, complex nav):
  /signin -> / (dashboard) -> /analysis/:id -> /simulation -> /portfolio (6 tabs) -> /negotiate -> /profile

NEW (2 screens):
  /signin -> / (single workspace)

Single Workspace Layout:
+------------------------------------------------------------------+
| [Logo]  Real Estate Agentic     [user@email.com] [Sign Out]      |
+------------------------------------------------------------------+
|  LEFT PANEL (300px) |  CENTER PANEL (1fr) |  RIGHT PANEL (1fr)   |
|                     |                     |                      |
| [Search/Paste URL]  | AI Analysis Results | Simulation           |
| [Property Card]     |  - Overall Score    |  - Cap Rate / CoC    |
| [Quick Stats]       |  - Risk Verdict     |  - DSCR / IRR / NOI  |
|  - Price            |  - Location Verdict |  - Stress Test       |
|  - Size/Type        |  - Vacancy/Demand   |  - Rent Comps        |
|  - Walk time        |  - Depreciation     |                      |
|  - Built year       |  - Red Flags        |                      |
|                     |  - Summary          |                      |
| [Analyze Button]    |                     | [Run Stress Test]    |
+------------------------------------------------------------------+
```

## File Structure

### Files to CREATE

| File | Responsibility |
|------|---------------|
| `frontend/src/pages/WorkspacePage.tsx` | Main single-page workspace with 3-panel layout |
| `frontend/src/components/workspace/PropertyInput.tsx` | Left panel: search, URL paste, property card |
| `frontend/src/components/workspace/AnalysisPanel.tsx` | Center panel: AI verdict cards, red flags, score |
| `frontend/src/components/workspace/SimulationPanel.tsx` | Right panel: underwriting, stress test, rent comps |
| `frontend/src/components/workspace/ScoreGauge.tsx` | Circular score display (0-100) |
| `frontend/src/styles/workspace.css` | All workspace styles (3-panel grid, cards, responsive) |

### Files to MODIFY

| File | Change |
|------|--------|
| `frontend/src/App.tsx` | Replace all routes with just `/signin` and `/` (WorkspacePage) |

### Files UNTOUCHED (kept for future use)

All existing pages and components stay in the codebase — just not routed to. No deletions.

---

### Task 1: Create workspace CSS and layout foundation

**Files:**
- Create: `frontend/src/styles/workspace.css`

- [ ] **Step 1: Create the workspace stylesheet**

```css
/* ---- Layout ---- */
.workspace {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #f8f9fa;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.workspace-header h1 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: #1a202c;
}

.workspace-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #64748b;
}

.workspace-header-right button {
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #64748b;
  transition: all 0.15s;
}

.workspace-header-right button:hover {
  background: #f1f5f9;
  color: #1a202c;
}

.workspace-panels {
  display: grid;
  grid-template-columns: 300px 1fr 1fr;
  gap: 0;
  flex: 1;
  overflow: hidden;
}

.workspace-panel {
  overflow-y: auto;
  padding: 20px;
  border-right: 1px solid #e2e8f0;
}

.workspace-panel:last-child {
  border-right: none;
}

.workspace-panel-header {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e2e8f0;
}

/* ---- Cards ---- */
.ws-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.ws-card-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}

/* ---- Property Input ---- */
.ws-search-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.ws-search-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.ws-search-results {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  margin-top: 4px;
}

.ws-search-item {
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
}

.ws-search-item:hover {
  background: #f1f5f9;
}

.ws-property-stat {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid #f8f9fa;
}

.ws-property-stat-label { color: #64748b; }
.ws-property-stat-value { font-weight: 600; color: #1a202c; }

.ws-btn-primary {
  width: 100%;
  padding: 10px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  margin-top: 12px;
  transition: background 0.15s;
}

.ws-btn-primary:hover { background: #2563eb; }
.ws-btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }

/* ---- Score Gauge ---- */
.ws-score-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
}

.ws-score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
}

.ws-score-circle--high { background: #22c55e; }
.ws-score-circle--mid { background: #f59e0b; }
.ws-score-circle--low { background: #ef4444; }

.ws-score-label {
  font-size: 12px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ---- Verdict Cards ---- */
.ws-verdict {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-left: 3px solid #e2e8f0;
  margin-bottom: 8px;
  background: #fff;
  border-radius: 0 6px 6px 0;
}

.ws-verdict--pass { border-left-color: #22c55e; }
.ws-verdict--caution { border-left-color: #f59e0b; }
.ws-verdict--block { border-left-color: #ef4444; }

.ws-verdict-title { font-size: 13px; font-weight: 600; color: #1a202c; }
.ws-verdict-summary { font-size: 12px; color: #64748b; margin-top: 4px; }

/* ---- Badges ---- */
.ws-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.ws-badge--green { background: #dcfce7; color: #166534; }
.ws-badge--red { background: #fee2e2; color: #991b1b; }
.ws-badge--amber { background: #fef3c7; color: #92400e; }
.ws-badge--gray { background: #f1f5f9; color: #475569; }

/* ---- Loading / Empty ---- */
.ws-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #64748b;
  font-size: 14px;
}

.ws-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: ws-spin 0.8s linear infinite;
  margin-bottom: 12px;
}

@keyframes ws-spin { to { transform: rotate(360deg); } }

.ws-empty {
  text-align: center;
  padding: 40px 20px;
  color: #94a3b8;
  font-size: 14px;
}

.ws-empty-icon { font-size: 48px; margin-bottom: 12px; }

/* ---- Responsive ---- */
@media (max-width: 1024px) {
  .workspace-panels { grid-template-columns: 1fr; }
  .workspace-panel { border-right: none; border-bottom: 1px solid #e2e8f0; }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/styles/workspace.css
git commit -m "feat: add workspace CSS for single-page layout"
```

---

### Task 2: Create PropertyInput component (left panel)

**Files:**
- Create: `frontend/src/components/workspace/PropertyInput.tsx`

- [ ] **Step 1: Create the component**

Debounced search against `/api/search`, property card with stats, Analyze button. See full code in plan source (components/workspace/PropertyInput.tsx). Key features:
- 300ms debounced search input
- Dropdown results from `/api/search?q=...&limit=10`
- Property card showing price (man-yen), size, walk time, built year, type, construction, assumed rent
- "Analyze This Property" button
- "Clear Selection" button
- Empty state with house icon

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workspace/PropertyInput.tsx
git commit -m "feat: add PropertyInput for workspace left panel"
```

---

### Task 3: Create ScoreGauge and AnalysisPanel (center panel)

**Files:**
- Create: `frontend/src/components/workspace/ScoreGauge.tsx`
- Create: `frontend/src/components/workspace/AnalysisPanel.tsx`

- [ ] **Step 1: Create ScoreGauge**

Circular score display: green (>=70), amber (>=45), red (<45). Props: `score: number`, `label?: string`.

- [ ] **Step 2: Create AnalysisPanel**

Displays analyst council results. Props: `analysis: AnalysisResult | null`, `loading: boolean`, `error: string | null`. Shows:
- Loading spinner with "Running analyst council (4 AI personas)..."
- ScoreGauge with overall_score
- Summary card
- 4 verdict cards with color-coded left border (pass/caution/block)
- Red flag badges per verdict
- Empty state when no analysis yet

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workspace/ScoreGauge.tsx frontend/src/components/workspace/AnalysisPanel.tsx
git commit -m "feat: add ScoreGauge and AnalysisPanel components"
```

---

### Task 4: Create SimulationPanel (right panel)

**Files:**
- Create: `frontend/src/components/workspace/SimulationPanel.tsx`

- [ ] **Step 1: Create the component**

Three sections in cards:
1. **Underwriting** — auto-fetches `POST /api/underwrite/{id}` when property has analysis. Shows cap rate, cash-on-cash, DSCR, IRR, NOI, monthly P&I.
2. **Stress Test** — button triggers `POST /api/underwrite/{id}/stress`. Shows median/P10/P90 IRR and fail rate with color-coded badge.
3. **Rent Comps** — reuses existing `RentComps` component directly (`import RentComps from '../RentComps'`).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workspace/SimulationPanel.tsx
git commit -m "feat: add SimulationPanel with underwriting, stress test, rent comps"
```

---

### Task 5: Create WorkspacePage (main page)

**Files:**
- Create: `frontend/src/pages/WorkspacePage.tsx`

- [ ] **Step 1: Create the page**

Imports workspace CSS, auth hook, and all 3 panel components. State:
- `property: Property | null`
- `analysis: AnalysisResult | null`
- `analyzing: boolean`
- `analysisError: string | null`

`handleAnalyze` calls `POST /api/listings/{id}/analyze` and sets analysis state.

Layout:
```
<div className="workspace">
  <header> logo + user email + sign out </header>
  <div className="workspace-panels">
    <PropertyInput />
    <AnalysisPanel />
    <SimulationPanel />
  </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/WorkspacePage.tsx
git commit -m "feat: add WorkspacePage single-page workspace"
```

---

### Task 6: Rewire App.tsx to single-page layout

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace App.tsx**

Strip down to 2 routes only:
- `/signin` -> `SignInPage` (existing, unchanged)
- `/*` -> `RequireAuth` -> `WorkspacePage`

Remove: all NavLinks, header nav, PortfolioModeToggle, SystemDrawer, isFullBleedRoute, all lazy imports except SignInPage and WorkspacePage.

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: simplify routing to signin + single workspace page"
```

---

### Task 7: Test the full flow

- [ ] **Step 1:** Start backend (`uvicorn main:app --reload`) and frontend (`cd frontend && npm run dev`)
- [ ] **Step 2:** Open `http://localhost:5173` — should redirect to `/signin`
- [ ] **Step 3:** Sign in — should show 3-panel workspace
- [ ] **Step 4:** Search a property — dropdown should appear
- [ ] **Step 5:** Select property, click Analyze — center panel shows AI verdicts
- [ ] **Step 6:** Right panel shows underwriting + stress test button + rent comps
- [ ] **Step 7:** Resize below 1024px — panels stack vertically

---

## What This Plan Does NOT Change

- **Backend:** Zero changes to any Python file or API endpoint
- **Old pages:** All existing pages remain in `frontend/src/pages/` — just not routed to
- **Old components:** All existing components remain — `RentComps.tsx` is reused directly
- **Auth:** Supabase auth flow unchanged (SignInPage stays as-is)
- **Tests:** Existing backend tests unaffected (342 pass)

## Rollback

To restore the multi-page app, revert only `frontend/src/App.tsx`:

```bash
git checkout HEAD~1 -- frontend/src/App.tsx
```
