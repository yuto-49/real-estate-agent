import { useCallback } from 'react'

export interface ShockEntry {
  round_num: number
  shock_type: string
  magnitude: number
  label: string
}

interface ShockConfiguratorProps {
  shocks: ShockEntry[]
  onShocksChange: (shocks: ShockEntry[]) => void
}

interface PresetDef {
  label: string
  shock_type: string
  magnitude: number
}

const PRESETS: PresetDef[] = [
  { label: '家賃下落', shock_type: 'rent_decline', magnitude: -0.05 },
  { label: '空室率急騰', shock_type: 'expense_spike', magnitude: 0.10 },
  { label: '金利上昇', shock_type: 'expense_spike', magnitude: 0.05 },
  { label: '家賃規制', shock_type: 'rent_regulation', magnitude: 0.1 },
  { label: '減価償却期限', shock_type: 'shield_expiry', magnitude: 0 },
]

export default function ShockConfigurator({ shocks, onShocksChange }: ShockConfiguratorProps) {
  const addPreset = useCallback(
    (preset: PresetDef) => {
      const entry: ShockEntry = {
        round_num: 1,
        shock_type: preset.shock_type,
        magnitude: preset.magnitude,
        label: preset.label,
      }
      onShocksChange([...shocks, entry])
    },
    [shocks, onShocksChange],
  )

  const addCustom = useCallback(() => {
    const entry: ShockEntry = {
      round_num: 1,
      shock_type: 'custom',
      magnitude: 0,
      label: 'カスタムショック',
    }
    onShocksChange([...shocks, entry])
  }, [shocks, onShocksChange])

  const updateShock = useCallback(
    (index: number, patch: Partial<ShockEntry>) => {
      const updated = shocks.map((s, i) => (i === index ? { ...s, ...patch } : s))
      onShocksChange(updated)
    },
    [shocks, onShocksChange],
  )

  const removeShock = useCallback(
    (index: number) => {
      onShocksChange(shocks.filter((_, i) => i !== index))
    },
    [shocks, onShocksChange],
  )

  const clearAll = useCallback(() => {
    onShocksChange([])
  }, [onShocksChange])

  return (
    <div className="shock-configurator" data-testid="shock-configurator">
      <h4>ショックプリセット</h4>
      <div className="shock-preset-buttons">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className="shock-preset-btn"
            onClick={() => addPreset(p)}
            data-testid={`preset-${p.shock_type}`}
          >
            {p.label}
          </button>
        ))}
        <button
          type="button"
          className="shock-preset-btn shock-custom-btn"
          onClick={addCustom}
          data-testid="add-custom-shock"
        >
          + カスタム追加
        </button>
        {shocks.length > 0 && (
          <button
            type="button"
            className="shock-clear-btn"
            onClick={clearAll}
            data-testid="clear-shocks"
          >
            全削除
          </button>
        )}
      </div>

      {shocks.length > 0 && (
        <table className="shock-list" data-testid="shock-list">
          <thead>
            <tr>
              <th>ラベル</th>
              <th>種別</th>
              <th>ラウンド</th>
              <th>強度</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {shocks.map((s, i) => (
              <tr key={i} data-testid={`shock-row-${i}`}>
                <td>
                  <input
                    type="text"
                    value={s.label}
                    onChange={(e) => updateShock(i, { label: e.target.value })}
                    data-testid={`shock-label-${i}`}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={s.shock_type}
                    onChange={(e) => updateShock(i, { shock_type: e.target.value })}
                    data-testid={`shock-type-${i}`}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={s.round_num}
                    onChange={(e) =>
                      updateShock(i, { round_num: Math.max(1, Math.min(20, Number(e.target.value))) })
                    }
                    data-testid={`shock-round-${i}`}
                  />
                </td>
                <td>
                  <input
                    type="range"
                    min={-1}
                    max={1}
                    step={0.01}
                    value={s.magnitude}
                    onChange={(e) => updateShock(i, { magnitude: Number(e.target.value) })}
                    data-testid={`shock-magnitude-${i}`}
                  />
                  <span className="shock-magnitude-label">{s.magnitude.toFixed(2)}</span>
                </td>
                <td>
                  <button
                    type="button"
                    className="shock-remove-btn"
                    onClick={() => removeShock(i)}
                    data-testid={`remove-shock-${i}`}
                  >
                    x
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
