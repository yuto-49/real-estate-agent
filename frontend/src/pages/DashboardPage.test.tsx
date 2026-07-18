import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import DashboardPage from './DashboardPage'
import { api } from '../utils/api'

vi.mock('../components/DashboardMap', () => ({
  default: ({
    properties,
    holdings,
  }: {
    properties: Array<{ id: string }>
    holdings: Array<{ id: string; address: string }>
  }) => (
    <div
      data-testid="dashboard-map"
      data-properties={properties.length}
      data-holdings={holdings.length}
    >
      {holdings.map((holding) => (
        <span key={holding.id}>{holding.address}</span>
      ))}
    </div>
  ),
}))

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    const storage = new Map<string, string>()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => storage.get(key) ?? null),
        setItem: vi.fn((key: string, value: string) => {
          storage.set(key, value)
        }),
        removeItem: vi.fn((key: string) => {
          storage.delete(key)
        }),
      },
    })
  })

  it('loads and shows the investor holdings so the map can focus on real properties', async () => {
    vi.spyOn(api.users, 'list').mockResolvedValue([
      {
        id: 'user-1',
        name: '山田 花子',
        email: 'hanako@example.com',
        role: 'investor',
        budget_min: 60_000_000,
        budget_max: 120_000_000,
        life_stage: 'investor',
        investment_goals: {},
        risk_tolerance: 'moderate',
        timeline_days: 180,
        latitude: 35.643,
        longitude: 139.67,
        zip_code: '154-0024',
        search_radius: 5,
        preferred_types: ['condo'],
      },
    ])
    vi.spyOn(api.properties, 'list').mockResolvedValue({
      properties: [
        {
          id: 'market-1',
          address: '東京都新宿区神楽坂四丁目2-11',
          asking_price: 98_000_000,
          latitude: 35.7009,
          longitude: 139.74,
        },
      ],
      count: 1,
    })
    vi.spyOn(api.portfolio, 'list').mockResolvedValue([
      {
        id: 'portfolio-1',
        user_id: 'user-1',
        name: '都内収益物件',
        investment_strategy: 'buy_and_hold',
      },
    ])
    vi.spyOn(api.portfolio, 'listHoldings').mockResolvedValue([
      {
        id: 'holding-1',
        portfolio_id: 'portfolio-1',
        property_id: 'property-1',
        address: '東京都世田谷区三軒茶屋二丁目11-14',
        latitude: 35.643,
        longitude: 139.67,
        zip_code: '154-0024',
        asset_class: 'condo',
        status: 'held',
        financials: {
          id: 'fin-1',
          holding_id: 'holding-1',
          monthly_rent: 265_000,
        },
      },
    ])

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('現在の保有物件所在地')).toBeInTheDocument()
    })

    expect(screen.getAllByText('東京都世田谷区三軒茶屋二丁目11-14')).toHaveLength(2)
    expect(screen.getByText('マップ連携済み')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-map')).toHaveAttribute('data-holdings', '1')
  })
})
