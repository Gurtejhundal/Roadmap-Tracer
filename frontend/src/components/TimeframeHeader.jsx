import { useState } from 'react'
import { ChevronDown, ChevronRight, Calendar } from 'lucide-react'
import axios from 'axios'
import { motion } from 'framer-motion'

import { API_URL } from '../config'

export default function TimeframeHeader({ timeframe, onUpdate }) {
    const [isEditing, setIsEditing] = useState(false)
    const [startDate, setStartDate] = useState(timeframe.start_date || '')
    const [endDate, setEndDate] = useState(timeframe.end_date || '')
    const [isExpanded, setIsExpanded] = useState(true)

    const handleSave = async () => {
        // Optimistic UI: Close immediately
        setIsEditing(false)
        try {
            await axios.put(`${API_URL}/timeframes/${timeframe.id}/dates`, {
                start_date: startDate || null,
                end_date: endDate || null
            })
            onUpdate()
        } catch (error) {
            console.error("Failed to update timeframe", error)
            // Optional: Re-open or show toast on error, but for now keep it simple/snappy
        }
    }

    // Determine status based on dates
    const now = new Date()
    const start = startDate ? new Date(startDate) : null
    const end = endDate ? new Date(endDate) : null

    let status = 'Upcoming'
    let statusClass = 'status-upcoming'

    if (start && end) {
        if (now >= start && now <= end) {
            status = 'Current'
            statusClass = 'status-current'
        } else if (now > end) {
            status = 'Passed'
            statusClass = 'status-passed'
        }
    }

    return (
        <div className="timeframe-header">
            <div className="timeframe-header-main">
                <h3 className="timeframe-label" onClick={() => setIsExpanded(!isExpanded)} style={{ cursor: 'pointer' }}>
                    {timeframe.label}
                </h3>

                <div className="header-actions">
                    <span className={`status-badge ${statusClass}`}>
                        {status}
                    </span>
                    <button
                        className="icon-btn"
                        onClick={() => setIsEditing(!isEditing)}
                    >
                        <Calendar size={16} />
                    </button>
                </div>
            </div>

            {isEditing && (
                <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    className="date-inputs"
                >
                    <div className="date-input-group">
                        <label>Start Date</label>
                        <input
                            type="date"
                            value={startDate ? startDate.split('T')[0] : ''}
                            onChange={(e) => setStartDate(e.target.value)}
                        />
                    </div>
                    <div className="date-input-group">
                        <label>End Date</label>
                        <input
                            type="date"
                            value={endDate ? endDate.split('T')[0] : ''}
                            onChange={(e) => setEndDate(e.target.value)}
                        />
                    </div>
                    <button className="btn-primary btn-small" onClick={handleSave}>
                        Save Dates
                    </button>
                </motion.div>
            )}

            {!isEditing && (startDate || endDate) && (
                <div className="date-display">
                    {startDate && new Date(startDate).toLocaleDateString()}
                    {startDate && endDate && ' - '}
                    {endDate && new Date(endDate).toLocaleDateString()}
                </div>
            )}
        </div>
    )
}
