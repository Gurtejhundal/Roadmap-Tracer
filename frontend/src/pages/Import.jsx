import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import axios from 'axios'
import { AlertCircle, FileText, FileUp, Upload, X } from 'lucide-react'

import { API_URL, LOCAL_USER_ID } from '../config'

const SUPPORTED_FILE_COPY = 'PDF, DOCX, TXT, Markdown, JSON, CSV, YAML, and other text-based roadmap files'

export default function Import() {
    const navigate = useNavigate()
    const [name, setName] = useState('')
    const [rawText, setRawText] = useState('')
    const [selectedFile, setSelectedFile] = useState(null)
    const [sourceMode, setSourceMode] = useState('text')
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)

    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])

    const inferredName = selectedFile?.name?.replace(/\.[^/.]+$/, '') || ''

    const handleFileChange = (event) => {
        const file = event.target.files?.[0]
        if (!file) return

        setSelectedFile(file)
        setSourceMode('file')
        setError(null)
        if (!name.trim()) {
            setName(file.name.replace(/\.[^/.]+$/, ''))
        }
    }

    const clearFile = () => {
        setSelectedFile(null)
        setSourceMode('text')
    }

    const importText = async (roadmapName) => {
        if (!rawText.trim()) {
            throw new Error('Paste roadmap text or switch to file upload.')
        }

        return axios.post(
            `${API_URL}/roadmaps`,
            { name: roadmapName, text: rawText },
            { headers: authHeaders }
        )
    }

    const importFile = async (roadmapName) => {
        if (!selectedFile) {
            throw new Error('Choose a roadmap file first.')
        }

        const formData = new FormData()
        formData.append('name', roadmapName)
        formData.append('file', selectedFile)

        return axios.post(`${API_URL}/roadmaps/import-file`, formData, {
            headers: {
                ...authHeaders,
                'Content-Type': 'multipart/form-data',
            },
        })
    }

    const handleImport = async () => {
        const roadmapName = name.trim() || inferredName
        if (!roadmapName) {
            setError('Roadmap name is required.')
            return
        }

        setError(null)
        setLoading(true)

        try {
            const res = sourceMode === 'file'
                ? await importFile(roadmapName)
                : await importText(roadmapName)

            navigate(`/roadmap/${res.data.id}`)
        } catch (err) {
            console.error(err)
            setError(err.response?.data?.detail || err.message || 'Failed to import roadmap.')
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
                <h2 className="section-title">Import Roadmap</h2>

                <div className="import-source-switch" role="tablist" aria-label="Roadmap import source">
                    <button
                        type="button"
                        className={`source-tab ${sourceMode === 'text' ? 'active' : ''}`}
                        onClick={() => setSourceMode('text')}
                    >
                        <FileText size={16} />
                        Paste Text
                    </button>
                    <button
                        type="button"
                        className={`source-tab ${sourceMode === 'file' ? 'active' : ''}`}
                        onClick={() => setSourceMode('file')}
                    >
                        <FileUp size={16} />
                        Upload File
                    </button>
                </div>

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

                {sourceMode === 'text' ? (
                    <div className="form-group">
                        <label>
                            <FileText size={16} style={{ marginBottom: '-2px', marginRight: '6px' }} />
                            Roadmap Text
                        </label>
                        <textarea
                            className="code-editor import-editor"
                            rows="15"
                            placeholder={`Week 1: Foundations
- Learn the basics
- Build a small practice project

Week 2: Applied Work
- Ship a milestone
- Review weak areas`}
                            value={rawText}
                            onChange={(event) => setRawText(event.target.value)}
                        />
                    </div>
                ) : (
                    <div className="form-group">
                        <label>
                            <FileUp size={16} style={{ marginBottom: '-2px', marginRight: '6px' }} />
                            Roadmap File
                        </label>
                        <label className={`file-dropzone ${selectedFile ? 'has-file' : ''}`}>
                            <input
                                type="file"
                                accept=".pdf,.docx,.txt,.md,.markdown,.json,.csv,.yaml,.yml,.rst,.log,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                onChange={handleFileChange}
                            />
                            <Upload size={28} />
                            <span>{selectedFile ? selectedFile.name : 'Choose a roadmap file'}</span>
                            <small>{SUPPORTED_FILE_COPY}</small>
                        </label>
                        {selectedFile && (
                            <button type="button" className="btn-secondary clear-file-btn" onClick={clearFile}>
                                <X size={16} />
                                Remove file
                            </button>
                        )}
                    </div>
                )}

                {error && (
                    <div className="error-message">
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
                        {loading ? 'Importing...' : 'Import and Track'}
                    </button>
                </div>
            </motion.div>
        </div>
    )
}
