const DOCUMENT_ELEMENT_TYPES = new Set(['heading', 'paragraph', 'list', 'callout', 'code', 'table'])
const MAX_VALUE_DEPTH = 8

function formatValue(value, seen, depth) {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string') return value
    if (['number', 'boolean', 'bigint'].includes(typeof value)) return String(value)
    if (typeof value !== 'object') {
        try {
            return String(value)
        } catch {
            return ''
        }
    }
    if (depth >= MAX_VALUE_DEPTH || seen.has(value)) return ''

    seen.add(value)
    let formatted = ''
    try {
        if (Array.isArray(value)) {
            formatted = value
                .map((item) => formatValue(item, seen, depth + 1))
                .filter(Boolean)
                .join(', ')
        } else {
            formatted = Object.entries(value)
                .map(([key, nestedValue]) => {
                    const nested = formatValue(nestedValue, seen, depth + 1)
                    return nested ? `${key}: ${nested}` : ''
                })
                .filter(Boolean)
                .join('; ')
        }
    } catch {
        formatted = ''
    }
    seen.delete(value)
    return formatted
}

export function formatDocumentValue(value) {
    return formatValue(value, new WeakSet(), 0).trim()
}

function normalizedContext(element) {
    const context = {}
    const page = Number(element.page)
    if (Number.isFinite(page)) context.page = Math.max(0, Math.trunc(page))
    if (Array.isArray(element.section_path)) {
        context.section_path = element.section_path.map(formatDocumentValue).filter(Boolean)
    }
    return context
}

export function normalizeDocumentElement(element) {
    if (!element || typeof element !== 'object' || Array.isArray(element)) return null

    const rawType = typeof element.type === 'string' ? element.type.trim().toLowerCase() : ''
    const type = DOCUMENT_ELEMENT_TYPES.has(rawType) ? rawType : 'paragraph'
    const normalized = { type, ...normalizedContext(element) }

    if (['heading', 'paragraph', 'code'].includes(type)) {
        const text = formatDocumentValue(element.text)
        if (!text) return null
        normalized.text = text
        if (type === 'heading') {
            const level = Number(element.level)
            normalized.level = Number.isFinite(level)
                ? Math.min(6, Math.max(1, Math.trunc(level)))
                : 3
        }
        return normalized
    }

    if (type === 'callout') {
        const title = formatDocumentValue(element.title)
        const text = formatDocumentValue(element.text)
        if (!title && !text) return null
        if (title) normalized.title = title
        if (text) normalized.text = text
        return normalized
    }

    if (type === 'list') {
        const items = Array.isArray(element.items)
            ? element.items.map(formatDocumentValue).filter(Boolean)
            : []
        if (items.length === 0) return null
        normalized.items = items
        return normalized
    }

    const columnSource = Array.isArray(element.columns)
        ? element.columns
        : (Array.isArray(element.headers) ? element.headers : [])
    const columns = columnSource.map(formatDocumentValue)
    const rows = Array.isArray(element.rows)
        ? element.rows.map((row) => {
            const cells = Array.isArray(row) ? row : [row]
            return cells.map(formatDocumentValue)
        }).filter((row) => row.some(Boolean))
        : []
    if (columns.length === 0 && rows.length === 0) return null
    normalized.columns = columns
    normalized.rows = rows
    return normalized
}

export function normalizeDocumentElements(elements) {
    if (!Array.isArray(elements)) return []
    return elements.map(normalizeDocumentElement).filter(Boolean)
}
