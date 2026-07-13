import { useCallback, useMemo, useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Save, ArrowLeft, FileText, Sparkles } from 'lucide-react'
import { parseRoadmapText, formatRoadmapToText } from '../utils/roadmapParser'

import { API_URL, LOCAL_USER_ID } from '../config'

export default function Edit() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [textContent, setTextContent] = useState('')
    const [roadmapName, setRoadmapName] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)
    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])

    const fetchRoadmapData = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/roadmaps/${id}/export`, { headers: authHeaders })
            setRoadmapName(res.data.name)
            const formattedText = formatRoadmapToText(res.data)
            setTextContent(formattedText)
        } catch (err) {
            console.error("Failed to fetch roadmap", err)
            setTextContent("# Error fetching data\nCould not load roadmap.")
        } finally {
            setLoading(false)
        }
    }, [authHeaders, id])

    useEffect(() => {
        fetchRoadmapData()
    }, [fetchRoadmapData])

    const handleSave = async () => {
        setError(null)
        setSaving(true)

        try {
            const tasks = parseRoadmapText(textContent)
            const payload = {
                name: roadmapName,
                tasks: tasks
            }

            await axios.put(`${API_URL}/roadmaps/${id}/smart`, payload, {
                headers: authHeaders
            })

            navigate(`/roadmap/${id}`)
        } catch (err) {
            console.error(err)
            setError(err.response?.data?.detail || err.message || "Failed to save roadmap")
        } finally {
            setSaving(false)
        }
    }

    if (loading) return (
        <div className="loading-state" role="status" aria-live="polite">
            <span className="loading-spinner" aria-hidden="true" />
            <strong>Preparing the editor</strong>
            <span>Formatting your roadmap text…</span>
        </div>
    )

    return (
        <div className="edit-page">
            <div className="edit-header">
                <button className="btn-secondary" onClick={() => navigate(-1)}>
                    <ArrowLeft size={18} /> Back
                </button>
                <div className="edit-heading">
                    <span className="eyebrow">Structure editor</span>
                    <h2>Edit roadmap</h2>
                </div>
                <button className="btn-primary" onClick={handleSave} disabled={saving}>
                    <Save size={18} style={{ marginRight: '8px' }} />
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            <div className="glass-panel edit-workspace">
                <div className="form-group">
                    <label htmlFor="edit-roadmap-name">Roadmap name</label>
                    <input
                        id="edit-roadmap-name"
                        className="name-input"
                        value={roadmapName}
                        onChange={(e) => setRoadmapName(e.target.value)}
                    />
                </div>

                <div className="editor-label-row">
                    <label htmlFor="roadmap-content">
                        <FileText size={16} style={{ marginBottom: '-2px', marginRight: '6px' }} />
                        Content (Smart Text)
                    </label>
                    <div className="format-hint">
                        <Sparkles size={12} style={{ marginRight: '4px' }} />
                        Supports Week 1 - Topic format
                    </div>
                </div>

                {error && <div className="error-message" role="alert">{error}</div>}

                <textarea
                    id="roadmap-content"
                    className="code-editor"
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    spellCheck="false"
                    rows={20}
                    placeholder="# Week 1&#10;- Task 1"
                />
            </div>
        </div>
    )
}
