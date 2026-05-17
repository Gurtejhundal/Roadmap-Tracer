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

    if (loading) return <div>Loading...</div>

    return (
        <div className="edit-page">
            <div className="edit-header">
                <button className="btn-secondary" onClick={() => navigate(-1)}>
                    <ArrowLeft size={18} /> Back
                </button>
                <div style={{ flex: 1 }}></div>
                <button className="btn-primary" onClick={handleSave} disabled={saving}>
                    <Save size={18} style={{ marginRight: '8px' }} />
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            <div className="glass-panel">
                <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>Roadmap Name</label>
                    <input
                        className="name-input"
                        style={{ width: '100%', padding: '0.5rem', fontSize: '1.2rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', borderRadius: '4px' }}
                        value={roadmapName}
                        onChange={(e) => setRoadmapName(e.target.value)}
                    />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label style={{ color: 'var(--text-secondary)' }}>
                        <FileText size={16} style={{ marginBottom: '-2px', marginRight: '6px' }} />
                        Content (Smart Text)
                    </label>
                    <div style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>
                        <Sparkles size={12} style={{ marginRight: '4px' }} />
                        Supports Week 1 - Topic format
                    </div>
                </div>

                {error && <div style={{ color: '#ff4d4d', marginBottom: '1rem' }}>{error}</div>}

                <textarea
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
