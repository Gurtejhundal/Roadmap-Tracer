import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { AlertCircle, ArrowRight, FileText, Plus, RefreshCw, Trash2 } from 'lucide-react'

import { API_URL, LOCAL_USER_ID } from '../config'

export default function Home() {
    const [roadmaps, setRoadmaps] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    const fetchRoadmaps = useCallback(async () => {
        try {
            setError('')
            const res = await axios.get(`${API_URL}/roadmaps`, {
                headers: { 'X-Local-User-Id': LOCAL_USER_ID },
            })
            setRoadmaps(Array.isArray(res.data) ? res.data : [])
        } catch (fetchError) {
            console.error('Failed to fetch roadmaps', fetchError)
            setError('Could not load your roadmaps. Check that the local server is running.')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchRoadmaps()
    }, [fetchRoadmaps])

    const deleteRoadmap = async (event, id, name) => {
        event.preventDefault()
        event.stopPropagation()
        if (!window.confirm(`Delete “${name}”? This cannot be undone.`)) return

        try {
            await axios.delete(`${API_URL}/roadmaps/${id}`, {
                headers: { 'X-Local-User-Id': LOCAL_USER_ID },
            })
            setRoadmaps((current) => current.filter((roadmap) => roadmap.id !== id))
        } catch (deleteError) {
            console.error('Failed to delete roadmap', deleteError)
            setError('The roadmap could not be deleted. Try again.')
        }
    }

    return (
        <main className="home-page">
            <header className="hero-section">
                <div>
                    <span className="eyebrow">Workspace</span>
                    <h1 className="section-title">Your roadmaps</h1>
                    <p>Plans, checklists, study schedules, and project work in one quiet place.</p>
                </div>
                <Link to="/import" className="btn-primary hero-action"><Plus size={16} /> New</Link>
            </header>

            {loading ? (
                <div className="loading-state" role="status" aria-live="polite">
                    <span className="loading-spinner" aria-hidden="true" />
                    <strong>Opening your workspace</strong>
                    <span>Loading roadmaps and progress…</span>
                </div>
            ) : error && roadmaps.length === 0 ? (
                <div className="feedback-state error-state" role="alert">
                    <AlertCircle size={21} />
                    <div><strong>Roadmaps unavailable</strong><p>{error}</p></div>
                    <button className="btn-secondary" onClick={fetchRoadmaps}><RefreshCw size={15} /> Retry</button>
                </div>
            ) : (
                <section className="library-section" aria-labelledby="library-heading">
                    <div className="library-heading-row">
                        <h2 id="library-heading">All documents</h2>
                        <span>{roadmaps.length} {roadmaps.length === 1 ? 'roadmap' : 'roadmaps'}</span>
                    </div>

                    {error && <div className="inline-error" role="alert">{error}</div>}

                    {roadmaps.length === 0 ? (
                        <div className="empty-library">
                            <FileText size={24} aria-hidden="true" />
                            <div><strong>No roadmaps yet</strong><p>Import a PDF, paste a plan, or start a simple task list.</p></div>
                            <Link to="/import" className="btn-secondary"><Plus size={16} /> Create your first roadmap</Link>
                        </div>
                    ) : (
                        <div className="roadmap-list">
                            {roadmaps.map((roadmap) => {
                                const totalTasks = roadmap.total_tasks || 0
                                const completedTasks = roadmap.completed_tasks || 0
                                const percentage = totalTasks > 0
                                    ? Math.round((completedTasks / totalTasks) * 100)
                                    : 0

                                return (
                                    <div className="roadmap-row" key={roadmap.id}>
                                        <Link to={`/roadmap/${roadmap.id}`} className="roadmap-row-link" aria-label={`Open ${roadmap.name}`} />
                                        <span className="document-icon" aria-hidden="true"><FileText size={17} /></span>
                                        <span className="roadmap-row-main">
                                            <strong>{roadmap.name}</strong>
                                            <small>{completedTasks} of {totalTasks} tasks complete · {new Date(roadmap.created_at).toLocaleDateString()}</small>
                                        </span>
                                        <span className="roadmap-row-progress" aria-label={`${percentage}% complete`}>
                                            <span><i style={{ width: `${percentage}%` }} /></span>
                                            <small>{percentage}%</small>
                                        </span>
                                        <button
                                            type="button"
                                            className="icon-btn delete-btn"
                                            aria-label={`Delete ${roadmap.name}`}
                                            onClick={(event) => deleteRoadmap(event, roadmap.id, roadmap.name)}
                                        >
                                            <Trash2 size={15} />
                                        </button>
                                        <ArrowRight className="arrow" size={16} aria-hidden="true" />
                                    </div>
                                )
                            })}
                        </div>
                    )}
                </section>
            )}
        </main>
    )
}
