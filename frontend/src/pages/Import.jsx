import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { AlertCircle, Check, FileText, FileUp, Upload, X } from 'lucide-react'

import { API_URL, LOCAL_USER_ID } from '../config'
import { getApiErrorMessage } from '../utils/apiErrors'
import { MAX_ROADMAP_NAME_LENGTH, MAX_ROADMAP_TEXT_LENGTH } from '../utils/roadmapLimits'

const SUPPORTED_FILE_COPY = 'PDF, DOCX, TXT, Markdown, JSON, CSV, and YAML · 8 MB maximum'
const MAX_FILE_BYTES = 8 * 1024 * 1024
const SUPPORTED_EXTENSIONS = new Set([
    'pdf', 'docx', 'txt', 'md', 'markdown', 'json', 'csv', 'yaml', 'yml', 'rst', 'log',
])

const fileStem = (filename = '') => filename.replace(/\.[^/.]+$/, '')

const isSupportedFile = (file) => {
    const extension = file?.name?.split('.').pop()?.toLowerCase()
    return Boolean(
        (extension && SUPPORTED_EXTENSIONS.has(extension))
        || file?.type === 'application/pdf'
        || file?.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        || file?.type?.startsWith('text/'),
    )
}

export default function Import() {
    const navigate = useNavigate()
    const fileInputRef = useRef(null)
    const [name, setName] = useState('')
    const [rawText, setRawText] = useState('')
    const [selectedFile, setSelectedFile] = useState(null)
    const [sourceMode, setSourceMode] = useState('file')
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)

    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])
    const inferredName = fileStem(selectedFile?.name)

    const selectFile = (file) => {
        if (!file) return false
        if (!isSupportedFile(file)) {
            setError('Unsupported file type. Choose PDF, DOCX, or a supported text document.')
            return false
        }
        if (file.size > MAX_FILE_BYTES) {
            setError('Roadmap file must be 8 MB or smaller.')
            return false
        }

        const previousInferredName = fileStem(selectedFile?.name)
        setSelectedFile(file)
        setSourceMode('file')
        setError(null)
        if (!name.trim() || name.trim() === previousInferredName) setName(fileStem(file.name))
        return true
    }

    const handleFileChange = (event) => {
        const file = event.target.files?.[0]
        if (!file) return
        if (!selectFile(file)) event.target.value = ''
    }

    const handleFileDrop = (event) => {
        event.preventDefault()
        const file = event.dataTransfer.files?.[0]
        if (selectFile(file) && fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const clearFile = () => {
        setSelectedFile(null)
        setError(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
    }

    const importText = async (roadmapName) => {
        if (!rawText.trim()) throw new Error('Paste roadmap text or switch to file upload.')

        return axios.post(
            `${API_URL}/roadmaps`,
            { name: roadmapName, text: rawText },
            { headers: authHeaders },
        )
    }

    const importFile = async (roadmapName) => {
        if (!selectedFile) throw new Error('Choose a roadmap file first.')
        if (selectedFile.size > MAX_FILE_BYTES) throw new Error('Roadmap file must be 8 MB or smaller.')

        const formData = new FormData()
        formData.append('name', roadmapName)
        formData.append('file', selectedFile)

        return axios.post(`${API_URL}/roadmaps/import-file`, formData, {
            headers: authHeaders,
        })
    }

    const handleSubmit = async (event) => {
        event.preventDefault()
        const roadmapName = name.trim() || inferredName
        if (!roadmapName) {
            setError('Roadmap name is required.')
            return
        }
        if (roadmapName.length > MAX_ROADMAP_NAME_LENGTH) {
            setError(`Roadmap name must be ${MAX_ROADMAP_NAME_LENGTH} characters or fewer.`)
            return
        }
        if (sourceMode === 'text' && rawText.length > MAX_ROADMAP_TEXT_LENGTH) {
            setError('Roadmap text must be 8 MB or smaller.')
            return
        }

        setError(null)
        setLoading(true)

        try {
            const res = sourceMode === 'file'
                ? await importFile(roadmapName)
                : await importText(roadmapName)
            navigate(`/roadmap/${res.data.id}`)
        } catch (importError) {
            console.error(importError)
            setError(getApiErrorMessage(importError, 'Failed to import roadmap.'))
        } finally {
            setLoading(false)
        }
    }

    return (
        <main className="import-page">
            <form className="form-container" onSubmit={handleSubmit} aria-busy={loading}>
                <span className="eyebrow">New document</span>
                <h1 className="section-title">Import a plan</h1>
                <p className="form-intro">Traqo reads the document’s hierarchy before creating tasks. Supporting content stays attached as notes and metadata instead of becoming noise.</p>

                <div className="import-capabilities" aria-label="Import behavior">
                    <span><Check size={14} /> Headings become sections</span>
                    <span><Check size={14} /> Table rows stay structured</span>
                    <span><Check size={14} /> Notes, code, and revision rules stay contextual</span>
                </div>

                <div className="import-source-switch" role="tablist" aria-label="Roadmap import source">
                    <button
                        type="button"
                        role="tab"
                        aria-selected={sourceMode === 'file'}
                        className={`source-tab ${sourceMode === 'file' ? 'active' : ''}`}
                        onClick={() => {
                            setSourceMode('file')
                            setError(null)
                        }}
                    >
                        <FileUp size={16} /> Upload file
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={sourceMode === 'text'}
                        className={`source-tab ${sourceMode === 'text' ? 'active' : ''}`}
                        onClick={() => {
                            setSourceMode('text')
                            setError(null)
                        }}
                    >
                        <FileText size={16} /> Paste text
                    </button>
                </div>

                <div className="form-group">
                    <label htmlFor="roadmap-name">Roadmap name</label>
                    <input
                        id="roadmap-name"
                        type="text"
                        placeholder="e.g. DSA foundation"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        maxLength={MAX_ROADMAP_NAME_LENGTH}
                        autoFocus
                    />
                </div>

                {sourceMode === 'file' ? (
                    <div className="form-group">
                        <label htmlFor="roadmap-file">Document</label>
                        <label
                            className={`file-dropzone ${selectedFile ? 'has-file' : ''}`}
                            htmlFor="roadmap-file"
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={handleFileDrop}
                        >
                            <input
                                ref={fileInputRef}
                                id="roadmap-file"
                                type="file"
                                accept=".pdf,.docx,.txt,.md,.markdown,.json,.csv,.yaml,.yml,.rst,.log,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                onChange={handleFileChange}
                            />
                            <Upload size={22} aria-hidden="true" />
                            <span>{selectedFile ? selectedFile.name : 'Choose a file or drop it here'}</span>
                            <small>{SUPPORTED_FILE_COPY}</small>
                        </label>
                        {selectedFile && (
                            <button type="button" className="btn-quiet clear-file-btn" onClick={clearFile}>
                                <X size={15} /> Remove file
                            </button>
                        )}
                    </div>
                ) : (
                    <div className="form-group">
                        <label htmlFor="roadmap-text">Plan content</label>
                        <textarea
                            id="roadmap-text"
                            className="code-editor import-editor"
                            rows="14"
                            placeholder={`Docker setup\n- Install Docker Desktop\n- Build and run an image\n\nDeployment\n- Push the image to a registry\n- Deploy the container`}
                            value={rawText}
                            onChange={(event) => setRawText(event.target.value)}
                            maxLength={MAX_ROADMAP_TEXT_LENGTH}
                        />
                    </div>
                )}

                {error && (
                    <div className="error-message" role="alert">
                        <AlertCircle size={17} /> {error}
                    </div>
                )}

                <button className="btn-primary full-width" type="submit" disabled={loading}>
                    {loading ? 'Analyzing document…' : 'Import roadmap'}
                </button>
            </form>
        </main>
    )
}
