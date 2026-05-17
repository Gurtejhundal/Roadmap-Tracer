import { useCallback, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import axios from 'axios'
import { Plus, Calendar, ArrowRight, Trash2 } from 'lucide-react'

import { API_URL, LOCAL_USER_ID } from '../config'

export default function Home() {
    const [roadmaps, setRoadmaps] = useState([])
    const [loading, setLoading] = useState(true)

    const fetchRoadmaps = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/roadmaps/`, {
                headers: { 'X-Local-User-Id': LOCAL_USER_ID }
            })
            setRoadmaps(res.data)
        } catch (error) {
            console.error("Failed to fetch roadmaps", error)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchRoadmaps()
    }, [fetchRoadmaps])

    const deleteRoadmap = async (e, id) => {
        e.preventDefault() // Prevent navigation
        e.stopPropagation()
        if (!window.confirm("Are you sure you want to delete this roadmap?")) return

        try {
            await axios.delete(`${API_URL}/roadmaps/${id}`, {
                headers: { 'X-Local-User-Id': LOCAL_USER_ID }
            })
            setRoadmaps(currentRoadmaps => currentRoadmaps.filter(r => r.id !== id))
        } catch (error) {
            console.error("Failed to delete roadmap", error)
        }
    }

    return (
        <div className="home-page">
            <div className="hero-section">
                <h2 className="section-title">Your Roadmaps</h2>
            </div>

            {loading ? (
                <div className="loading">Loading...</div>
            ) : (
                <div className="grid-container">
                    {/* New Roadmap Card */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="roadmap-card-wrapper"
                    >
                        <Link to="/import" className="roadmap-card-link">
                            <div className="roadmap-card create-card">
                                <Plus size={40} strokeWidth={1.5} />
                                <span>Create New</span>
                            </div>
                        </Link>
                    </motion.div>

                    {roadmaps.map((roadmap, index) => {
                        const totalTasks = roadmap.total_tasks || 0
                        const completedTasks = roadmap.completed_tasks || 0
                        const percentage = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0

                        return (
                        <motion.div
                            key={roadmap.id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: (index + 1) * 0.1 }}
                            className="roadmap-card-wrapper"
                        >
                            <Link to={`/roadmap/${roadmap.id}`} className="roadmap-card-link">
                                <div className="roadmap-card">
                                    <div className="card-header">
                                        <h3>{roadmap.name}</h3>
                                        <button
                                            type="button"
                                            className="icon-btn delete-btn"
                                            aria-label={`Delete ${roadmap.name}`}
                                            onClick={(e) => deleteRoadmap(e, roadmap.id)}
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>

                                    <div className="progress-section">
                                        <div className="progress-info">
                                            <span className="progress-text">{completedTasks}/{totalTasks} tasks</span>
                                            <span className="progress-percentage">{percentage}%</span>
                                        </div>
                                        <div className="progress-bar">
                                            <div className="progress-fill" style={{ width: `${percentage}%` }} />
                                        </div>
                                    </div>

                                    <div className="card-footer">
                                        <div className="date">
                                            <Calendar size={14} style={{ marginRight: '6px' }} />
                                            {new Date(roadmap.created_at).toLocaleDateString()}
                                        </div>
                                        <ArrowRight className="arrow" size={18} />
                                    </div>
                                </div>
                            </Link>
                        </motion.div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
