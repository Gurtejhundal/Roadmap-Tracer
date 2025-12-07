import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import axios from 'axios'
import { Plus, Calendar, ArrowRight, Trash2 } from 'lucide-react'

import { API_URL } from '../config'

import { useAuth } from '@clerk/clerk-react'

export default function Home() {
    const { userId, isLoaded } = useAuth()
    const [roadmaps, setRoadmaps] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (isLoaded && userId) {
            fetchRoadmaps()
        }
    }, [isLoaded, userId])

    const fetchRoadmaps = async () => {
        try {
            const res = await axios.get(`${API_URL}/roadmaps/`, {
                headers: { 'X-Clerk-User-Id': userId }
            })
            setRoadmaps(res.data)
        } catch (error) {
            console.error("Failed to fetch roadmaps", error)
        } finally {
            setLoading(false)
        }
    }

    const deleteRoadmap = async (e, id) => {
        e.preventDefault() // Prevent navigation
        if (!window.confirm("Are you sure you want to delete this roadmap?")) return

        try {
            await axios.delete(`${API_URL}/roadmaps/${id}`, {
                headers: { 'X-Clerk-User-Id': userId }
            })
            setRoadmaps(roadmaps.filter(r => r.id !== id))
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

                    {roadmaps.map((roadmap, index) => (
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
                                            className="icon-btn delete-btn"
                                            onClick={(e) => deleteRoadmap(e, roadmap.id)}
                                        >
                                            <Trash2 size={16} />
                                        </button>
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
                    ))}
                </div>
            )}
        </div>
    )
}
