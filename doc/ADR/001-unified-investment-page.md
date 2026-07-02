# ADR-001: Unified Investment Page with Hash Routing

**Status:** accepted
**Date:** 2026-06-11
**Author:** Yuto Maruyama

## Context

The platform had three separate pages for investor workflows: `/analysis`, `/simulation`, and `/portfolio`. Each had its own user/portfolio selector and navigation. Investors had to jump between routes to go from analysis to simulation to portfolio decisions, creating friction and duplicating state management.

## Decision

Consolidate all three into a single `/invest` page using a sidebar + content layout with hash-based section switching (`/invest#portfolio`, `/invest#analysis`, etc.). Investor ID and portfolio ID are shared state at the `InvestmentPage` level, passed to all sections.

Key choices:
- **Hash routing over nested React Router routes** -- simpler shared state in one component
- **Vanilla CSS with `.invest-*` prefix** -- project uses vanilla CSS; avoids collision with existing 5,216-line index.css
- **Old routes redirect** -- `/analysis`, `/simulation`, `/portfolio` redirect to `/invest#section`

## Consequences

- Easier: single context for investor/portfolio, no prop drilling across routes
- Easier: deep-linking to sections via hash
- Harder: single page component manages more state
- Harder: browser back/forward behavior with hash routing is less intuitive than route-based

## Alternatives Considered

- **Nested routes** (`/invest/portfolio`, `/invest/analysis`): Better browser navigation but requires React Router outlet pattern and more complex state sharing. Rejected for simplicity.
- **Tab component on existing PortfolioPage**: Would bloat an already large page. Rejected because PortfolioPage already had 6 tabs.
