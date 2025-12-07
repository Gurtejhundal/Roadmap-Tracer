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
    let statusColor = 'bg-blue-500' // tailwind-like classes won't work without tailwind, using style object or css classes

    if (start && end) {
        if (now >= start && now <= end) {
            status = 'Current'
            statusColor = 'var(--primary)'
        } else if (now > end) {
            status = 'Passed'
            statusColor = 'var(--muted)'
        }
    }

    return (
        <div className="timeframe-header">
            <div className="timeframe-header-main">
                <h3 className="timeframe-label" onClick={() => setIsExpanded(!isExpanded)} style={{ cursor: 'pointer' }}>
                    {timeframe.label}
                    {/* We can add chevron here if we want collapsible logic in parent, 
                       but parent manages the rendering of tasks? 
                       Actually parent renders tasks *inside* the group mapping, so checking `RoadmapView`...
                       Wait, `RoadmapView` maps `groupedTasks`. 
                       It renders `TimeframeHeader` then `tasks-list`. 
                       It does NOT wrap tasks-list inside TimeframeHeader children.
                       So `isExpanded` here won't hide tasks unless we lift state up.
                       For now, let's just make it a header.
                   */}
                </h3>

                <div className="header-actions">
                    <span
                        className="status-badge"
                        style={{ backgroundColor: statusColor }}
                    >
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
