# frontend/ — React SPA

## Purpose
React 18 + TypeScript + Vite single-page application providing the investor dashboard, portfolio management, listing analysis, social simulation, and negotiation workspace.

## Key Structure

| Path | Role |
|------|------|
| `src/pages/` | Route-level pages: Portfolio, Analysis, Simulation, Negotiation, Onboarding, SignIn |
| `src/components/` | Reusable UI — portfolio tabs (Overview, Holdings, Underwrite, Stress Test, Decisions, Strategy), market map, negotiation chat, persona builder |
| `src/auth/` | Supabase integration — `AuthProvider`, client setup |
| `src/hooks/` | Custom hooks — `useAuth`, `usePortfolioMode` |
| `src/api.ts` | HTTP client with Bearer token injection |
| `src/utils/supabase.ts` | Supabase client configuration |
| `e2e/` | Playwright end-to-end tests |

## Key Pages
- **PortfolioPage** — 6 tabs: Overview, Holdings, Underwrite, Stress Test, Decisions, Strategy
- **NegotiationPage** — Persona Risk Workspace (social simulation primary surface)
- **AnalysisPage** — listing analysis via analyst council
- **OnboardingWizard** — multi-step user setup

## Patterns
- **Lazy-loaded routes** for code splitting
- **Supabase auth** with JWT tokens passed to backend
- **Typed WebSocket** for real-time events
- **Vitest** for unit tests, **Playwright** for E2E

## Commands
```bash
npm install && npm run dev   # dev server on :5173
npm run test                 # Vitest unit tests
npm run test:e2e             # Playwright E2E
```
