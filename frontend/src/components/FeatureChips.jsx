// Renders a show's extracted script features as colored chips.

const CHIP_GROUPS = [
  { key: 'tone', className: 'chip-tone' },
  { key: 'humor_type', className: 'chip-humor' },
  { key: 'dialogue_style', className: 'chip-dialogue' },
  { key: 'themes', className: 'chip-theme' },
  { key: 'genre_blend', className: 'chip-genre' },
]

export default function FeatureChips({ features, limit = 6 }) {
  if (!features) return null

  const chips = []
  for (const group of CHIP_GROUPS) {
    for (const value of features[group.key] || []) {
      chips.push({ value, className: group.className })
    }
  }
  if (features.pacing) chips.push({ value: `${features.pacing} pacing`, className: 'chip-pacing' })

  if (!chips.length) return null

  return (
    <div className="chips">
      {chips.slice(0, limit).map((chip, i) => (
        <span key={i} className={`chip ${chip.className}`}>
          {chip.value}
        </span>
      ))}
    </div>
  )
}
