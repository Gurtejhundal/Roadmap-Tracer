const PDF_DETAIL_LABELS = new Set([
    'cadence',
    'duration',
    'evidence',
    'focus',
    'goal',
    'learn',
    'objective',
    'output',
    'practice',
    'proof',
    'proof of skill',
    'required output',
])

export function formatSemanticValue(value) {
    if (value === null || value === undefined) return ''
    if (Array.isArray(value)) {
        return value.map(formatSemanticValue).filter(Boolean).join(', ')
    }
    if (typeof value === 'object') {
        return Object.entries(value)
            .map(([key, nestedValue]) => {
                const formatted = formatSemanticValue(nestedValue)
                return formatted ? `${key}: ${formatted}` : ''
            })
            .filter(Boolean)
            .join('; ')
    }
    return String(value)
}

export function getSemanticBlockDisplay(block) {
    const data = block?.data && typeof block.data === 'object' ? block.data : {}
    const label = formatSemanticValue(data.label).trim() || 'Detail'
    const value = formatSemanticValue(data.text ?? data.value ?? data.url ?? data.bookmarked)
    return { label, value }
}

export function getTaskRoadmap(task) {
    const value = task?.properties?.Roadmap
    return typeof value === 'string' || typeof value === 'number'
        ? String(value).trim()
        : ''
}

export function isImportedSemanticBlock(block) {
    if (block?.type !== 'note') return false
    if (block?.data?.source === 'user') return false
    if (['pdf', 'import'].includes(block?.data?.source)) return true
    const label = String(block?.data?.label || '').trim().toLowerCase()
    return PDF_DETAIL_LABELS.has(label)
}

export function formatTaskBlockForText(block) {
    const data = block?.data || {}
    const label = String(data.label || '').trim()

    if (block?.type === 'note') {
        const text = String(data.text || '').trim()
        return text ? `${label || 'Note'}: ${text}` : ''
    }
    if (block?.type === 'checklist') {
        const items = Array.isArray(data.items) ? data.items : []
        const visibleItems = items.filter((item) => String(item?.text || '').trim())
        const doneCount = items.filter((item) => item?.checked === true).length
        if (visibleItems.length === 0) return `${label || 'Checklist'}: ${doneCount}/${items.length} complete`
        return `${label || 'Checklist'}: ${visibleItems
            .map((item) => `${item?.checked === true ? '[x]' : '[ ]'} ${String(item?.text || '').trim()}`)
            .join('; ')}`
    }
    if (block?.type === 'counter') {
        const value = Number(data.value)
        return `${label || 'Counter'}: ${Number.isFinite(value) ? value : 0}`
    }
    if (block?.type === 'bookmark') {
        if (data.url) return `${label || 'Bookmark'}: ${data.url}`
        return `${label || 'Bookmark'}: ${data.bookmarked === false ? 'cleared' : 'marked'}`
    }
    if (block?.type === 'date') {
        return data.date ? `${label || 'Due date'}: ${data.date}` : ''
    }
    if (block?.type === 'label') {
        const value = String(data.value || '').trim()
        return value ? `${label || 'Label'}: ${value}` : ''
    }
    if (block?.type === 'code') {
        const code = String(data.code || '').trim()
        const language = String(data.language || '').trim()
        return code ? `${label || 'Code'}${language ? ` (${language})` : ''}: ${code}` : ''
    }

    const value = formatSemanticValue(data)
    return value ? `${block?.type || 'Block'}: ${value}` : ''
}

function searchValue(value) {
    if (value === null || value === undefined) return ''
    if (Array.isArray(value)) return value.map(searchValue).join(' ')
    if (typeof value === 'object') {
        return Object.entries(value)
            .map(([key, nestedValue]) => `${key} ${searchValue(nestedValue)}`)
            .join(' ')
    }
    return String(value)
}

export function getTaskSearchText(task, timeframe = '', roadmap = '') {
    const properties = Object.entries(task?.properties || {})
        .map(([key, value]) => `${key} ${searchValue(value)}`)
    const blocks = (Array.isArray(task?.blocks) ? task.blocks : [])
        .map((block) => `${block?.type || ''} ${formatTaskBlockForText(block)} ${searchValue(block?.data || {})}`)

    return [task?.title, timeframe, roadmap, ...properties, ...blocks]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
}

export function documentElementToLines(element) {
    const type = element?.type || 'paragraph'
    if (type === 'list') {
        return (element.items || []).map((item) => `- ${formatSemanticValue(item)}`)
    }
    if (type === 'table') {
        const lines = []
        if (Array.isArray(element.columns) && element.columns.length > 0) {
            lines.push(element.columns.map(formatSemanticValue).join(' | '))
        }
        (element.rows || []).forEach((row) => {
            const cells = Array.isArray(row) ? row : [row]
            lines.push(cells.map(formatSemanticValue).join(' | '))
        })
        return lines
    }
    if (type === 'callout') {
        return [element.title, element.text].map(formatSemanticValue).filter(Boolean)
    }
    return [formatSemanticValue(element?.text)].filter(Boolean)
}
