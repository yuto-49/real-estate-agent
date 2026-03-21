"""Financial modeling engine for deep MiroFish intelligence reports.

Pure math modules — no DB, no I/O. Each class is independently testable.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Any


class MortgageCalculator:
    """Fixed-rate mortgage math."""

    @staticmethod
    def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
        """Calculate monthly mortgage payment (P&I)."""
        if annual_rate <= 0:
            return principal / (years * 12)
        r = annual_rate / 12
        n = years * 12
        return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    @staticmethod
    def amortization_schedule(
        principal: float, annual_rate: float, years: int,
    ) -> list[dict]:
        """Return yearly amortization summary."""
        r = annual_rate / 12
        n = years * 12
        monthly = MortgageCalculator.monthly_payment(principal, annual_rate, years)
        balance = principal
        schedule = []
        yearly_interest = 0.0
        yearly_principal = 0.0

        for month in range(1, n + 1):
            interest = balance * r
            principal_paid = monthly - interest
            balance -= principal_paid
            yearly_interest += interest
            yearly_principal += principal_paid

            if month % 12 == 0:
                year = month // 12
                equity_pct = round((1 - max(balance, 0) / principal) * 100, 2)
                schedule.append({
                    "year": year,
                    "remaining_balance": round(max(balance, 0), 2),
                    "total_interest_paid": round(yearly_interest, 2),
                    "total_principal_paid": round(yearly_principal, 2),
                    "equity_pct": equity_pct,
                })
                yearly_interest = 0.0
                yearly_principal = 0.0

        return schedule

    @staticmethod
    def total_interest(principal: float, annual_rate: float, years: int) -> float:
        monthly = MortgageCalculator.monthly_payment(principal, annual_rate, years)
        return round(monthly * years * 12 - principal, 2)


class CashFlowModel:
    """Monthly and annual cash flow projections for rental properties."""

    @staticmethod
    def monthly_cash_flow(
        rental_income: float,
        mortgage: float,
        taxes: float,
        insurance: float,
        hoa: float = 0,
        maintenance_pct: float = 0.01,
        property_value: float = 0,
        vacancy_rate: float = 0.05,
    ) -> dict:
        """Calculate monthly net cash flow."""
        effective_rent = rental_income * (1 - vacancy_rate)
        maintenance = (property_value * maintenance_pct) / 12 if property_value else 0
        total_expenses = mortgage + taxes + insurance + hoa + maintenance
        net = effective_rent - total_expenses
        return {
            "gross_rental_income": round(rental_income, 2),
            "effective_rental_income": round(effective_rent, 2),
            "mortgage": round(mortgage, 2),
            "taxes": round(taxes, 2),
            "insurance": round(insurance, 2),
            "hoa": round(hoa, 2),
            "maintenance": round(maintenance, 2),
            "total_expenses": round(total_expenses, 2),
            "net_cash_flow": round(net, 2),
        }

    @staticmethod
    def annual_projections(
        property_value: float,
        rental_income: float,
        appreciation_rate: float,
        rental_growth_rate: float,
        years: int,
        mortgage: float = 0,
        taxes: float = 0,
        insurance: float = 0,
        hoa: float = 0,
        maintenance_pct: float = 0.01,
        vacancy_rate: float = 0.05,
    ) -> list[dict]:
        """Project annual cash flows over N years."""
        projections = []
        val = property_value
        rent = rental_income

        for year in range(1, years + 1):
            val *= (1 + appreciation_rate)
            rent *= (1 + rental_growth_rate)
            effective_rent = rent * 12 * (1 - vacancy_rate)
            annual_maintenance = val * maintenance_pct
            annual_expenses = (mortgage + taxes + insurance + hoa) * 12 + annual_maintenance
            annual_net = effective_rent - annual_expenses

            projections.append({
                "year": year,
                "property_value": round(val, 2),
                "annual_rental_income": round(effective_rent, 2),
                "annual_expenses": round(annual_expenses, 2),
                "annual_net_cash_flow": round(annual_net, 2),
                "cumulative_equity_gain": round(val - property_value, 2),
            })

        return projections


class InvestmentMetrics:
    """Core real estate investment metrics."""

    @staticmethod
    def cap_rate(noi: float, property_value: float) -> float:
        """Capitalization rate = NOI / property value."""
        if property_value <= 0:
            return 0.0
        return round((noi / property_value) * 100, 2)

    @staticmethod
    def cash_on_cash(annual_cash_flow: float, cash_invested: float) -> float:
        """Cash-on-cash return = annual cash flow / total cash invested."""
        if cash_invested <= 0:
            return 0.0
        return round((annual_cash_flow / cash_invested) * 100, 2)

    @staticmethod
    def irr(cash_flows: list[float], guess: float = 0.1, max_iter: int = 100) -> float:
        """Internal rate of return via Newton's method."""
        rate = guess
        for _ in range(max_iter):
            npv = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
            dnpv = sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))
            if abs(dnpv) < 1e-12:
                break
            new_rate = rate - npv / dnpv
            if abs(new_rate - rate) < 1e-8:
                rate = new_rate
                break
            rate = new_rate
        return round(rate * 100, 2)

    @staticmethod
    def npv(cash_flows: list[float], discount_rate: float) -> float:
        """Net present value at given discount rate."""
        return round(
            sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cash_flows)), 2
        )

    @staticmethod
    def break_even_months(
        monthly_cost_to_own: float,
        monthly_rent: float,
        upfront_costs: float = 0,
    ) -> int:
        """Months until owning beats renting (accounting for upfront costs)."""
        if monthly_cost_to_own >= monthly_rent:
            return 0  # Owning is never cheaper on a monthly basis at these rates
        monthly_savings = monthly_rent - monthly_cost_to_own
        if monthly_savings <= 0:
            return 999  # Never breaks even
        return math.ceil(upfront_costs / monthly_savings) if upfront_costs > 0 else 0


class MonteCarloEngine:
    """Run Monte Carlo scenarios for investment outcome distributions."""

    @staticmethod
    def run_scenarios(
        base_params: dict,
        n_scenarios: int = 300,
        rng: random.Random | None = None,
        hold_years: int = 10,
    ) -> dict:
        """Run N randomized investment scenarios.

        base_params should contain:
            property_value, down_payment_pct, annual_rate, loan_years,
            monthly_rent, annual_appreciation, vacancy_rate, maintenance_pct,
            annual_tax_rate, annual_insurance
        """
        if rng is None:
            rng = random.Random()

        pv = base_params.get("property_value", 400000)
        dp_pct = base_params.get("down_payment_pct", 0.20)
        base_rate = base_params.get("annual_rate", 0.065)
        loan_years = base_params.get("loan_years", 30)
        base_rent = base_params.get("monthly_rent", 2500)
        base_appreciation = base_params.get("annual_appreciation", 0.035)
        base_vacancy = base_params.get("vacancy_rate", 0.05)
        base_maintenance = base_params.get("maintenance_pct", 0.01)
        tax_rate = base_params.get("annual_tax_rate", 0.012)
        insurance = base_params.get("annual_insurance", 1800)

        down_payment = pv * dp_pct
        loan_amount = pv - down_payment
        closing_costs = pv * 0.03  # ~3% closing costs
        cash_invested = down_payment + closing_costs

        irr_results = []
        npv_results = []
        final_values = []
        total_returns = []

        for _ in range(n_scenarios):
            # Randomize parameters
            appreciation = rng.gauss(base_appreciation, 0.02)
            rate = max(0.01, base_rate + rng.uniform(-0.015, 0.015))
            vacancy = max(0.0, min(0.20, rng.uniform(0.03, 0.12)))
            maintenance = max(0.005, rng.uniform(0.008, 0.02))
            rental_growth = rng.uniform(0.01, 0.05)

            monthly_mortgage = MortgageCalculator.monthly_payment(loan_amount, rate, loan_years)

            # Build annual cash flows
            cash_flows = [-cash_invested]
            val = pv
            rent = base_rent

            for year in range(1, hold_years + 1):
                val *= (1 + appreciation)
                rent *= (1 + rental_growth)
                annual_rent = rent * 12 * (1 - vacancy)
                annual_expenses = (
                    monthly_mortgage * 12
                    + val * tax_rate
                    + insurance
                    + val * maintenance
                )
                annual_net = annual_rent - annual_expenses

                if year == hold_years:
                    # Sell: property value minus selling costs (6%) minus remaining loan
                    remaining_months = (loan_years * 12) - (hold_years * 12)
                    if remaining_months > 0 and rate > 0:
                        r = rate / 12
                        remaining_balance = loan_amount * (
                            (1 + r) ** (loan_years * 12)
                            - (1 + r) ** (hold_years * 12)
                        ) / ((1 + r) ** (loan_years * 12) - 1)
                    else:
                        remaining_balance = 0
                    sale_proceeds = val * 0.94 - max(remaining_balance, 0)
                    annual_net += sale_proceeds

                cash_flows.append(annual_net)

            irr_val = InvestmentMetrics.irr(cash_flows)
            npv_val = InvestmentMetrics.npv(cash_flows, 0.08)
            total_return = sum(cash_flows)

            irr_results.append(irr_val)
            npv_results.append(npv_val)
            final_values.append(round(val, 2))
            total_returns.append(round(total_return, 2))

        irr_results.sort()
        npv_results.sort()
        final_values.sort()
        total_returns.sort()

        def percentiles(data: list[float]) -> dict:
            n = len(data)
            return {
                "p10": round(data[int(n * 0.10)], 2),
                "p25": round(data[int(n * 0.25)], 2),
                "p50": round(data[int(n * 0.50)], 2),
                "p75": round(data[int(n * 0.75)], 2),
                "p90": round(data[int(n * 0.90)], 2),
            }

        loss_count = sum(1 for r in total_returns if r < 0)

        return {
            "scenarios_run": n_scenarios,
            "hold_years": hold_years,
            "irr_distribution": percentiles(irr_results),
            "npv_distribution": percentiles(npv_results),
            "final_value_distribution": percentiles(final_values),
            "total_return_distribution": percentiles(total_returns),
            "probability_of_loss": round(loss_count / n_scenarios, 3),
            "mean_irr": round(sum(irr_results) / n_scenarios, 2),
            "mean_npv": round(sum(npv_results) / n_scenarios, 2),
        }


class TaxEstimator:
    """Estimate tax benefits of property ownership."""

    @staticmethod
    def annual_tax_benefit(
        mortgage_interest: float,
        property_taxes: float,
        marginal_rate: float = 0.24,
    ) -> dict:
        """Estimate annual tax deduction and savings."""
        # SALT cap is $10,000 for property taxes
        deductible_property_tax = min(property_taxes, 10000)
        total_deduction = mortgage_interest + deductible_property_tax
        # Standard deduction comparison (single: ~$14,600, married: ~$29,200)
        standard_deduction = 14600
        itemized_benefit = max(0, total_deduction - standard_deduction)
        estimated_savings = round(itemized_benefit * marginal_rate, 2)

        return {
            "mortgage_interest_deduction": round(mortgage_interest, 2),
            "property_tax_deduction": round(deductible_property_tax, 2),
            "total_itemized_deduction": round(total_deduction, 2),
            "standard_deduction_comparison": standard_deduction,
            "incremental_benefit": round(itemized_benefit, 2),
            "estimated_annual_savings": estimated_savings,
            "effective_marginal_rate": marginal_rate,
        }

    @staticmethod
    def depreciation_benefit(
        property_value: float,
        land_pct: float = 0.20,
        years: float = 27.5,
        marginal_rate: float = 0.24,
    ) -> dict:
        """Calculate annual depreciation tax benefit (rental properties only)."""
        depreciable_basis = property_value * (1 - land_pct)
        annual_depreciation = depreciable_basis / years
        tax_savings = annual_depreciation * marginal_rate

        return {
            "depreciable_basis": round(depreciable_basis, 2),
            "annual_depreciation": round(annual_depreciation, 2),
            "annual_tax_savings": round(tax_savings, 2),
            "depreciation_period_years": years,
            "land_percentage": land_pct,
        }


class PortfolioMetrics:
    """Portfolio-level risk and return metrics."""

    @staticmethod
    def sharpe_ratio(
        returns: list[float], risk_free_rate: float = 0.04,
    ) -> float:
        """Sharpe ratio = (mean return - risk free) / std dev."""
        if len(returns) < 2:
            return 0.0
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        if std_dev < 1e-10:
            return 0.0
        return round((mean_return - risk_free_rate) / std_dev, 2)

    @staticmethod
    def max_drawdown(values: list[float]) -> float:
        """Maximum peak-to-trough decline as a percentage."""
        if len(values) < 2:
            return 0.0
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return round(max_dd * 100, 2)
