import { useEffect, useMemo, useState } from 'react'
import { Calendar } from 'lucide-react'
import axios from 'axios'

import { API_URL, LOCAL_USER_ID } from '../config'

function dateInputValue(value) {
    return String(value || '').split('T')[0]
}

function localDate(value, endOfDay = false) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateInputValue(value))
    if (!match) return null
    const [, year, month, day] = match.map(Number)
    return new Date(year, month - 1, day, endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0)
}

function formatDate(value) {
    const date = localDate(value)
    return date ? date.toLocaleDateString() : ''
}

export default function TimeframeHeader({ timeframe, onUpdate }) {
    const [isEditing, setIsEditing] = useState(false)
    const [startDate, setStartDate] = useState(timeframe.start_date || '')
    const [endDate, setEndDate] = useState(timeframe.end_date || '')
    const [error, setError] = useState('')
    const [saving, setSaving] = useState(false)
    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])
    const startInputId = `timeframe-${timeframe.id}-start-date`
    const endInputId = `timeframe-${timeframe.id}-end-date`

    useEffect(() => {
        if (isEditing) return
        setError('')
        setStartDate(timeframe.start_date || '')
        setEndDate(timeframe.end_date || '')
    }, [isEditing, timeframe.end_date, timeframe.start_date])

    const handleSave = async () => {
        setError('')
        const normalizedStart = dateInputValue(startDate)
        const normalizedEnd = dateInputValue(endDate)
        if (normalizedStart && normalizedEnd && normalizedStart > normalizedEnd) {
            setError('End date must be on or after the start date.')
            return
        }

        setSaving(true)
        try {
            await axios.put(`${API_URL}/timeframes/${timeframe.id}/dates`, {
                start_date: normalizedStart || null,
                end_date: normalizedEnd || null,
            }, {
                headers: authHeaders,
            })
            await onUpdate?.()
            setIsEditing(false)
        } catch (saveError) {
            console.error('Failed to update timeframe', saveError)
            setError('Dates could not be saved. Try again.')
        } finally {
            setSaving(false)
        }
    }

    // Determine status based on dates
    const now = new Date()
    const start = localDate(startDate)
    const end = localDate(endDate, true)

    let status = 'Unscheduled'
    let statusClass = 'status-upcoming'

    if (start && now < start) {
        status = 'Upcoming'
    } else if (end && now > end) {
        status = 'Passed'
        statusClass = 'status-passed'
    } else if (start || end) {
        status = 'Current'
        statusClass = 'status-current'
    }

    return (
        <div className="timeframe-header">
            <div className="timeframe-header-main">
                <h3 className="timeframe-label">
                    {timeframe.label}
                </h3>

                <div className="header-actions">
                    <span className={`status-badge ${statusClass}`}>
                        {status}
                    </span>
                    <button
                        className="icon-btn"
                        onClick={() => {
                            setError('')
                            setIsEditing((current) => !current)
                        }}
                        disabled={saving}
                        aria-label={`${isEditing ? 'Close' : 'Edit'} dates for ${timeframe.label}`}
                        aria-expanded={isEditing}
                    >
                        <Calendar size={16} aria-hidden="true" />
                    </button>
                </div>
            </div>

            {isEditing && (
                <div className="date-inputs">
                    <div className="date-input-group">
                        <label htmlFor={startInputId}>Start date</label>
                        <input
                            id={startInputId}
                            type="date"
                            value={dateInputValue(startDate)}
                            onChange={(e) => setStartDate(e.target.value)}
                            disabled={saving}
                        />
                    </div>
                    <div className="date-input-group">
                        <label htmlFor={endInputId}>End date</label>
                        <input
                            id={endInputId}
                            type="date"
                            value={dateInputValue(endDate)}
                            onChange={(e) => setEndDate(e.target.value)}
                            disabled={saving}
                        />
                    </div>
                    <button className="btn-primary btn-small" onClick={handleSave} disabled={saving}>
                        {saving ? 'Saving…' : 'Save dates'}
                    </button>
                    {error && <div className="inline-error" role="alert">{error}</div>}
                </div>
            )}

            {!isEditing && (startDate || endDate) && (
                <div className="date-display">
                    {startDate && formatDate(startDate)}
                    {startDate && endDate && ' - '}
                    {endDate && formatDate(endDate)}
                </div>
            )}
        </div>
    )
}
