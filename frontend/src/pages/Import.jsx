import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import axios from 'axios'
import { Upload, FileText, Sparkles, AlertCircle } from 'lucide-react'

import { API_URL } from '../config'
import { useAuth } from '@clerk/clerk-react'

export default function Import() {
    const { userId } = useAuth()
    const navigate = useNavigate()
    const [name, setName] = useState('')
    const [rawText, setRawText] = useState('')
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)

    const parseRoadmapText = (text) => {
        const lines = text.split('\n').map(l => l.trim()).filter(l => l)
        const tasks = []
        let currentTimeframe = "General"

        // Improved Heuristics for "Natural" typing
        const explicitHeaderRegex = /^(#{1,3}|phase|month|week|day|step|part|learning path|section)\s*\d*/i
        const explicitTaskRegex = /^(\-|\*|\d+\.|\[\s*\]|\[x\]|•|→)\s+/i

        lines.forEach(line => {
            const isExplicitHeader = explicitHeaderRegex.test(line) || line.endsWith(':')
            // If it looks like "Week 1 - Something", treat as header
            // If it starts with #, treat as header

            if (isExplicitHeader) {
                // Remove Markdown chars (#) and trailing colons
                // Keep the rest of the text as the timeframe label (e.g. "Week 1 - Python Basic")
                currentTimeframe = line.replace(/^(#{1,3}\s*)/, '').replace(/:$/, '').trim()
            }
            else {
                // It's a task.
                // Remove bullet point if it exists, otherwise just take the text
                const title = line.replace(/^(\-|\*|\d+\.|\[\s*\]|\[x\]|•|→)\s+/, '').trim()

                // Edge case: Note/Comment detection? 
                // User said "comment" so just treat it as a task for now.
                tasks.push({
                    title: title,
                    timeframe: currentTimeframe,
                    is_done: line.toLowerCase().includes('[x]')
                })
            }
        })

        if (tasks.length === 0) {
            // If we somehow didn't get any tasks (maybe single line?), just add it
            if (rawText.trim()) {
                tasks.push({ title: rawText.trim(), timeframe: "General", is_done: false })
            } else {
                throw new Error("Could not detect any tasks.")
            }
        }

        return tasks
    }

    const handleImport = async () => {
        if (!name.trim()) {
            setError("Please enter a roadmap name")
            return
        }
        if (!rawText.trim()) {
            setError("Please paste the roadmap text")
            return
        }

        setError(null)
        setLoading(true)

        try {
            let tasks = []
            // Try JSON first if user insists (advanced)
            if (rawText.trim().startsWith('{')) {
                try {
                    const json = JSON.parse(rawText)
                    tasks = json.tasks || []
                    if (json.name && !name) setName(json.name)
                } catch (e) {
                    // Not JSON, fall back to text parse
                    tasks = parseRoadmapText(rawText)
                }
            } else {
                tasks = parseRoadmapText(rawText)
            }

            const payload = {
                name: name,
                tasks: tasks
            }

            const res = await axios.post(`${API_URL}/roadmaps/import`, payload, {
                headers: { 'X-Clerk-User-Id': userId }
            })
            navigate(`/roadmap/${res.data.id}`)
        } catch (err) {
            console.error(err)
            setError(err.response?.data?.detail || err.message || "Failed to parse or import")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="import-page">
            <motion.div
                className="form-container glass-panel"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
            >
                <h2 className="section-title">Import Your Roadmap</h2>

                <div className="form-group">
                    <label>Roadmap Name</label>
                    <input
                        type="text"
                        placeholder="e.g. Frontend Mastery"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        autoFocus
                    />
                </div>

                <div className="form-group">
                    <label>
                        <FileText size={16} style={{ marginBottom: '-2px', marginRight: '6px' }} />
                        Roadmap Content
                    </label>
                    <textarea
                        className="code-editor"
                        rows="15"
                        placeholder="Week 1: Foundations
Learn the Basics
Practice Coding

Week 2: Advanced
Build a Project"
                        value={rawText}
                        onChange={(e) => setRawText(e.target.value)}
                    ></textarea>
                </div>

                {error && (
                    <div className="error-message" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ff4d4d', marginBottom: '1rem', background: 'rgba(255, 77, 77, 0.1)', padding: '10px', borderRadius: '8px' }}>
                        <AlertCircle size={18} />
                        {error}
                    </div>
                )}

                <div className="full-width">
                    <button
                        className="btn-primary full-width"
                        onClick={handleImport}
                        disabled={loading}
                    >
                        {loading ? 'Analyzing...' : (
                            <>
                                <Sparkles size={18} style={{ marginRight: '8px' }} />
                                Smart Import
                            </>
                        )}
                    </button>
                </div>
            </motion.div>
        </div>
    )
}
