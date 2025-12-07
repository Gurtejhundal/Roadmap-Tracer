import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Save, ArrowLeft, FileText, Sparkles } from 'lucide-react'
import { parseRoadmapText, formatRoadmapToText } from '../utils/roadmapParser'

import { API_URL } from '../config'

export default function Edit() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [textContent, setTextContent] = useState('')
    const [roadmapName, setRoadmapName] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        fetchRoadmapData()
    }, [id])

    const fetchRoadmapData = async () => {
        try {
            // We fetch the export format { name, tasks }
            const res = await axios.get(`${API_URL}/roadmaps/${id}/export`)
            setRoadmapName(res.data.name)
            // Convert JSON tasks to Text format
            const formattedText = formatRoadmapToText(res.data)
            setTextContent(formattedText)
        } catch (err) {
            console.error("Failed to fetch roadmap", err)
            setTextContent("# Error fetching data\nCould not load roadmap.")
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async () => {
        setError(null)
        setSaving(true)

        try {
            // Parse text back to JSON tasks
            const tasks = parseRoadmapText(textContent)

            // We need to send { name, tasks } to PUT /roadmaps/{id}
            // Wait, PUT update_roadmap only takes { text: str } in main.py? 
            // Let's check main.py... It takes `roadmap: RoadmapUpdate`.
            // RoadmapUpdate is { text: str }. 
            // `db.update_roadmap_content` calls parser on the text.
            // Oh right, the backend parser logic in `roadmap_parser.py` might be different from our frontend logic!
            // BUT, `main.py` uses `parser.parse_roadmap`. 
            // If I send "Week 1\nTask 1" as text, the backend parser needs to handle it.
            // OR I can change the endpoint directly to accept the structured tasks I just parsed.

            // Actually, the user wants the frontend "Smart Import" logic to be the source of truth if we use that.
            // The current backend `update_roadmap` re-parses raw text.
            // If I send the `textContent` as `text`, does the backend parser handle "Week 1 - Task"?
            // I should stick to the pattern I established in "Smart Import" which uses `save_imported_roadmap`.
            // But `save_imported_roadmap` is for CREATING (INSERT).
            // For UPDATING, I should probably expose a similar endpoint or update `update_roadmap` to accept tasks or use the new parser.

            // EASIEST PATH: use the `/import` endpoint logic but for update.
            // OR, since I already built the parser in frontend, 
            // I can modify `update_roadmap` to accept `RoadmapImport` (name + tasks) essentially.

            // Let's try to verify if I can just send the clean text and let backend parse it?
            // The backend `roadmap_parser.py` might be outdated compared to my new frontend logic.
            // So relying on frontend parsing is safer.

            // Let's use `axios.put` but I need to make sure the backend accepts the structured tasks.
            // It currently expects `RoadmapUpdate(text=...)`.
            // I will update the backend `update_roadmap` to accept structured tasks if possible, 
            // OR I can make a new endpoint `PUT /roadmaps/{id}/smart_update`.

            // Let's go with a new endpoint to be safe and clean.
            // `PUT /roadmaps/{id}/structure`

            // Since I can't modify backend in this single tool call, I will assume I'll add the endpoint next.
            // For now, I'll write the frontend code to call this hypothetically new endpoint `PUT /roadmaps/{id}/import_update` which takes `{ name, tasks }`.

            const payload = {
                name: roadmapName,
                tasks: tasks
            }

            await axios.put(`${API_URL}/roadmaps/${id}/smart`, payload)

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
                        Supports "Week 1 - Topic" format
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
