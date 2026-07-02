# intelligence/ — Financial Analysis Engines

## Purpose
Pure math engines for real estate investment analysis: underwriting, Monte Carlo stress testing, mortgage calculations, JP depreciation, and tax projections. No DB or network I/O.

## Key Files

| File | Role |
|------|------|
| `underwriting.py` | `underwrite()` — computes cap rate, cash-on-cash return, DSCR, IRR from `UnderwritingInputs` |
| `financial_models.py` | `MortgageCalculator` — amortization schedules, random market simulations |
| `stress_test.py` | Monte Carlo on 5 sliders (vacancy, rent growth, expense growth, loan rate, exit cap) with tornado decomposition |
| `depreciation_jp.py` | JP statutory useful life lookup; tax-shield projection for wood/steel/RC buildings |
| `tax_basic.py` | Basic tax math — deductions, depreciation shields |

## Key Types
- `UnderwritingInputs` — purchase price, rent, expenses, loan terms
- `UnderwritingResult` — P&I, NOI, cap rate, cash-on-cash, DSCR, IRR
- `StressTestResult` — Monte Carlo distribution + tornado sensitivity

## Patterns
- **Pure functions** — no side effects, all inputs via dataclass parameters
- **Immutable outputs** — frozen dataclasses for all results
- **JP-aware** — supports both USD and JPY calculations, Japanese building types

## Testing
- Tests in `tests/test_stress_test.py`, `tests/test_depreciation_jp.py`
