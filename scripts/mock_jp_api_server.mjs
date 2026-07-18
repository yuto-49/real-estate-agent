import { createServer } from 'node:http'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const PORT = Number(process.env.PORT || 8000)
const ROOT = process.cwd()
const REINS_DIR = join(ROOT, 'tests', 'fixtures', 'tokyo', 'reins_samples')
const MLIT_PATH = join(
  ROOT,
  'tests',
  'fixtures',
  'tokyo',
  'mlit_transactions',
  '2024_tokyo_13_sample.csv',
)

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf-8'))
}

function parseCsv(text) {
  const rows = []
  let cell = ''
  let row = []
  let inQuotes = false

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          cell += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        cell += char
      }
      continue
    }
    if (char === '"') {
      inQuotes = true
      continue
    }
    if (char === ',') {
      row.push(cell)
      cell = ''
      continue
    }
    if (char === '\n') {
      row.push(cell.replace(/\r$/, ''))
      rows.push(row)
      row = []
      cell = ''
      continue
    }
    cell += char
  }
  if (cell || row.length > 0) {
    row.push(cell.replace(/\r$/, ''))
    rows.push(row)
  }

  const [header, ...data] = rows
  return data.map((values) =>
    Object.fromEntries(header.map((key, index) => [key, values[index] ?? ''])),
  )
}

function parseIntSafe(value) {
  const cleaned = String(value || '').replace(/[^\d.-]/g, '')
  if (!cleaned) return null
  const parsed = Number(cleaned)
  return Number.isFinite(parsed) ? parsed : null
}

function loadListings() {
  return readdirSync(REINS_DIR)
    .filter((name) => name.endsWith('.json'))
    .flatMap((name) => readJson(join(REINS_DIR, name)).listings || [])
    .map((listing) => {
      const municipality = listing.shozaichi?.shikuchouson || ''
      const prefecture = listing.shozaichi?.todoufuken || ''
      const neighborhood = listing.shozaichi?.chome || ''
      const banchi = listing.shozaichi?.banchi_go || ''
      const buildingName = listing.shozaichi?.building_name || ''
      const address = [prefecture, municipality, neighborhood, banchi, buildingName]
        .filter(Boolean)
        .join(' ')
      return {
        id: listing.bukken_bangou,
        source: listing,
        address,
        municipality,
        prefecture,
        neighborhood,
        stationNames: (listing.rinshii_eki || []).map((item) => item.eki).filter(Boolean),
        walkMinutes: Math.min(
          ...((listing.rinshii_eki || [])
            .map((item) => Number(item.toho_bun))
            .filter((value) => Number.isFinite(value) && value > 0)),
          99,
        ),
        price: Number(listing.baibai_kakaku_yen || 0),
        propertyType:
          listing.bukken_shubetsu === 'mansion'
            ? 'condo'
            : listing.bukken_shubetsu === 'issenkodate'
              ? 'sfr'
              : listing.bukken_shubetsu === 'shueki'
                ? 'multifamily'
                : 'condo',
        bedrooms: Number(String(listing.madori || '').match(/\d+/)?.[0] || 1),
        bathrooms: 1,
        sqft: Math.round(Number(listing.menseki_m2 || listing.tatemono_menseki_m2 || 0) * 10.7639),
      }
    })
}

function loadMlitBenchmarks() {
  const rows = parseCsv(readFileSync(MLIT_PATH, 'utf-8'))
  const byCode = new Map()
  const byMunicipality = new Map()

  for (const row of rows) {
    const code = row['市区町村コード']
    const municipality = row['市区町村名']
    const price = parseIntSafe(row['取引価格(総額)'])
    if (!code || !municipality || !price) continue
    if (!byCode.has(code)) {
      byCode.set(code, { municipality, prices: [] })
    }
    byCode.get(code).prices.push(price)
    byMunicipality.set(municipality, code)
  }

  const medians = new Map()
  for (const [code, value] of byCode.entries()) {
    const prices = value.prices.sort((a, b) => a - b)
    const middle = Math.floor(prices.length / 2)
    const median =
      prices.length % 2 === 0
        ? Math.round((prices[middle - 1] + prices[middle]) / 2)
        : prices[middle]
    medians.set(code, {
      cityCode: code,
      municipality: value.municipality,
      medianPrice: median,
      count: prices.length,
    })
  }

  return { medians, byMunicipality }
}

function normalizeText(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
}

function normalizeZip(value) {
  const digits = String(value || '').replace(/\D/g, '')
  return digits.length === 7 ? digits : digits.length === 5 ? digits : ''
}

function formatYen(value) {
  if (!value) return '—'
  if (value >= 100_000_000) {
    return `${Math.floor((value / 100_000_000) * 100) / 100}億円`
  }
  if (value >= 10_000) {
    return `${Math.floor((value / 10_000) * 100) / 100}万円`
  }
  return `¥${value.toLocaleString('ja-JP')}`
}

function buildPropertyRecord(listing) {
  return {
    id: listing.id,
    address: listing.address,
    asking_price: listing.price,
    bedrooms: listing.bedrooms,
    bathrooms: listing.bathrooms,
    sqft: listing.sqft,
    property_type: listing.propertyType,
    latitude: listing.source.latitude,
    longitude: listing.source.longitude,
    status: 'active',
  }
}

function buildRecommendations(profile, listings, benchmarks, topN = 10) {
  const geo = profile?.geography || {}
  const budget = Number(profile?.budget || 0)
  const municipalityWanted = normalizeText(geo.municipality || geo.city || geo.ward)
  const prefectureWanted = normalizeText(geo.prefecture || geo.state)
  const neighborhoodWanted = normalizeText(geo.neighborhood)
  const stationWanted = normalizeText(geo.station)
  const zipWanted = normalizeZip(geo.zip)

  const matchesCoreFilters = (listing) => {
    if (budget && listing.price > budget * 1.05) return false
    if (prefectureWanted && normalizeText(listing.prefecture) !== prefectureWanted) return false
    if (zipWanted && municipalityWanted) return true
    return true
  }

  const matchesStrictLocation = (listing) => {
    if (municipalityWanted && normalizeText(listing.municipality) !== municipalityWanted) return false
    if (neighborhoodWanted && !normalizeText(listing.neighborhood).includes(neighborhoodWanted)) return false
    if (stationWanted) {
      const stationMatch = listing.stationNames.some(
        (station) => normalizeText(station).includes(stationWanted),
      )
      if (!stationMatch) return false
    }
    return true
  }

  const strictMatches = listings.filter(
    (listing) => matchesCoreFilters(listing) && matchesStrictLocation(listing),
  )
  const filtered =
    strictMatches.length > 0
      ? strictMatches
      : listings.filter((listing) => matchesCoreFilters(listing))

  const scored = filtered.map((listing) => {
    const cityCode = benchmarks.byMunicipality.get(listing.municipality)
    const benchmark = cityCode ? benchmarks.medians.get(cityCode) : null
    const relativeScore = benchmark?.medianPrice
      ? Math.max(0, Math.min(1, 1 - Math.abs(listing.price - benchmark.medianPrice) / benchmark.medianPrice))
      : 0.55
    const budgetScore = budget ? Math.max(0, Math.min(1, 1 - listing.price / (budget * 1.1))) : 0.6
    const stationScore = listing.walkMinutes ? Math.max(0, Math.min(1, 1 - listing.walkMinutes / 15)) : 0.4
    const areaScore = listing.sqft ? Math.max(0.25, Math.min(1, listing.sqft / 800)) : 0.4

    let geoScore = 0.45
    if (stationWanted && listing.stationNames.some((station) => normalizeText(station).includes(stationWanted))) {
      geoScore = 0.95
    } else if (municipalityWanted && normalizeText(listing.municipality) === municipalityWanted) {
      geoScore = 0.9
    } else if (prefectureWanted && normalizeText(listing.prefecture) === prefectureWanted) {
      geoScore = 0.8
    }

    const score = Math.max(
      0,
      Math.min(1, geoScore * 0.35 + relativeScore * 0.3 + budgetScore * 0.2 + stationScore * 0.1 + areaScore * 0.05),
    )

    const rationale = [
      benchmark?.medianPrice
        ? `REINFOLIB ${listing.municipality} 成約中央値 ${formatYen(benchmark.medianPrice)} に近い価格帯`
        : 'REINFOLIB 価格ベンチマークは取得準備中',
      listing.stationNames.length > 0
        ? `${listing.stationNames[0]}駅まで徒歩${listing.walkMinutes}分`
        : '駅距離データは未設定',
      `${listing.source.madori || '間取り未設定'}・${Math.round(Number(listing.source.menseki_m2 || listing.source.tatemono_menseki_m2 || 0))}㎡`,
    ]

    return {
      property_id: listing.id,
      address: listing.address,
      asking_price: listing.price,
      property_type: listing.propertyType,
      bedrooms: listing.bedrooms,
      bathrooms: listing.bathrooms,
      sqft: listing.sqft,
      score: Number(score.toFixed(4)),
      rationale,
    }
  })

  scored.sort((left, right) => right.score - left.score || right.asking_price - left.asking_price)
  return {
    candidates_considered: filtered.length,
    recommendations: scored.slice(0, topN),
  }
}

const listings = loadListings()
const benchmarks = loadMlitBenchmarks()
const demoListing = listings.find((listing) => listing.municipality === '世田谷区') || listings[0]
const demoUser = {
  id: 'dev-user-0001',
  name: '山田 花子',
  email: 'dev@realestate.local',
  role: 'investor',
  budget_min: 60_000_000,
  budget_max: 120_000_000,
  life_stage: 'investor',
  investment_goals: {},
  risk_tolerance: 'moderate',
  timeline_days: 180,
  latitude: demoListing?.source.latitude ?? 35.643,
  longitude: demoListing?.source.longitude ?? 139.67,
  zip_code: '154-0024',
  search_radius: 5,
  preferred_types: [demoListing?.propertyType ?? 'condo'],
  created_at: new Date().toISOString(),
}
const demoPortfolio = {
  id: 'portfolio-demo',
  user_id: demoUser.id,
  name: '都内収益物件',
  investment_strategy: 'buy_and_hold',
  notes: 'REINFOLIB ベンチマーク付きのデモ保有ポートフォリオ',
  created_at: new Date().toISOString(),
}
const demoHolding = {
  id: `holding-${demoListing.id}`,
  portfolio_id: demoPortfolio.id,
  property_id: demoListing.id,
  address: demoListing.address,
  latitude: demoListing.source.latitude,
  longitude: demoListing.source.longitude,
  zip_code: '154-0024',
  asset_class: demoListing.propertyType === 'condo' ? 'condo' : 'multifamily',
  status: 'held',
  financials: {
    id: `fin-${demoListing.id}`,
    holding_id: `holding-${demoListing.id}`,
    cost_basis: Math.round(demoListing.price * 0.92),
    current_value_estimate: demoListing.price,
    loan_balance: Math.round(demoListing.price * 0.56),
    monthly_rent: 265_000,
    monthly_opex_estimate: 58_000,
    monthly_piti: 132_000,
    vacancy_rate: 0.04,
  },
  created_at: new Date().toISOString(),
}
const users = new Map([[demoUser.id, demoUser]])
const profiles = new Map()
const portfolios = new Map([[demoPortfolio.user_id, demoPortfolio]])
const portfolioHoldings = new Map([[demoPortfolio.id, [demoHolding]]])
const runs = new Map()

function listPortfoliosForUser(userId) {
  return [...portfolios.values()].filter((portfolio) => portfolio.user_id === userId)
}

function listHoldingsForPortfolio(portfolioId) {
  return [...(portfolioHoldings.get(portfolioId) || [])]
}

function findPortfolioById(portfolioId) {
  return [...portfolios.values()].find((portfolio) => portfolio.id === portfolioId) || null
}

function summarizePortfolio(portfolio) {
  const holdings = listHoldingsForPortfolio(portfolio.id)
  const perHolding = holdings.map((holding) => ({
    holding_id: holding.id,
    address: holding.address,
    zip_code: holding.zip_code,
    asset_class: holding.asset_class,
    current_value: holding.financials?.current_value_estimate ?? demoListing.price,
    monthly_cash_flow:
      (holding.financials?.monthly_rent ?? 0)
      - (holding.financials?.monthly_opex_estimate ?? 0)
      - (holding.financials?.monthly_piti ?? 0),
    cap_rate: 0.043,
    dscr: 1.42,
    cash_on_cash: 0.081,
    recommendation: 'HOLD',
    recommendation_score: 0.84,
    recommendation_rationale: 'REINFOLIB 価格帯と駅距離のバランスが良好です。',
    market_context_available: true,
  }))
  const totalValue = perHolding.reduce((sum, row) => sum + (row.current_value || 0), 0)
  const totalLoanBalance = holdings.reduce(
    (sum, holding) => sum + (holding.financials?.loan_balance ?? 0),
    0,
  )
  const totalEquity = totalValue - totalLoanBalance
  const monthlyGrossRent = holdings.reduce(
    (sum, holding) => sum + (holding.financials?.monthly_rent ?? 0),
    0,
  )
  const monthlyCashFlow = perHolding.reduce((sum, row) => sum + (row.monthly_cash_flow || 0), 0)
  const annualNoi = monthlyCashFlow * 12

  return {
    portfolio_id: portfolio.id,
    generated_at: new Date().toISOString(),
    holding_count: holdings.length,
    aggregates: {
      total_value: totalValue,
      total_loan_balance: totalLoanBalance,
      total_equity: totalEquity,
      monthly_gross_rent: monthlyGrossRent,
      monthly_net_operating_income: monthlyCashFlow + 18_000,
      monthly_cash_flow: monthlyCashFlow,
      annual_noi: annualNoi,
      blended_cap_rate: totalValue > 0 ? annualNoi / totalValue : 0.043,
      weighted_dscr: 1.42,
    },
    per_holding: perHolding,
    attention: perHolding.map((row) => ({
      holding_id: row.holding_id,
      address: row.address,
      action: row.recommendation,
      score: row.recommendation_score,
      rationale: row.recommendation_rationale,
    })),
    market_coverage: {
      total: holdings.length,
      with_signals: holdings.length,
    },
  }
}

function aggregatePortfolio(portfolio) {
  const summary = summarizePortfolio(portfolio)
  const holdings = listHoldingsForPortfolio(portfolio.id)
  const assetClassMix = Object.fromEntries(
    holdings.reduce((counts, holding) => {
      counts.set(holding.asset_class, (counts.get(holding.asset_class) || 0) + 1)
      return counts
    }, new Map()),
  )
  return {
    portfolio_id: portfolio.id,
    holding_count: summary.holding_count,
    total_value: summary.aggregates.total_value,
    total_loan_balance: summary.aggregates.total_loan_balance,
    total_equity: summary.aggregates.total_equity,
    total_cost_basis: holdings.reduce(
      (sum, holding) => sum + (holding.financials?.cost_basis ?? 0),
      0,
    ),
    monthly_gross_rent: summary.aggregates.monthly_gross_rent,
    monthly_net_operating_income: summary.aggregates.monthly_net_operating_income,
    monthly_cash_flow: summary.aggregates.monthly_cash_flow,
    blended_cap_rate: summary.aggregates.blended_cap_rate,
    weighted_dscr: summary.aggregates.weighted_dscr,
    concentration: { top_market: demoListing.municipality, share: 1 },
    asset_class_mix: assetClassMix,
    investment_strategy: portfolio.investment_strategy,
  }
}

function json(res, status, body) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  })
  res.end(JSON.stringify(body))
}

async function readBody(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf-8')) : {}
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host}`)
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    })
    res.end()
    return
  }

  if (url.pathname === '/health') {
    json(res, 200, { status: 'ok', version: 'mock-jp-reinfolib' })
    return
  }

  if (url.pathname === '/api/config/public') {
    json(res, 200, {
      environment: 'development',
      api_base_url: '/api',
      ws_base_url: '/ws',
      supabase_url: '',
      supabase_publishable_key: '',
      map_style_url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    })
    return
  }

  if (url.pathname === '/api/onboarding/state') {
    const userId = url.searchParams.get('user_id') || 'dev-user-0001'
    json(res, 200, {
      user_id: userId,
      has_portfolio: portfolios.has(userId),
      has_profile: profiles.has(userId),
    })
    return
  }

  if (url.pathname === '/api/users/' && req.method === 'GET') {
    json(res, 200, [...users.values()])
    return
  }

  const userMatch = url.pathname.match(/^\/api\/users\/([^/]+)$/)
  if (userMatch && req.method === 'GET') {
    const user = users.get(userMatch[1])
    if (!user) {
      json(res, 404, { detail: 'user_not_found' })
      return
    }
    json(res, 200, user)
    return
  }

  if (url.pathname === '/api/properties/' && req.method === 'GET') {
    const properties = listings.map((listing) => buildPropertyRecord(listing))
    json(res, 200, { properties, count: properties.length })
    return
  }

  if (url.pathname === '/api/investor-profile/' && req.method === 'POST') {
    const payload = await readBody(req)
    const geography = payload.geography || {}
    const profile = {
      id: `profile-${payload.user_id || 'dev'}`,
      user_id: payload.user_id || 'dev-user-0001',
      budget: payload.budget || null,
      strategy: payload.strategy || 'buy_and_hold',
      target_cap_rate: payload.target_cap_rate || null,
      target_coc: payload.target_coc || null,
      geography: {
        zip: geography.zip || null,
        city: geography.city || null,
        state: geography.state || null,
        prefecture: geography.prefecture || null,
        municipality: geography.municipality || null,
        ward: geography.ward || null,
        neighborhood: geography.neighborhood || null,
        station: geography.station || null,
      },
      notes: payload.notes || null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    profiles.set(profile.user_id, profile)
    json(res, 201, profile)
    return
  }

  if (url.pathname === '/api/properties/recommend' && req.method === 'GET') {
    const userId = url.searchParams.get('user_id') || 'dev-user-0001'
    const topN = Number(url.searchParams.get('top_n') || 10)
    const profile = profiles.get(userId) || {
      id: `profile-${userId}`,
      user_id: userId,
      budget: 100_000_000,
      strategy: 'buy_and_hold',
      target_cap_rate: 5.0,
      target_coc: 5.0,
      geography: {
        prefecture: '東京都',
        municipality: '港区',
      },
    }
    const recommendationSet = buildRecommendations(profile, listings, benchmarks, topN)
    json(res, 200, {
      ...recommendationSet,
      profile_id: profile.id,
    })
    return
  }

  if (url.pathname === '/api/portfolio/from-property' && req.method === 'POST') {
    const payload = await readBody(req)
    const listing = listings.find((item) => item.id === payload.property_id) || demoListing
    const portfolio = {
      id: `portfolio-${payload.property_id}`,
      user_id: payload.user_id || 'dev-user-0001',
      name: payload.portfolio_name || '提案物件ポートフォリオ',
      investment_strategy: payload.investment_strategy || 'buy_and_hold',
      created_at: new Date().toISOString(),
    }
    portfolios.set(portfolio.user_id, portfolio)
    portfolioHoldings.set(portfolio.id, [
      {
        id: `holding-${payload.property_id}`,
        portfolio_id: portfolio.id,
        property_id: listing.id,
        address: listing.address,
        latitude: listing.source.latitude,
        longitude: listing.source.longitude,
        zip_code: '154-0024',
        asset_class: listing.propertyType === 'condo' ? 'condo' : 'multifamily',
        status: 'held',
        financials: {
          id: `fin-${payload.property_id}`,
          holding_id: `holding-${payload.property_id}`,
          cost_basis: Math.round(listing.price * 0.92),
          current_value_estimate: listing.price,
          loan_balance: Math.round(listing.price * 0.58),
          monthly_rent: 252_000,
          monthly_opex_estimate: 55_000,
          monthly_piti: 128_000,
          vacancy_rate: 0.04,
        },
        created_at: new Date().toISOString(),
      },
    ])
    json(res, 201, portfolio)
    return
  }

  if (url.pathname === '/api/portfolio/' && req.method === 'GET') {
    const userId = url.searchParams.get('user_id')
    json(res, 200, userId ? listPortfoliosForUser(userId) : [...portfolios.values()])
    return
  }

  const holdingsMatch = url.pathname.match(/^\/api\/portfolio\/([^/]+)\/holdings$/)
  if (holdingsMatch && req.method === 'GET') {
    json(res, 200, listHoldingsForPortfolio(holdingsMatch[1]))
    return
  }

  const aggregateMatch = url.pathname.match(/^\/api\/portfolio\/([^/]+)\/aggregate$/)
  if (aggregateMatch && req.method === 'GET') {
    const portfolio = findPortfolioById(aggregateMatch[1])
    if (!portfolio) {
      json(res, 404, { detail: 'portfolio_not_found' })
      return
    }
    json(res, 200, aggregatePortfolio(portfolio))
    return
  }

  const summaryMatch = url.pathname.match(/^\/api\/portfolio\/([^/]+)\/summary$/)
  if (summaryMatch && req.method === 'GET') {
    const portfolio = findPortfolioById(summaryMatch[1])
    if (!portfolio) {
      json(res, 404, { detail: 'portfolio_not_found' })
      return
    }
    json(res, 200, summarizePortfolio(portfolio))
    return
  }

  if (url.pathname === '/api/strategy/extract' && req.method === 'POST') {
    json(res, 200, {
      profile: {
        thesis: {
          market_outlook: 'bullish',
          trajectory: 'neighborhood_trajectory',
          sentiment_topics: [],
          notes: '東京23区・駅徒歩10分以内の区分マンションを長期保有',
        },
        assumptions: {
          hold_period_years: 7,
          rent_growth: 0.015,
          expense_growth: 0.01,
          exit_cap_rate: 0.045,
          loan_rate_outlook: 0.018,
          vacancy_rate: 0.04,
        },
        policy_config: {
          refi_rate_threshold: 0.02,
          tenant_protection: true,
          raise_rent_bias: 0.05,
          risk_tolerance: 'moderate',
          sell_bias: 0.0,
        },
      },
    })
    return
  }

  if (url.pathname === '/api/strategy/run' && req.method === 'POST') {
    const payload = await readBody(req)
    const runId = `run-${Date.now()}`
    const portfolioId = payload.portfolio_id || 'portfolio-demo'
    const selected = [...portfolios.values()].find((portfolio) => portfolio.id === portfolioId)
    const listing = listings.find((item) => `portfolio-${item.id}` === portfolioId) || listings[0]
    const record = {
      run_id: runId,
      portfolio_id: portfolioId,
      status: 'completed',
      profile: {
        thesis: {
          market_outlook: 'bullish',
          trajectory: 'neighborhood_trajectory',
          sentiment_topics: [],
        },
        assumptions: {
          hold_period_years: 7,
          rent_growth: 0.015,
          expense_growth: 0.01,
          exit_cap_rate: 0.045,
          loan_rate_outlook: 0.018,
          vacancy_rate: 0.04,
        },
        policy_config: {
          refi_rate_threshold: 0.02,
          tenant_protection: true,
          raise_rent_bias: 0.05,
          risk_tolerance: 'moderate',
          sell_bias: 0.0,
        },
      },
      analysis: null,
      simulation: {
        portfolio_id: portfolioId,
        horizon_years: 7,
        per_holding: [
          {
            holding_id: `holding-${listing.id}`,
            address: listing.address,
            horizon_years: 7,
            projected_value: Math.round(listing.price * 1.08),
            projected_annual_noi: Math.round(listing.price * 0.038),
            projected_cap_rate: 0.043,
            projected_monthly_cash_flow: Math.round((listing.price * 0.038) / 12 * 0.18),
            projected_recommendation: 'HOLD',
          },
        ],
        aggregate_value_projection: Math.round(listing.price * 1.08),
        aggregate_annual_noi_projection: Math.round(listing.price * 0.038),
        aggregate_cap_rate_projection: 0.043,
        notes: [],
      },
      unified: {
        portfolio_id: portfolioId,
        horizon_years: 7,
        survives: true,
        confidence: 0.84,
        agreements: [
          `${listing.municipality} の REINFOLIB 成約帯と大きく乖離していません`,
          `${listing.stationNames[0] || '最寄り駅'} 近接で賃貸需要を見込みやすい前提です`,
        ],
        divergences: [],
        reconciliations: [
          {
            holding_id: `holding-${listing.id}`,
            address: listing.address,
            today_action: 'HOLD',
            projected_action: 'HOLD',
            flipped: false,
            note: 'REINFOLIB 価格帯に沿った保守的な長期保有シナリオです。',
          },
        ],
        summary: `${selected?.name || '提案物件ポートフォリオ'} は REINFOLIB ベンチマークに沿った価格帯で、東京の長期保有シナリオに概ね適合しています。`,
      },
      error: null,
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      steps: [],
    }
    runs.set(runId, record)
    json(res, 202, { run_id: runId, portfolio_id: portfolioId, status: 'pending', profile: record.profile })
    return
  }

  if (url.pathname === '/api/strategy/recent' && req.method === 'GET') {
    const userId = url.searchParams.get('user_id')
    const limit = Number(url.searchParams.get('limit') || 5)
    const userPortfolios = userId ? listPortfoliosForUser(userId).map((portfolio) => portfolio.id) : null
    const recent = [...runs.values()]
      .filter((run) => !userPortfolios || userPortfolios.includes(run.portfolio_id))
      .sort((left, right) => String(right.started_at).localeCompare(String(left.started_at)))
      .slice(0, limit)
    json(res, 200, recent)
    return
  }

  const statusMatch = url.pathname.match(/^\/api\/strategy\/([^/]+)\/status$/)
  if (statusMatch && req.method === 'GET') {
    const record = runs.get(statusMatch[1])
    json(res, 200, record || { status: 'completed' })
    return
  }

  const resultMatch = url.pathname.match(/^\/api\/strategy\/([^/]+)\/result$/)
  if (resultMatch && req.method === 'GET') {
    const record = runs.get(resultMatch[1])
    if (!record) {
      json(res, 404, { detail: 'run_not_found' })
      return
    }
    json(res, 200, record)
    return
  }

  json(res, 404, { detail: 'not_found', path: url.pathname })
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`mock_jp_api_server listening on http://127.0.0.1:${PORT}`)
})
