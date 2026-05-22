"""POST /api/underwrite + POST /api/listing/parse — Phase P2."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    ListingParseRequest,
    ListingParseResponse,
    StressTestRequest,
    StressTestResponse,
    UnderwriteRequest,
    UnderwriteResponse,
)
from intelligence.stress_test import (
    SliderRange,
    StressTestConfig,
    monte_carlo_stress_test,
)
from intelligence.underwriting import UnderwritingInputs, underwrite
from services.listing_import import ListingParseError, parse_zillow_url

underwrite_router = APIRouter()
listing_router = APIRouter()


@underwrite_router.post("", response_model=UnderwriteResponse)
async def underwrite_endpoint(data: UnderwriteRequest) -> UnderwriteResponse:
    inputs = UnderwritingInputs(**data.model_dump())
    result = underwrite(inputs)
    return UnderwriteResponse(
        monthly_piti=result.monthly_piti,
        annual_debt_service=result.annual_debt_service,
        effective_gross_income=result.effective_gross_income,
        annual_noi=result.annual_noi,
        cap_rate=result.cap_rate,
        cash_on_cash=result.cash_on_cash,
        dscr=result.dscr if result.dscr != float("inf") else 999.0,
        breakeven_occupancy=result.breakeven_occupancy,
        initial_equity=result.initial_equity,
        irr_5yr=result.irr_5yr,
        irr_10yr=result.irr_10yr,
    )


@underwrite_router.post("/stress-test", response_model=StressTestResponse)
async def stress_test_endpoint(data: StressTestRequest) -> StressTestResponse:
    base = UnderwritingInputs(**data.base_inputs.model_dump())
    cfg = StressTestConfig(
        iterations=data.config.iterations,
        seed=data.config.seed,
        vacancy_rate=SliderRange(
            data.config.vacancy_rate.low, data.config.vacancy_rate.high
        ),
        rent_growth=SliderRange(
            data.config.rent_growth.low, data.config.rent_growth.high
        ),
        expense_growth=SliderRange(
            data.config.expense_growth.low, data.config.expense_growth.high
        ),
        loan_rate=SliderRange(data.config.loan_rate.low, data.config.loan_rate.high),
        exit_cap_rate=SliderRange(
            data.config.exit_cap_rate.low, data.config.exit_cap_rate.high
        ),
    )
    result = monte_carlo_stress_test(base, cfg)
    return StressTestResponse(
        iterations=result.iterations,
        cap_rate_p10=result.cap_rate_p10,
        cap_rate_p50=result.cap_rate_p50,
        cap_rate_p90=result.cap_rate_p90,
        cash_on_cash_p10=result.cash_on_cash_p10,
        cash_on_cash_p50=result.cash_on_cash_p50,
        cash_on_cash_p90=result.cash_on_cash_p90,
        dscr_p10=result.dscr_p10,
        dscr_p50=result.dscr_p50,
        dscr_p90=result.dscr_p90,
        irr_5yr_p10=result.irr_5yr_p10,
        irr_5yr_p50=result.irr_5yr_p50,
        irr_5yr_p90=result.irr_5yr_p90,
        probability_negative_cash_flow=result.probability_negative_cash_flow,
        probability_dscr_under_1=result.probability_dscr_under_1,
        tornado=result.tornado,
    )


@listing_router.post("/parse", response_model=ListingParseResponse)
async def listing_parse_endpoint(data: ListingParseRequest) -> ListingParseResponse:
    try:
        parsed = parse_zillow_url(data.url)
    except ListingParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ListingParseResponse(
        source=parsed.source,
        zpid=parsed.zpid,
        url=parsed.url,
        address_hint=parsed.address_hint,
        state=parsed.state,
        zip_code=parsed.zip_code,
    )
