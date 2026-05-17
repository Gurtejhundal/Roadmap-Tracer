import { useCallback, useMemo, useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import axios from 'axios'
import {
    ArrowLeft,
    Calendar,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    Download,
    Edit2,
    FileText,
    Plus,
    Save,
    Search,
    Trash2,
    X,
} from 'lucide-react'
import TimeframeHeader from '../components/TimeframeHeader'

import jsPDF from 'jspdf'
import { Document, Packer, Paragraph, HeadingLevel } from 'docx'
import { saveAs } from 'file-saver'

import { API_URL, LOCAL_USER_ID } from '../config'

const statusFilters = [
    { value: 'all', label: 'All' },
    { value: 'open', label: 'Open' },
    { value: 'done', label: 'Done' },
]

export default function RoadmapView() {
    const { id } = useParams()
    const [tasks, setTasks] = useState([])
    const [roadmap, setRoadmap] = useState(null)
    const [timeframes, setTimeframes] = useState([])
    const [isEditingName, setIsEditingName] = useState(false)
    const [newName, setNewName] = useState('')
    const [searchTerm, setSearchTerm] = useState('')
    const [statusFilter, setStatusFilter] = useState('all')
    const [collapsedGroups, setCollapsedGroups] = useState(() => new Set())
    const [editingTaskId, setEditingTaskId] = useState(null)
    const [editingTaskTitle, setEditingTaskTitle] = useState('')
    const [newTaskTitles, setNewTaskTitles] = useState({})
    const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)
    const [isExporting, setIsExporting] = useState(false)
    const roadmapRef = useRef(null)
    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])

    const fetchData = useCallback(async () => {
        try {
            const [rRes, tRes] = await Promise.all([
                axios.get(`${API_URL}/roadmaps/${id}`, { headers: authHeaders }),
                axios.get(`${API_URL}/roadmaps/${id}/tasks`, { headers: authHeaders }),
            ])
            setRoadmap(rRes.data)
            setNewName(rRes.data.name)
            setTasks(tRes.data)
        } catch (error) {
            console.error('Failed to fetch data', error)
        }
    }, [authHeaders, id])

    const fetchTimeframes = useCallback(async () => {
        try {
            const res = await axios.get(`${API_URL}/roadmaps/${id}/timeframes`, { headers: authHeaders })
            setTimeframes(res.data)
        } catch (error) {
            console.error('Failed to fetch timeframes', error)
        }
    }, [authHeaders, id])

    useEffect(() => {
        fetchData()
        fetchTimeframes()
    }, [fetchData, fetchTimeframes])

    const groupedTasks = useMemo(() => {
        return tasks.reduce((acc, task) => {
            const group = task.timeframe_label || 'Unassigned'
            if (!acc[group]) acc[group] = []
            acc[group].push(task)
            return acc
        }, {})
    }, [tasks])

    const visibleGroupedTasks = useMemo(() => {
        const query = searchTerm.trim().toLowerCase()

        return Object.entries(groupedTasks)
            .map(([group, groupTasks]) => {
                const filtered = groupTasks.filter((task) => {
                    const matchesSearch =
                        !query ||
                        task.title.toLowerCase().includes(query) ||
                        group.toLowerCase().includes(query)
                    const matchesStatus =
                        statusFilter === 'all' ||
                        (statusFilter === 'done' && task.is_done) ||
                        (statusFilter === 'open' && !task.is_done)
                    return matchesSearch && matchesStatus
                })
                return [group, filtered]
            })
            .filter(([, groupTasks]) => groupTasks.length > 0)
    }, [groupedTasks, searchTerm, statusFilter])

    const totalTasks = tasks.length
    const completedTasks = tasks.filter((task) => task.is_done).length
    const visibleTasksCount = visibleGroupedTasks.reduce((count, [, groupTasks]) => count + groupTasks.length, 0)
    const percentage = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0

    const toggleTask = async (taskId, currentStatus) => {
        setTasks((current) =>
            current.map((task) => (task.id === taskId ? { ...task, is_done: !currentStatus } : task))
        )
        try {
            await axios.put(
                `${API_URL}/tasks/${taskId}/status`,
                { is_done: !currentStatus },
                { headers: authHeaders }
            )
        } catch (error) {
            console.error('Failed to update task', error)
            setTasks((current) =>
                current.map((task) => (task.id === taskId ? { ...task, is_done: currentStatus } : task))
            )
        }
    }

    const updateGroupStatus = async (groupTasks, isDone) => {
        const timeframeId = groupTasks[0]?.timeframe_id
        if (!timeframeId) return

        const taskIds = new Set(groupTasks.map((task) => task.id))
        setTasks((current) =>
            current.map((task) => (taskIds.has(task.id) ? { ...task, is_done: isDone } : task))
        )

        try {
            await axios.put(
                `${API_URL}/timeframes/${timeframeId}/tasks/status`,
                { is_done: isDone },
                { headers: authHeaders }
            )
        } catch (error) {
            console.error('Failed to update group status', error)
            fetchData()
        }
    }

    const createTask = async (group) => {
        const title = (newTaskTitles[group] || '').trim()
        if (!title) return

        try {
            const response = await axios.post(
                `${API_URL}/tasks`,
                {
                    roadmap_id: Number(id),
                    timeframe_label: group,
                    title,
                },
                { headers: authHeaders }
            )
            setTasks((current) => [...current, response.data])
            setNewTaskTitles((current) => ({ ...current, [group]: '' }))
            fetchTimeframes()
        } catch (error) {
            console.error('Failed to create task', error)
        }
    }

    const saveTaskTitle = async (taskId) => {
        const title = editingTaskTitle.trim()
        if (!title) return

        const previousTasks = tasks
        setTasks((current) =>
            current.map((task) => (task.id === taskId ? { ...task, title } : task))
        )
        setEditingTaskId(null)
        setEditingTaskTitle('')

        try {
            const response = await axios.put(
                `${API_URL}/tasks/${taskId}`,
                { title },
                { headers: authHeaders }
            )
            setTasks((current) =>
                current.map((task) => (task.id === taskId ? response.data : task))
            )
        } catch (error) {
            console.error('Failed to rename task', error)
            setTasks(previousTasks)
        }
    }

    const deleteTask = async (taskId) => {
        if (!window.confirm('Delete this task?')) return

        const previousTasks = tasks
        setTasks((current) => current.filter((task) => task.id !== taskId))
        try {
            await axios.delete(`${API_URL}/tasks/${taskId}`, { headers: authHeaders })
        } catch (error) {
            console.error('Failed to delete task', error)
            setTasks(previousTasks)
        }
    }

    const saveName = async () => {
        if (!newName.trim()) return
        try {
            await axios.put(`${API_URL}/roadmaps/${id}/name`, { name: newName }, { headers: authHeaders })
            setRoadmap({ ...roadmap, name: newName })
            setIsEditingName(false)
        } catch (error) {
            console.error('Failed to rename roadmap', error)
        }
    }

    const toggleGroupCollapsed = (group) => {
        setCollapsedGroups((current) => {
            const next = new Set(current)
            if (next.has(group)) {
                next.delete(group)
            } else {
                next.add(group)
            }
            return next
        })
    }

    const collapseAllGroups = () => {
        setCollapsedGroups(new Set(Object.keys(groupedTasks)))
    }

    const expandAllGroups = () => {
        setCollapsedGroups(new Set())
    }

    const startEditingTask = (task) => {
        setEditingTaskId(task.id)
        setEditingTaskTitle(task.title)
    }

    const handleExportPDF = () => {
        setIsExporting(true)
        setIsExportMenuOpen(false)
        try {
            const doc = new jsPDF()
            doc.setFont('helvetica', 'bold')
            doc.setFontSize(24)
            doc.text(roadmap.name, 20, 20)

            doc.setFont('helvetica', 'normal')
            doc.setFontSize(10)
            doc.setTextColor(100)
            doc.text(`Generated by TRAQO - ${new Date().toLocaleDateString()}`, 20, 28)

            let yPos = 40
            Object.entries(groupedTasks).forEach(([group, groupTasks]) => {
                if (yPos > 270) {
                    doc.addPage()
                    yPos = 20
                }

                doc.setFont('helvetica', 'bold')
                doc.setFontSize(16)
                doc.setTextColor(0)
                doc.text(group.toUpperCase(), 20, yPos)
                yPos += 10

                doc.setFont('helvetica', 'normal')
                doc.setFontSize(12)

                groupTasks.forEach((task) => {
                    if (yPos > 280) {
                        doc.addPage()
                        yPos = 20
                    }
                    doc.text(`- ${task.title}`, 25, yPos)
                    yPos += 8
                })

                yPos += 10
            })

            doc.save(`${roadmap.name.replace(/\s+/g, '_')}_Roadmap.pdf`)
        } catch (err) {
            console.error('PDF Export failed', err)
            alert('Failed to generate PDF')
        } finally {
            setIsExporting(false)
        }
    }

    const handleExportDoc = async () => {
        setIsExporting(true)
        setIsExportMenuOpen(false)
        try {
            const children = [
                new Paragraph({
                    text: roadmap.name,
                    heading: HeadingLevel.TITLE,
                    spacing: { after: 300 },
                }),
                new Paragraph({
                    text: `Generated by TRAQO - ${new Date().toLocaleDateString()}`,
                    spacing: { after: 500 },
                    style: 'Subtitle',
                }),
            ]

            Object.entries(groupedTasks).forEach(([group, groupTasks]) => {
                children.push(
                    new Paragraph({
                        text: group.toUpperCase(),
                        heading: HeadingLevel.HEADING_1,
                        spacing: { before: 400, after: 200 },
                    })
                )

                groupTasks.forEach((task) => {
                    children.push(
                        new Paragraph({
                            text: task.title,
                            bullet: { level: 0 },
                        })
                    )
                })
            })

            const doc = new Document({
                sections: [{ properties: {}, children }],
            })

            const blob = await Packer.toBlob(doc)
            saveAs(blob, `${roadmap.name.replace(/\s+/g, '_')}.docx`)
        } catch (err) {
            console.error('Word Export failed', err)
            alert('Failed to generate Word Doc')
        } finally {
            setIsExporting(false)
        }
    }

    if (!roadmap) return <div className="loading">Loading...</div>

    return (
        <div className="roadmap-view" ref={roadmapRef}>
            <div className="view-header" data-html2canvas-ignore>
                <div className="header-left">
                    <Link to="/">
                        <button className="btn-primary back-btn">
                            <ArrowLeft size={18} /> Back
                        </button>
                    </Link>
                </div>

                <div className="header-right">
                    <div className="export-menu-container">
                        <button
                            className="btn-primary"
                            onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
                            disabled={isExporting}
                        >
                            {isExporting ? (
                                <span className="spinner-small"></span>
                            ) : (
                                <Download size={16} style={{ marginRight: '8px' }} />
                            )}
                            Save As
                            <ChevronDown size={14} style={{ marginLeft: '6px' }} />
                        </button>

                        <AnimatePresence>
                            {isExportMenuOpen && (
                                <motion.div
                                    className="dropdown-menu glass-panel"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: 10 }}
                                >
                                    <button className="dropdown-item" onClick={handleExportPDF}>
                                        <FileText size={16} /> PDF
                                    </button>
                                    <button className="dropdown-item" onClick={handleExportDoc}>
                                        <FileText size={16} /> Word Doc
                                    </button>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    <Link to={`/edit/${id}`}>
                        <button className="btn-primary">
                            <Edit2 size={16} style={{ marginRight: '8px' }} />
                            Edit Raw
                        </button>
                    </Link>
                </div>
            </div>

            <div className="roadmap-hero">
                <div className="hero-top">
                    {isEditingName ? (
                        <div className="edit-name-container">
                            <input
                                type="text"
                                value={newName}
                                onChange={(event) => setNewName(event.target.value)}
                                className="name-input"
                                autoFocus
                            />
                            <button className="icon-btn save-btn" onClick={saveName} aria-label="Save roadmap name">
                                <Save size={20} />
                            </button>
                            <button
                                className="icon-btn cancel-btn"
                                onClick={() => setIsEditingName(false)}
                                aria-label="Cancel roadmap rename"
                            >
                                <X size={20} />
                            </button>
                        </div>
                    ) : (
                        <div className="title-container">
                            <h2>{roadmap.name}</h2>
                            <button
                                className="icon-btn edit-name-btn"
                                onClick={() => setIsEditingName(true)}
                                data-html2canvas-ignore
                                aria-label="Rename roadmap"
                            >
                                <Edit2 size={16} />
                            </button>
                        </div>
                    )}
                    <span className="date-badge">
                        <Calendar size={14} /> {new Date(roadmap.created_at).toLocaleDateString()}
                    </span>
                </div>

                <div className="progress-section large">
                    <div className="progress-info">
                        <span className="progress-text">
                            {completedTasks}/{totalTasks} tasks completed
                        </span>
                        <span className="progress-percentage">{percentage}%</span>
                    </div>
                    <div className="progress-bar large">
                        <motion.div
                            className="progress-fill"
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 0.8 }}
                        />
                    </div>
                </div>

                <div className="roadmap-tools" data-html2canvas-ignore>
                    <div className="roadmap-search">
                        <Search size={18} />
                        <input
                            type="search"
                            placeholder="Search tasks or sections"
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                        />
                    </div>

                    <div className="tool-row">
                        <div className="segmented-control" aria-label="Task status filter">
                            {statusFilters.map((filter) => (
                                <button
                                    key={filter.value}
                                    type="button"
                                    className={statusFilter === filter.value ? 'active' : ''}
                                    onClick={() => setStatusFilter(filter.value)}
                                >
                                    {filter.label}
                                </button>
                            ))}
                        </div>

                        <div className="compact-actions">
                            <button className="btn-secondary btn-small" onClick={expandAllGroups}>
                                Expand all
                            </button>
                            <button className="btn-secondary btn-small" onClick={collapseAllGroups}>
                                Collapse all
                            </button>
                        </div>
                    </div>

                    <div className="result-summary">
                        Showing {visibleTasksCount} of {totalTasks} tasks across {visibleGroupedTasks.length} sections
                    </div>
                </div>
            </div>

            <div className="timeline">
                {visibleGroupedTasks.length === 0 ? (
                    <div className="empty-state glass-panel">
                        No tasks match the current search and filter.
                    </div>
                ) : (
                    visibleGroupedTasks.map(([group, groupTasks], groupIndex) => {
                        const timeframeData = timeframes.find((timeframe) => timeframe.label === group)
                        const allGroupTasks = groupedTasks[group] || []
                        const groupDoneCount = allGroupTasks.filter((task) => task.is_done).length
                        const groupIsDone = allGroupTasks.length > 0 && groupDoneCount === allGroupTasks.length
                        const isCollapsed = collapsedGroups.has(group)

                        return (
                            <motion.div
                                key={group}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: Math.min(groupIndex * 0.03, 0.3) }}
                                className="timeframe-group"
                            >
                                {timeframeData ? (
                                    <TimeframeHeader timeframe={timeframeData} onUpdate={fetchTimeframes} />
                                ) : (
                                    <h3 className="timeframe-label">{group}</h3>
                                )}

                                <div className="group-toolbar" data-html2canvas-ignore>
                                    <span className="group-progress">
                                        {groupDoneCount}/{allGroupTasks.length} done
                                    </span>
                                    <button
                                        type="button"
                                        className="btn-secondary btn-small"
                                        onClick={() => updateGroupStatus(allGroupTasks, !groupIsDone)}
                                    >
                                        {groupIsDone ? <Circle size={15} /> : <CheckCircle2 size={15} />}
                                        {groupIsDone ? 'Mark open' : 'Mark done'}
                                    </button>
                                    <button
                                        type="button"
                                        className="icon-btn"
                                        onClick={() => toggleGroupCollapsed(group)}
                                        aria-label={isCollapsed ? `Expand ${group}` : `Collapse ${group}`}
                                    >
                                        {isCollapsed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
                                    </button>
                                </div>

                                <AnimatePresence initial={false}>
                                    {!isCollapsed && (
                                        <motion.div
                                            className="tasks-list"
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: 'auto' }}
                                            exit={{ opacity: 0, height: 0 }}
                                        >
                                            {groupTasks.map((task) => {
                                                const isEditingTask = editingTaskId === task.id
                                                return (
                                                    <div
                                                        key={task.id}
                                                        className={`task-item glass-panel ${task.is_done ? 'done' : ''}`}
                                                        onClick={() => {
                                                            if (!isEditingTask) toggleTask(task.id, task.is_done)
                                                        }}
                                                    >
                                                        <div className={`custom-checkbox ${task.is_done ? 'checked' : ''}`} />

                                                        {isEditingTask ? (
                                                            <div
                                                                className="task-edit-row"
                                                                onClick={(event) => event.stopPropagation()}
                                                            >
                                                                <input
                                                                    value={editingTaskTitle}
                                                                    onChange={(event) => setEditingTaskTitle(event.target.value)}
                                                                    onKeyDown={(event) => {
                                                                        if (event.key === 'Enter') saveTaskTitle(task.id)
                                                                        if (event.key === 'Escape') setEditingTaskId(null)
                                                                    }}
                                                                    autoFocus
                                                                />
                                                                <button
                                                                    className="icon-btn save-btn"
                                                                    onClick={() => saveTaskTitle(task.id)}
                                                                    aria-label="Save task title"
                                                                >
                                                                    <Save size={17} />
                                                                </button>
                                                                <button
                                                                    className="icon-btn cancel-btn"
                                                                    onClick={() => setEditingTaskId(null)}
                                                                    aria-label="Cancel task edit"
                                                                >
                                                                    <X size={17} />
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            <>
                                                                <span className="task-title">{task.title}</span>
                                                                <div
                                                                    className="task-actions"
                                                                    onClick={(event) => event.stopPropagation()}
                                                                >
                                                                    <button
                                                                        className="icon-btn"
                                                                        onClick={() => startEditingTask(task)}
                                                                        aria-label="Edit task"
                                                                    >
                                                                        <Edit2 size={16} />
                                                                    </button>
                                                                    <button
                                                                        className="icon-btn delete-btn-visible"
                                                                        onClick={() => deleteTask(task.id)}
                                                                        aria-label="Delete task"
                                                                    >
                                                                        <Trash2 size={16} />
                                                                    </button>
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>
                                                )
                                            })}

                                            <div className="add-task-row" data-html2canvas-ignore>
                                                <input
                                                    value={newTaskTitles[group] || ''}
                                                    onChange={(event) =>
                                                        setNewTaskTitles((current) => ({
                                                            ...current,
                                                            [group]: event.target.value,
                                                        }))
                                                    }
                                                    onKeyDown={(event) => {
                                                        if (event.key === 'Enter') createTask(group)
                                                    }}
                                                    placeholder={`Add task to ${group}`}
                                                />
                                                <button className="btn-primary btn-small" onClick={() => createTask(group)}>
                                                    <Plus size={16} />
                                                    Add
                                                </button>
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </motion.div>
                        )
                    })
                )}
            </div>

            <style>{`
                .export-menu-container {
                    position: relative;
                }
                .dropdown-menu {
                    position: absolute;
                    top: 100%;
                    right: 0;
                    margin-top: 0.5rem;
                    background: #1a1a2e;
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 12px;
                    padding: 0.5rem;
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                    min-width: 160px;
                    z-index: 50;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                }
                .dropdown-item {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    background: transparent;
                    border: none;
                    color: #fff;
                    padding: 0.6rem 1rem;
                    border-radius: 8px;
                    cursor: pointer;
                    text-align: left;
                    font-size: 0.9rem;
                    transition: all 0.2s;
                }
                .dropdown-item:hover {
                    background: rgba(255,255,255,0.1);
                }
                .spinner-small {
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-top: 2px solid white;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    display: inline-block;
                    margin-right: 8px;
                }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            `}</style>
        </div>
    )
}
