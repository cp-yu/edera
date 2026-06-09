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

export function entityColor(entity: string): string {
  let hash = 0
  for (let i = 0; i < entity.length; i++) hash = ((hash << 5) - hash + entity.charCodeAt(i)) | 0
  const [r, g, b] = PALETTE[Math.abs(hash) % PALETTE.length]
  return `rgb(${r}, ${g}, ${b})`
}
