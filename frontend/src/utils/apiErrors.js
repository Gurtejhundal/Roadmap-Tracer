function detailMessage(detail) {
    if (typeof detail === 'string') return detail.trim()
    if (Array.isArray(detail)) {
        return detail.map((issue) => {
            if (typeof issue === 'string') return issue.trim()
            if (!issue || typeof issue !== 'object') return ''
            const message = detailMessage(issue.msg ?? issue.message ?? issue.detail)
            const location = Array.isArray(issue.loc)
                ? issue.loc.filter((part) => !['body', 'query', 'path'].includes(String(part))).join('.')
                : ''
            return message ? `${location ? `${location}: ` : ''}${message}` : ''
        }).filter(Boolean).join(' ')
    }
    if (detail && typeof detail === 'object') {
        return detailMessage(detail.message ?? detail.msg ?? detail.error ?? detail.detail)
    }
    return ''
}

export function getApiErrorMessage(error, fallback = 'Something went wrong.') {
    return detailMessage(error?.response?.data?.detail)
        || detailMessage(error?.response?.data?.message)
        || detailMessage(error?.message)
        || fallback
}
