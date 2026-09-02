import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import axios from 'axios'
import { ArrowLeft, FileText, Info, Save } from 'lucide-react'
import { getApiErrorMessage } from '../utils/apiErrors'
import { mergeEditableRoadmap, prepareEditableRoadmap } from '../utils/editableRoadmap'
import { MAX_ROADMAP_NAME_LENGTH } from '../utils/roadmapLimits'

import { API_URL, LOCAL_USER_ID } from '../config'

export default function Edit() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [textContent, setTextContent] = useState('')
    const [roadmapName, setRoadmapName] = useState('')
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState(null)
    const [savedTasks, setSavedTasks] = useState([])
    const [savedSections, setSavedSections] = useState([])
    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])

    const fetchRoadmapData = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/roadmaps/${id}/export`, { headers: authHeaders })
            const prepared = prepareEditableRoadmap(res.data)
            setRoadmapName(res.data.name)
            setTextContent(prepared.text)
            setSavedTasks(prepared.savedTasks)
            setSavedSections(prepared.savedSections)
        } catch (fetchError) {
            console.error('Failed to fetch roadmap', fetchError)
            setError('Could not load this roadmap.')
        } finally {
            setLoading(false)
        }
    }, [authHeaders, id])

    useEffect(() => {
        fetchRoadmapData()
    }, [fetchRoadmapData])

    const handleSave = async () => {
        if (saving) return
        setError(null)
        const normalizedName = roadmapName.trim()
        if (!normalizedName) {
            setError('Roadmap name is required.')
            return
        }
        if (normalizedName.length > MAX_ROADMAP_NAME_LENGTH) {
            setError(`Roadmap name must be ${MAX_ROADMAP_NAME_LENGTH} characters or fewer.`)
            return
        }
        setSaving(true)

        try {
            const tasks = mergeEditableRoadmap(textContent, savedTasks, savedSections)
            await axios.put(
                `${API_URL}/roadmaps/${id}/smart`,
                { name: normalizedName, tasks },
                { headers: authHeaders },
            )
            navigate(`/roadmap/${id}`)
        } catch (saveError) {
            console.error(saveError)
            setError(getApiErrorMessage(saveError, 'Failed to save roadmap.'))
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
        <main className="edit-page">
            <header className="edit-header">
                <button className="btn-secondary" onClick={() => navigate(-1)}>
                    <ArrowLeft size={16} /> Back
                </button>
                <div className="edit-heading">
                    <span className="eyebrow">Raw structure</span>
                    <h1>Edit roadmap</h1>
                </div>
                <button className="btn-primary" onClick={handleSave} disabled={saving}>
                    <Save size={16} /> {saving ? 'Saving…' : 'Save changes'}
                </button>
            </header>

            <div className="edit-workspace">
                <div className="form-group">
                    <label htmlFor="edit-roadmap-name">Roadmap name</label>
                    <input
                        id="edit-roadmap-name"
                        className="name-input"
                        value={roadmapName}
                        onChange={(event) => setRoadmapName(event.target.value)}
                        maxLength={MAX_ROADMAP_NAME_LENGTH}
                        required
                    />
                </div>

                <div className="editor-label-row">
                    <label htmlFor="roadmap-content"><FileText size={15} /> Roadmap outline</label>
                    <div className="format-hint">
                        <Info size={13} /> Keep task and section markers attached; they preserve notes, fields, and schedules during structural edits
                    </div>
                </div>

                {error && <div className="error-message" role="alert">{error}</div>}

                <textarea
                    id="roadmap-content"
                    className="code-editor"
                    value={textContent}
                    onChange={(event) => setTextContent(event.target.value)}
                    spellCheck="false"
                    rows={24}
                    placeholder="# Week 1&#10;- Task 1"
                />
            </div>
        </main>
    )
}
