import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import {
    Bookmark,
    CalendarDays,
    Check,
    CheckSquare,
    Code2,
    Edit2,
    ExternalLink,
    Flag,
    Hash,
    Link as LinkIcon,
    Plus,
    RotateCcw,
    StickyNote,
    Tag,
    Trash2,
    X,
} from 'lucide-react'

import { API_URL, LOCAL_USER_ID } from '../config'
import { formatSemanticValue, getSemanticBlockDisplay, isImportedSemanticBlock } from '../utils/taskSemantics'

const BLOCK_OPTIONS = [
    {
        key: 'note',
        label: 'Note',
        description: 'Add context or working notes',
        icon: StickyNote,
        type: 'note',
        data: { label: 'Note', text: '', source: 'user' },
    },
    {
        key: 'checklist',
        label: 'Checklist',
        description: 'Add a small list of steps',
        icon: CheckSquare,
        type: 'checklist',
        data: { label: 'Checklist', items: [{ id: 'item-1', text: '', checked: false }], source: 'user' },
    },
    {
        key: 'counter',
        label: 'Counter',
        description: 'Track attempts, repetitions, or quantity',
        icon: Hash,
        type: 'counter',
        data: { label: 'Counter', value: 0, step: 1, source: 'user' },
    },
    {
        key: 'bookmark',
        label: 'Bookmark',
        description: 'Keep a useful link with the task',
        icon: LinkIcon,
        type: 'bookmark',
        data: { label: 'Bookmark', url: '', bookmarked: true, source: 'user' },
    },
    {
        key: 'date',
        label: 'Due date',
        description: 'Set a date for this work',
        icon: CalendarDays,
        type: 'date',
        data: { label: 'Due date', date: '', source: 'user' },
    },
    {
        key: 'label',
        label: 'Label',
        description: 'Add a status or category',
        icon: Tag,
        type: 'label',
        data: { label: 'Label', value: '', source: 'user' },
    },
    {
        key: 'code',
        label: 'Code',
        description: 'Keep a snippet or command',
        icon: Code2,
        type: 'code',
        data: { label: 'Code', language: '', code: '', source: 'user' },
    },
    {
        key: 'revision',
        label: 'Revision',
        description: 'Count completed review passes',
        icon: RotateCcw,
        type: 'counter',
        data: { label: 'Revision', value: 0, step: 1, preset: 'revision', source: 'user' },
    },
    {
        key: 'revisit',
        label: 'Revisit',
        description: 'Mark this task for another pass',
        icon: Flag,
        type: 'bookmark',
        data: { label: 'Revisit', bookmarked: true, preset: 'revisit', source: 'user' },
    },
]

const legacyPropertyPattern = /^(?:revision\s*count|revisit)$/i

function asNumber(value, fallback = 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
}

function isSafeUrl(value) {
    return /^https?:\/\//i.test(String(value || '').trim())
}

function uniqueTaskIds(tasks) {
    return [...new Set((tasks || []).map((item) => Number(item?.id)).filter(Number.isFinite))]
}

function newChecklistItem() {
    return {
        id: `item-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        text: '',
        checked: false,
    }
}

function checklistItems(value) {
    if (!Array.isArray(value)) return []
    return value.map((item, index) => ({
        id: String(item?.id || `item-${index + 1}`),
        text: String(item?.text || ''),
        checked: item?.checked === true,
    }))
}

function returnedBlocks(payload) {
    if (Array.isArray(payload)) return payload
    for (const key of ['blocks', 'created', 'items']) {
        if (Array.isArray(payload?.[key])) return payload[key]
    }
    return []
}

function BlockItem({ block, taskTitle, onChange, onDelete, onError }) {
    const [draft, setDraft] = useState(() => ({ ...(block.data || {}) }))
    const [pendingSaves, setPendingSaves] = useState(0)
    const draftRef = useRef(draft)
    const persistedBlockRef = useRef(block)
    const saveQueueRef = useRef(Promise.resolve())
    const saveVersionRef = useRef(0)
    const mountedRef = useRef(true)
    const saving = pendingSaves > 0

    useLayoutEffect(() => {
        draftRef.current = draft
    }, [draft])

    useEffect(() => {
        mountedRef.current = true
        return () => {
            mountedRef.current = false
        }
    }, [])

    const persist = (nextData) => {
        const resolved = { ...draftRef.current, ...nextData }
        draftRef.current = resolved
        setDraft(resolved)
        const version = saveVersionRef.current + 1
        saveVersionRef.current = version
        setPendingSaves((current) => current + 1)

        const operation = saveQueueRef.current
            .catch(() => null)
            .then(async () => {
                const savedBlock = await onChange(persistedBlockRef.current, resolved)
                if (savedBlock?.id === block.id) persistedBlockRef.current = savedBlock
                if (
                    mountedRef.current
                    && version === saveVersionRef.current
                    && draftRef.current === resolved
                    && savedBlock?.data
                ) {
                    const savedData = { ...savedBlock.data }
                    draftRef.current = savedData
                    setDraft(savedData)
                }
            })
            .catch((saveError) => {
                console.error('Unexpected task block save failure', saveError)
                onError?.('A block change could not be saved.')
            })
            .finally(() => {
                if (mountedRef.current) setPendingSaves((current) => Math.max(0, current - 1))
            })

        saveQueueRef.current = operation
        return operation
    }

    const deleteButton = (
        <button
            type="button"
            className="block-delete icon-btn"
            onClick={() => onDelete(block)}
            disabled={saving}
            aria-label={`Remove ${draft.label || block.type} block from ${taskTitle}`}
        >
            <Trash2 size={14} />
        </button>
    )

    const savingIndicator = (label) => saving && (
        <span className="block-saving" role="status" aria-live="polite">
            <span className="sr-only">
                Saving {label}; {pendingSaves} {pendingSaves === 1 ? 'change' : 'changes'} pending
            </span>
        </span>
    )

    if (block.type === 'note') {
        return (
            <div className="task-block note-block">
                <StickyNote size={15} aria-hidden="true" />
                <div className="note-fields">
                    <input
                        className="block-label-input"
                        value={draft.label || ''}
                        placeholder="Note"
                        aria-label={`Note label for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                        onBlur={() => persist({ label: draft.label || 'Note' })}
                    />
                    <textarea
                        value={draft.text || ''}
                        placeholder="Write a note…"
                        aria-label={`${draft.label || 'Note'} for ${taskTitle}`}
                        rows={Math.max(1, String(draft.text || '').split('\n').length)}
                        onChange={(event) => setDraft((current) => ({ ...current, text: event.target.value }))}
                        onBlur={() => persist({ text: draft.text || '' })}
                    />
                </div>
                <div className="block-inline-actions">
                    {savingIndicator('note')}
                    {deleteButton}
                </div>
            </div>
        )
    }

    if (block.type === 'checklist') {
        const items = checklistItems(draft.items)
        const setItems = (nextItems) => persist({ items: nextItems })
        return (
            <div className="task-block checklist-block">
                <CheckSquare size={15} aria-hidden="true" />
                <div className="checklist-fields">
                    <input
                        className="block-label-input"
                        value={draft.label || ''}
                        placeholder="Checklist"
                        aria-label={`Checklist label for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                        onBlur={() => persist({ label: draft.label || 'Checklist' })}
                    />
                    <div className="checklist-items">
                        {items.map((item, index) => (
                            <div className="checklist-item" key={item.id}>
                                <input
                                    type="checkbox"
                                    checked={item.checked}
                                    aria-label={`Mark checklist item ${index + 1} ${item.checked ? 'open' : 'complete'}`}
                                    onChange={(event) => setItems(items.map((current) => (
                                        current.id === item.id ? { ...current, checked: event.target.checked } : current
                                    )))}
                                />
                                <input
                                    value={item.text}
                                    placeholder="Checklist item"
                                    aria-label={`Checklist item ${index + 1} for ${taskTitle}`}
                                    onChange={(event) => {
                                        const text = event.target.value
                                        setDraft((current) => ({
                                            ...current,
                                            items: checklistItems(current.items).map((currentItem) => (
                                                currentItem.id === item.id ? { ...currentItem, text } : currentItem
                                            )),
                                        }))
                                    }}
                                    onBlur={() => persist({ items: checklistItems(draft.items) })}
                                />
                                <button
                                    type="button"
                                    className="checklist-remove icon-btn"
                                    onClick={() => setItems(items.filter((current) => current.id !== item.id))}
                                    aria-label={`Remove checklist item ${index + 1}`}
                                >
                                    <X size={13} />
                                </button>
                            </div>
                        ))}
                    </div>
                    <button
                        type="button"
                        className="checklist-add"
                        onClick={() => setItems([...items, newChecklistItem()])}
                    >
                        <Plus size={13} /> Add item
                    </button>
                </div>
                {savingIndicator('checklist')}
                {deleteButton}
            </div>
        )
    }

    if (block.type === 'counter') {
        const value = asNumber(draft.value)
        const step = Math.max(1, asNumber(draft.step, 1))
        const isRevision = draft.preset === 'revision' || /^revisions?$/i.test(draft.label || '')
        const Icon = isRevision ? RotateCcw : Hash
        return (
            <div className="task-block counter-block">
                <Icon size={15} aria-hidden="true" />
                <input
                    className="block-label-input"
                    value={draft.label || (isRevision ? 'Revision' : 'Counter')}
                    aria-label={`Counter label for ${taskTitle}`}
                    onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                    onBlur={() => persist({ label: draft.label || 'Counter' })}
                />
                <div className="counter-controls" role="group" aria-label={`${draft.label || 'Counter'} controls`}>
                    <button
                        type="button"
                        onClick={() => persist({ value: Math.max(0, value - step) })}
                        disabled={saving || value <= 0}
                        aria-label={`Decrease ${draft.label || 'counter'}`}
                    >−</button>
                    <output aria-live="polite" aria-atomic="true">{value}</output>
                    <button
                        type="button"
                        onClick={() => persist({ value: value + step })}
                        disabled={saving}
                        aria-label={`Increase ${draft.label || 'counter'}`}
                    >+</button>
                </div>
                {deleteButton}
            </div>
        )
    }

    if (block.type === 'bookmark') {
        const isRevisit = draft.preset === 'revisit' || /^revisit$/i.test(draft.label || '')
        if (isRevisit) {
            const bookmarked = draft.bookmarked !== false
            return (
                <div className={`task-block revisit-block ${bookmarked ? 'active' : ''}`}>
                    <Flag size={15} aria-hidden="true" />
                    <button
                        type="button"
                        className="revisit-toggle"
                        onClick={() => persist({ bookmarked: !bookmarked })}
                        aria-pressed={bookmarked}
                    >
                        {bookmarked ? 'Marked to revisit' : 'Revisit cleared'}
                    </button>
                    {deleteButton}
                </div>
            )
        }

        return (
            <div className="task-block bookmark-block">
                <Bookmark size={15} aria-hidden="true" />
                <div className="bookmark-fields">
                    <input
                        value={draft.label || ''}
                        placeholder="Bookmark label"
                        aria-label={`Bookmark label for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                        onBlur={() => persist({ label: draft.label || 'Bookmark' })}
                    />
                    <input
                        type="url"
                        value={draft.url || ''}
                        placeholder="https://…"
                        aria-label={`Bookmark URL for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))}
                        onBlur={() => persist({ url: draft.url || '' })}
                    />
                </div>
                <div className="block-inline-actions">
                    {isSafeUrl(draft.url) && (
                        <a
                            className="block-open-link icon-btn"
                            href={draft.url}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Open ${draft.label || 'bookmark'} in a new tab`}
                        >
                            <ExternalLink size={14} />
                        </a>
                    )}
                    {deleteButton}
                </div>
            </div>
        )
    }

    if (block.type === 'date') {
        return (
            <div className="task-block date-block">
                <CalendarDays size={15} aria-hidden="true" />
                <div className="compact-block-fields">
                    <input
                        className="block-label-input"
                        value={draft.label || ''}
                        placeholder="Due date"
                        aria-label={`Date label for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                        onBlur={() => persist({ label: draft.label || 'Due date' })}
                    />
                    <input
                        type="date"
                        value={draft.date || ''}
                        aria-label={`${draft.label || 'Due date'} for ${taskTitle}`}
                        onChange={(event) => persist({ date: event.target.value })}
                    />
                </div>
                {savingIndicator('due date')}
                {deleteButton}
            </div>
        )
    }

    if (block.type === 'label') {
        return (
            <div className="task-block label-block">
                <Tag size={15} aria-hidden="true" />
                <div className="compact-block-fields">
                    <input
                        className="block-label-input"
                        value={draft.label || ''}
                        placeholder="Label"
                        aria-label={`Label name for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                        onBlur={() => persist({ label: draft.label || 'Label' })}
                    />
                    <input
                        value={draft.value || ''}
                        placeholder="Add a value"
                        aria-label={`${draft.label || 'Label'} value for ${taskTitle}`}
                        onChange={(event) => setDraft((current) => ({ ...current, value: event.target.value }))}
                        onBlur={() => persist({ value: draft.value || '' })}
                    />
                </div>
                {savingIndicator('label')}
                {deleteButton}
            </div>
        )
    }

    if (block.type === 'code') {
        return (
            <div className="task-block code-block">
                <Code2 size={15} aria-hidden="true" />
                <div className="code-fields">
                    <div className="code-heading-fields">
                        <input
                            className="block-label-input"
                            value={draft.label || ''}
                            placeholder="Code"
                            aria-label={`Code block label for ${taskTitle}`}
                            onChange={(event) => setDraft((current) => ({ ...current, label: event.target.value }))}
                            onBlur={() => persist({ label: draft.label || 'Code' })}
                        />
                        <input
                            value={draft.language || ''}
                            placeholder="Language"
                            aria-label={`Code language for ${taskTitle}`}
                            onChange={(event) => setDraft((current) => ({ ...current, language: event.target.value }))}
                            onBlur={() => persist({ language: draft.language || '' })}
                        />
                    </div>
                    <textarea
                        value={draft.code || ''}
                        placeholder="Paste code or a command…"
                        aria-label={`${draft.label || 'Code'} content for ${taskTitle}`}
                        rows={Math.max(2, String(draft.code || '').split('\n').length)}
                        spellCheck="false"
                        onChange={(event) => setDraft((current) => ({ ...current, code: event.target.value }))}
                        onBlur={() => persist({ code: draft.code || '' })}
                    />
                </div>
                {savingIndicator('code')}
                {deleteButton}
            </div>
        )
    }

    return (
        <div className="task-block unknown-block">
            <span>{block.type}</span>
            <code>{JSON.stringify(draft)}</code>
            {deleteButton}
        </div>
    )
}

function SemanticBlockItem({ block, taskTitle, onChange, onDelete, onError }) {
    const [isEditing, setIsEditing] = useState(false)
    const { label, value } = getSemanticBlockDisplay(block)

    if (isEditing) {
        return (
            <div className="semantic-block-editor">
                <BlockItem block={block} taskTitle={taskTitle} onChange={onChange} onDelete={onDelete} onError={onError} />
                <button type="button" className="semantic-edit-done" onClick={() => setIsEditing(false)}>
                    <Check size={13} /> Done
                </button>
            </div>
        )
    }

    return (
        <div className="semantic-field-row">
            <span className="semantic-field-label">{label}</span>
            <span className="semantic-field-value">{value || 'No value'}</span>
            <button
                type="button"
                className="semantic-field-edit icon-btn"
                onClick={() => setIsEditing(true)}
                aria-label={`Edit ${label} for ${taskTitle}`}
            >
                <Edit2 size={13} />
            </button>
        </div>
    )
}

export default function TaskBlocks({
    task,
    sectionTasks = [],
    roadmapTasks = [],
    onBlocksChange,
    onBulkBlocksChange,
}) {
    const [isPickerOpen, setIsPickerOpen] = useState(false)
    const [scope, setScope] = useState('task')
    const [pendingOption, setPendingOption] = useState(null)
    const [feedback, setFeedback] = useState('')
    const [error, setError] = useState('')
    const [adding, setAdding] = useState(false)
    const pickerRef = useRef(null)
    const triggerRef = useRef(null)
    const confirmRef = useRef(null)
    const feedbackTimerRef = useRef(null)
    const blocks = Array.isArray(task.blocks) ? task.blocks : []
    const authHeaders = useMemo(() => ({ 'X-Local-User-Id': LOCAL_USER_ID }), [])
    const taskIds = useMemo(() => uniqueTaskIds([task]), [task])
    const sectionTaskIds = useMemo(() => uniqueTaskIds(sectionTasks.length ? sectionTasks : [task]), [sectionTasks, task])
    const roadmapTaskIds = useMemo(() => uniqueTaskIds(roadmapTasks.length ? roadmapTasks : [task]), [roadmapTasks, task])
    const scopeOptions = [
        { value: 'task', label: 'This task', taskIds },
        { value: 'section', label: 'This section', taskIds: sectionTaskIds },
        { value: 'roadmap', label: 'Entire roadmap', taskIds: roadmapTaskIds },
    ]
    const selectedScope = scopeOptions.find((option) => option.value === scope) || scopeOptions[0]
    const importedProperties = Object.entries(task.properties || {}).filter(([key, value]) => (
        !legacyPropertyPattern.test(key) && key.toLowerCase() !== 'roadmap' && value !== '' && value !== null && value !== undefined
    ))
    const semanticBlocks = blocks.filter(isImportedSemanticBlock)
    const editableBlocks = blocks.filter((block) => !isImportedSemanticBlock(block))
    const typeProperty = importedProperties.find(([key]) => key.toLowerCase() === 'type')
    const contextProperties = importedProperties.filter(([key]) => ['section', 'order'].includes(key.toLowerCase()))
    const highlightedProperties = importedProperties.filter(([key]) => (
        ['exit criterion', 'requires', 'unlocks'].includes(key.toLowerCase())
    ))
    const secondaryProperties = importedProperties.filter(([key]) => ![
        'type',
        'section',
        'order',
        'exit criterion',
        'requires',
        'unlocks',
    ].includes(key.toLowerCase()))

    useLayoutEffect(() => {
        if (!isPickerOpen) return
        if (pendingOption) confirmRef.current?.focus()
        else pickerRef.current?.querySelector('[data-block-option]')?.focus()
    }, [isPickerOpen, pendingOption])

    useEffect(() => {
        if (!isPickerOpen) return undefined

        const closeOnOutsideClick = (event) => {
            if (!pickerRef.current?.contains(event.target) && !triggerRef.current?.contains(event.target)) {
                setIsPickerOpen(false)
                setPendingOption(null)
            }
        }
        const closeOnEscape = (event) => {
            if (event.key !== 'Escape') return
            if (pendingOption) {
                setPendingOption(null)
                return
            }
            setIsPickerOpen(false)
            triggerRef.current?.focus()
        }

        document.addEventListener('pointerdown', closeOnOutsideClick)
        document.addEventListener('keydown', closeOnEscape)
        return () => {
            document.removeEventListener('pointerdown', closeOnOutsideClick)
            document.removeEventListener('keydown', closeOnEscape)
        }
    }, [isPickerOpen, pendingOption])

    useEffect(() => () => {
        if (feedbackTimerRef.current) window.clearTimeout(feedbackTimerRef.current)
    }, [])

    const announce = (message, isError = false) => {
        if (feedbackTimerRef.current) window.clearTimeout(feedbackTimerRef.current)
        if (isError) {
            setFeedback('')
            setError(message)
        } else {
            setError('')
            setFeedback(message)
        }
        feedbackTimerRef.current = window.setTimeout(() => {
            if (isError) setError('')
            else setFeedback('')
            feedbackTimerRef.current = null
        }, 5000)
    }

    const closePicker = () => {
        setIsPickerOpen(false)
        setPendingOption(null)
        setScope('task')
        triggerRef.current?.focus()
    }

    const addSingleBlock = async (option) => {
        setAdding(true)
        setError('')
        try {
            const response = await axios.post(
                `${API_URL}/tasks/${task.id}/blocks`,
                { type: option.type, data: option.data },
                { headers: authHeaders },
            )
            onBlocksChange((current) => {
                if (current.some((item) => item.id === response.data.id)) return current
                return [...current, response.data]
                    .sort((left, right) => (Number(left.position) || 0) - (Number(right.position) || 0))
            })
            closePicker()
            announce(`Added ${option.label} to this task.`)
        } catch (addError) {
            console.error('Failed to add task block', addError)
            announce('Could not add this block.', true)
        } finally {
            setAdding(false)
        }
    }

    const chooseBlock = (option) => {
        if (scope === 'task') addSingleBlock(option)
        else setPendingOption(option)
    }

    const addBulkBlocks = async () => {
        if (!pendingOption || selectedScope.taskIds.length === 0) return
        setAdding(true)
        setError('')
        try {
            const response = await axios.post(
                `${API_URL}/task-blocks/bulk`,
                {
                    task_ids: selectedScope.taskIds,
                    type: pendingOption.type,
                    data: pendingOption.data,
                },
                { headers: authHeaders },
            )
            const createdBlocks = returnedBlocks(response.data)
            if (createdBlocks.length !== selectedScope.taskIds.length) {
                throw new Error(`Expected ${selectedScope.taskIds.length} blocks but received ${createdBlocks.length}`)
            }
            onBulkBlocksChange?.(createdBlocks)
            const count = createdBlocks.length
            const label = pendingOption.label
            closePicker()
            announce(`Added ${label} to ${count} ${count === 1 ? 'task' : 'tasks'}.`)
        } catch (addError) {
            console.error('Failed to add task blocks in bulk', addError)
            announce(`Could not confirm the change for ${selectedScope.taskIds.length} tasks. Reload before trying again.`, true)
        } finally {
            setAdding(false)
        }
    }

    const updateBlock = async (block, data) => {
        onBlocksChange((current) => current.map((item) => (
            item.id === block.id ? { ...item, data } : item
        )))
        setError('')
        try {
            const response = await axios.patch(
                `${API_URL}/task-blocks/${block.id}`,
                { data },
                { headers: authHeaders },
            )
            onBlocksChange((current) => current.map((item) => (
                item.id === block.id && item.data === data ? response.data : item
            )))
            return response.data
        } catch (updateError) {
            console.error('Failed to update task block', updateError)
            const rolledBack = { ...block, data: { ...(block.data || {}) } }
            onBlocksChange((current) => current.map((item) => (
                item.id === block.id && item.data === data ? rolledBack : item
            )))
            announce('A block change could not be saved.', true)
            return rolledBack
        }
    }

    const deleteBlock = async (block) => {
        onBlocksChange((current) => current.filter((item) => item.id !== block.id))
        setError('')
        try {
            await axios.delete(`${API_URL}/task-blocks/${block.id}`, { headers: authHeaders })
        } catch (deleteError) {
            console.error('Failed to delete task block', deleteError)
            onBlocksChange((current) => {
                if (current.some((item) => item.id === block.id)) return current
                return [...current, block]
                    .sort((left, right) => (Number(left.position) || 0) - (Number(right.position) || 0))
            })
            announce('The block could not be removed.', true)
        }
    }

    const handlePickerKeys = (event) => {
        if (!event.target.hasAttribute('data-block-option')) return
        const items = [...pickerRef.current.querySelectorAll('[data-block-option]:not(:disabled)')]
        const currentIndex = items.indexOf(document.activeElement)
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            const offset = event.key === 'ArrowDown' ? 1 : -1
            items[(currentIndex + offset + items.length) % items.length]?.focus()
        }
        if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault()
            items[event.key === 'Home' ? 0 : items.length - 1]?.focus()
        }
    }

    const togglePicker = () => {
        setIsPickerOpen((current) => {
            if (!current) {
                setScope('task')
                setPendingOption(null)
                setError('')
            }
            return !current
        })
    }

    return (
        <div className="task-block-area" onClick={(event) => event.stopPropagation()}>
            {(typeProperty || contextProperties.length > 0) && (
                <div className="semantic-property-strip" role="group" aria-label="Task classification">
                    {typeProperty && <strong>{formatSemanticValue(typeProperty[1])}</strong>}
                    {contextProperties.map(([key, value]) => (
                        <span key={key}>{key}: {formatSemanticValue(value)}</span>
                    ))}
                </div>
            )}

            {highlightedProperties.length > 0 && (
                <div className="semantic-property-list">
                    {highlightedProperties.map(([key, value]) => (
                        <div className="semantic-field-row" key={key}>
                            <span className="semantic-field-label">{key}</span>
                            <span className="semantic-field-value">{formatSemanticValue(value)}</span>
                        </div>
                    ))}
                </div>
            )}

            {semanticBlocks.length > 0 && (
                <details className="semantic-details">
                    <summary>Details · {semanticBlocks.length}</summary>
                    <div className="semantic-field-list">
                        {semanticBlocks.map((block) => (
                            <SemanticBlockItem
                                key={block.id}
                                block={block}
                                taskTitle={task.title}
                                onChange={updateBlock}
                                onDelete={deleteBlock}
                                onError={(message) => announce(message, true)}
                            />
                        ))}
                    </div>
                </details>
            )}

            {editableBlocks.length > 0 && (
                <div className="task-block-list">
                    {editableBlocks.map((block) => (
                        <BlockItem
                            key={block.id}
                            block={block}
                            taskTitle={task.title}
                            onChange={updateBlock}
                            onDelete={deleteBlock}
                            onError={(message) => announce(message, true)}
                        />
                    ))}
                </div>
            )}

            {secondaryProperties.length > 0 && (
                <details className="imported-properties">
                    <summary>More fields · {secondaryProperties.length}</summary>
                    <dl>
                        {secondaryProperties.map(([key, value]) => (
                            <div key={key}><dt>{key}</dt><dd>{formatSemanticValue(value)}</dd></div>
                        ))}
                    </dl>
                </details>
            )}

            <div className="block-inserter">
                <button
                    ref={triggerRef}
                    type="button"
                    className="add-block-button"
                    onClick={togglePicker}
                    aria-expanded={isPickerOpen}
                    aria-haspopup="dialog"
                    aria-label={`Add a block to ${task.title}`}
                >
                    <Plus size={15} /> <span>Add</span>
                </button>

                {isPickerOpen && (
                    <div
                        ref={pickerRef}
                        className="block-picker"
                        role="dialog"
                        aria-modal="false"
                        aria-labelledby={`block-picker-title-${task.id}`}
                        onKeyDown={handlePickerKeys}
                    >
                        <h3 className="sr-only" id={`block-picker-title-${task.id}`}>Add blocks to {task.title}</h3>
                        {!pendingOption ? (
                            <>
                                <fieldset className="block-scope-selector">
                                    <legend>Apply to</legend>
                                    {scopeOptions.map((option) => (
                                        <label key={option.value}>
                                            <input
                                                type="radio"
                                                name={`block-scope-${task.id}`}
                                                value={option.value}
                                                checked={scope === option.value}
                                                onChange={() => setScope(option.value)}
                                            />
                                            <span>{option.label}</span>
                                            <small>{option.taskIds.length} {option.taskIds.length === 1 ? 'task' : 'tasks'}</small>
                                        </label>
                                    ))}
                                </fieldset>
                                <div className="block-picker-heading">Choose a block</div>
                                <div className="block-option-list">
                                    {BLOCK_OPTIONS.map((option) => (
                                        <button
                                            type="button"
                                            data-block-option
                                            key={option.key}
                                            onClick={() => chooseBlock(option)}
                                            disabled={adding}
                                        >
                                            <span className="block-option-icon"><option.icon size={16} /></span>
                                            <span><strong>{option.label}</strong><small>{option.description}</small></span>
                                        </button>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="block-picker-confirmation" role="group" aria-labelledby={`bulk-confirm-${task.id}`}>
                                <span className="block-confirm-eyebrow">Confirm bulk add</span>
                                <h4 id={`bulk-confirm-${task.id}`}>Add {pendingOption.label} to {selectedScope.label.toLowerCase()}?</h4>
                                <p>
                                    This creates one {pendingOption.label.toLowerCase()} on each of{' '}
                                    <strong>{selectedScope.taskIds.length} {selectedScope.taskIds.length === 1 ? 'task' : 'tasks'}</strong>.
                                    You can edit or remove each one separately afterward.
                                </p>
                                {error && <p className="block-confirm-error" role="alert">{error}</p>}
                                <div className="block-confirm-actions">
                                    <button
                                        type="button"
                                        className="btn-secondary btn-small"
                                        onClick={() => setPendingOption(null)}
                                        disabled={adding}
                                    >
                                        Back
                                    </button>
                                    <button
                                        ref={confirmRef}
                                        type="button"
                                        className="btn-primary btn-small"
                                        onClick={addBulkBlocks}
                                        disabled={adding}
                                    >
                                        {adding
                                            ? 'Adding…'
                                            : `Add to ${selectedScope.taskIds.length} ${selectedScope.taskIds.length === 1 ? 'task' : 'tasks'}`}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            <span
                className={`task-block-feedback ${error ? 'error' : ''}`}
                role={error ? 'alert' : 'status'}
                aria-live={error ? 'assertive' : 'polite'}
            >
                {feedback || (!pendingOption ? error : '')}
            </span>
        </div>
    )
}
