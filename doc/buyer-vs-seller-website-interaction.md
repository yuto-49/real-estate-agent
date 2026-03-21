# Buyer vs Seller Website Interaction

This document explains how buyer and seller users should experience the platform differently, while sharing the same core transaction pipeline.

## 1) Shared Foundation

Both roles use the same backend system and core flow:

1. Discover properties
2. Enter negotiation
3. Exchange offers/counters
4. Move toward contract and close
5. Use intelligence reports to improve decisions

Shared UI/navigation (current frontend):

- `Search`
- `Users`
- `Negotiate`
- `Intelligence`
- `System`

## 2) Buyer Experience

Buyer goal: find the right property, avoid overpaying, and close with acceptable risk.

### Buyer Journey

1. Complete buyer profile (`budget`, `timeline`, `risk_tolerance`, `preferred_types`, `zip_code`)
2. Browse `Search` page (map + list) and shortlist properties
3. Start negotiation from a chosen property
4. Submit offer and counter-offers through negotiation flow
5. Generate intelligence report for timing/strategy guidance
6. Accept final terms and proceed to closing steps

### Buyer-Facing Priorities

- Affordability and payment fit
- Neighborhood suitability (schools, transit, amenities)
- Inspection and disclosure risk
- Timing: buy now vs wait
- Negotiation leverage from comps/market context

### Buyer Actions (API level)

- `GET /api/properties/` (search listings)
- `POST /api/negotiations/` (start negotiation)
- `POST /api/negotiations/{id}/offer` (submit offer/counter)
- `POST /api/reports/generate` (run MiroFish report for buyer profile)
- `GET /api/reports/{id}` (read recommendations)

## 3) Seller Experience

Seller goal: list effectively, maximize outcome, and close reliably.

### Seller Journey

1. Complete seller profile (role + constraints)
2. Create/update listings with required disclosures
3. Review incoming offers and negotiation context
4. Counter, accept, or reject based on strategy and risk
5. Use intelligence output for pricing/timing guidance
6. Advance accepted deal into contract/inspection/closing

### Seller-Facing Priorities

- Listing quality and pricing strategy
- Offer quality (price, contingencies, close likelihood)
- Time-to-close vs price tradeoff
- Legal/disclosure compliance
- Counter-offer discipline and escalation thresholds

### Seller Actions (API level)

- `POST /api/properties/` (list property)
- `PATCH /api/properties/{id}` (adjust asking price/status)
- `GET /api/offers/` (review offers)
- `POST /api/negotiations/{id}/offer` (counter-offer)
- `POST /api/negotiations/{id}/accept` (accept final terms)
- `POST /api/reports/generate` (seller-side market strategy report, optional)

## 4) Key UX Differences by Page

## `Search`

- Buyer view:
  - Property fit filters (price/type/beds/baths)
  - "Start Negotiation" from selected listing
- Seller view:
  - Comparable listings and competing inventory
  - "List Property" and "Adjust Price" CTAs

## `Negotiate`

- Buyer view:
  - Draft offer based on budget/strategy
  - Track counters and decide accept/walk-away
- Seller view:
  - Review buyer offers with margin/risk context
  - Counter toward target price and terms

## `Intelligence`

- Buyer report emphasis:
  - timing recommendation
  - strategy comparison for acquisition
  - top property targets
- Seller report emphasis:
  - list price/timing optimization
  - expected demand/liquidity
  - concession strategy and risk flags

## `Users`

- Buyer profile fields are typically dominant now (`budget`, `timeline`, `preferred_types`).
- Seller flow should add seller-specific fields (target net proceeds, urgency, minimum acceptable price, preferred close window).

## 5) Guardrails Impact (Different by Role)

- Buyer-side:
  - cannot submit offers below minimum threshold
  - cannot exceed configured constraints without escalation
- Seller-side:
  - cannot bypass required disclosures
  - high-value deals and excessive counter rounds trigger escalation logic

## 6) Current Repo State vs Target Role UX

As of this repository's current frontend:

- Search, negotiation, and reports exist
- Dedicated seller dashboard/page is not yet implemented
- Role-specific behavior is mostly enforced in backend agents/tools/guardrails

Target next step for stronger role separation:

1. Add explicit role-aware routing/views (`/buyer/*`, `/seller/*`)
2. Add seller listing management UI
3. Add role-specific report templates and action panels
4. Add role-based navigation/menu visibility

## 7) Quick Role Comparison

| Area | Buyer | Seller |
|---|---|---|
| Primary objective | Acquire good property at fair value | Maximize sale outcome with reliable close |
| First action | Search + shortlist | Create/optimize listing |
| Negotiation style | Push price down, preserve contingencies | Protect price, optimize terms and certainty |
| Intelligence use | Buy timing + strategy selection | Pricing/timing + concession strategy |
| Success metric | Fit + value + manageable risk | Net proceeds + days-to-close + deal certainty |

