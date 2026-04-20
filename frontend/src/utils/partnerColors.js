// Single source of truth for partner type/category colors
// Used in: PartnerCard, PartnerDetailPage, PartnersPage

export const TYPE_CATEGORY_COLORS = {
  'medic':                   { bg: '#FCE4EC', text: '#880E4F' }, // rose/pink — medical red cross
  'partner:doctor':          { bg: '#EDE7F6', text: '#4527A0' }, // deep purple
  'partner:fitness_trainer': { bg: '#E8F5E9', text: '#1B5E20' }, // green
  'partner:blogger':         { bg: '#FFD54F', text: '#3E2723' }, // gold bar
  'partner:other':           { bg: '#FFF8E1', text: '#E65100' }, // amber
  'partner:':                { bg: '#E3F2FD', text: '#1565C0' }, // blue (no category)
}

export function nameColor(partner) {
  if (!partner) return TYPE_CATEGORY_COLORS['partner:']
  const key = partner.type === 'medic'
    ? 'medic'
    : `partner:${partner.category || ''}`
  return TYPE_CATEGORY_COLORS[key] || TYPE_CATEGORY_COLORS['partner:']
}

// Deterministic operator color by user id
export const OP_PALETTE = [
  { bg: '#E3F2FD', text: '#1565C0', avatar: '#1976D2' },
  { bg: '#E8F5E9', text: '#2E7D32', avatar: '#388E3C' },
  { bg: '#EDE7F6', text: '#4527A0', avatar: '#5E35B1' },
  { bg: '#FFF3E0', text: '#E65100', avatar: '#F57C00' },
  { bg: '#E0F2F1', text: '#00695C', avatar: '#00897B' },
  { bg: '#FCE4EC', text: '#880E4F', avatar: '#C2185B' },
  { bg: '#E8EAF6', text: '#283593', avatar: '#3949AB' },
  { bg: '#F1F8E9', text: '#33691E', avatar: '#558B2F' },
  { bg: '#FFF8E1', text: '#F57F17', avatar: '#F9A825' },
  { bg: '#E0F7FA', text: '#006064', avatar: '#00838F' },
]

export function opColor(userId) {
  if (!userId) return { bg: '#F5F5F5', text: '#9E9E9E', avatar: '#BDBDBD' }
  return OP_PALETTE[userId % OP_PALETTE.length]
}
