const PALETTE = [
  [59, 130, 246],   // blue
  [16, 185, 129],   // emerald
  [245, 158, 11],   // amber
  [239, 68, 68],    // red
  [139, 92, 246],   // violet
  [236, 72, 153],   // pink
  [6, 182, 212],    // cyan
  [249, 115, 22],   // orange
  [34, 197, 94],    // green
  [168, 85, 247],   // purple
] as const

export function targetColor(target: string): string {
  let hash = 0
  for (let i = 0; i < target.length; i++) hash = ((hash << 5) - hash + target.charCodeAt(i)) | 0
  const [r, g, b] = PALETTE[Math.abs(hash) % PALETTE.length]
  return `rgb(${r}, ${g}, ${b})`
}

export function blendTargetColors(targets: string[]): string {
  if (targets.length === 0) return 'rgb(148, 163, 184)' // slate-400
  if (targets.length === 1) return targetColor(targets[0])
  let rSum = 0, gSum = 0, bSum = 0
  for (const t of targets) {
    let hash = 0
    for (let i = 0; i < t.length; i++) hash = ((hash << 5) - hash + t.charCodeAt(i)) | 0
    const [r, g, b] = PALETTE[Math.abs(hash) % PALETTE.length]
    rSum += r; gSum += g; bSum += b
  }
  const n = targets.length
  let r = Math.round(rSum / n), g = Math.round(gSum / n), b = Math.round(bSum / n)
  // Luminance correction: boost if too dark
  const lum = 0.299 * r + 0.587 * g + 0.114 * b
  if (lum < 80) { r = Math.min(255, r + 40); g = Math.min(255, g + 40); b = Math.min(255, b + 40) }
  return `rgb(${r}, ${g}, ${b})`
}
