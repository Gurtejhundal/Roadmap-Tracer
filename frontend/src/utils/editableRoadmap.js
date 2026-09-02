import { parseRoadmapText } from './roadmapParser.js'
import { MAX_TASK_TITLE_LENGTH, MAX_TIMEFRAME_LABEL_LENGTH } from './roadmapLimits.js'

const TASK_MARKER_PATTERN = /\s*<!--\s*traqo-task:([a-z0-9-]+)\s*-->\s*/gi
const SECTION_MARKER_PATTERN = /\s*<!--\s*traqo-section:([a-z0-9-]+)\s*-->\s*/gi
const SECTION_METADATA_KEYS = ['granularity', 'start_date', 'end_date']

function taskMarker(editorId) {
    return `<!-- traqo-task:${editorId} -->`
}

function sectionMarker(editorId) {
    return `<!-- traqo-section:${editorId} -->`
}

function taskHasMetadata(task) {
    return Object.keys(task?.properties || {}).length > 0 || (task?.blocks || []).length > 0
}

function sectionHasMetadata(section) {
    return (
        (section?.timeframeId !== null && section?.timeframeId !== undefined)
        || SECTION_METADATA_KEYS.some((key) => (
            section?.[key] !== undefined && section?.[key] !== null && section?.[key] !== ''
        ))
    )
}

function normalizedTimeframeId(value) {
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function taskKey(sectionEditorId, timeframe, title) {
    const sectionIdentity = sectionEditorId || `label:${String(timeframe || 'General').trim()}`
    return `${sectionIdentity}\u0000${String(title || '').trim()}`
}

function parseEditableTasks(text) {
    return parseRoadmapText(text).map((task) => {
        const taskMarkerIds = []
        const sectionMarkerIds = []
        const title = String(task.title || '').replace(TASK_MARKER_PATTERN, (_, editorId) => {
            taskMarkerIds.push(editorId.toLowerCase())
            return ' '
        }).replace(/\s+/g, ' ').trim()
        const timeframe = String(task.timeframe || '').replace(SECTION_MARKER_PATTERN, (_, editorId) => {
            sectionMarkerIds.push(editorId.toLowerCase())
            return ' '
        }).replace(/\s+/g, ' ').trim()

        if (taskMarkerIds.length > 1) {
            throw new Error(`A task line contains more than one Traqo task marker: "${title || task.title}".`)
        }
        if (sectionMarkerIds.length > 1) {
            throw new Error(`Section "${timeframe || task.timeframe}" contains more than one Traqo section marker.`)
        }
        if (!title) throw new Error('A task title cannot contain only a Traqo marker.')
        if (!timeframe) throw new Error('A section label cannot contain only a Traqo marker.')
        if (title.length > MAX_TASK_TITLE_LENGTH) {
            throw new Error(`Task "${title.slice(0, 80)}…" exceeds the ${MAX_TASK_TITLE_LENGTH}-character title limit.`)
        }
        if (timeframe.length > MAX_TIMEFRAME_LABEL_LENGTH) {
            throw new Error(`Section "${timeframe.slice(0, 80)}…" exceeds the ${MAX_TIMEFRAME_LABEL_LENGTH}-character limit.`)
        }

        return {
            ...task,
            title,
            timeframe,
            editorId: taskMarkerIds[0] || '',
            sectionEditorId: sectionMarkerIds[0] || '',
        }
    })
}

function metadataForTask(task, savedTask, savedSection) {
    const merged = {
        ...task,
        is_done: Boolean(task.is_done),
        properties: savedTask?.properties || {},
        blocks: savedTask?.blocks || [],
    }

    SECTION_METADATA_KEYS.forEach((key) => {
        if (savedSection?.[key] !== undefined) merged[key] = savedSection[key]
    })
    if (savedSection?.timeframeId !== null && savedSection?.timeframeId !== undefined) {
        merged.timeframe_id = savedSection.timeframeId
    }
    delete merged.editorId
    delete merged.sectionEditorId
    return merged
}

function resolveSavedSections(parsedTasks, savedSections) {
    const savedById = new Map(savedSections.map((section) => [section.editorId, section]))
    const savedByLabel = new Map()
    savedSections.forEach((section) => {
        if (!savedByLabel.has(section.label)) savedByLabel.set(section.label, [])
        savedByLabel.get(section.label).push(section)
    })
    const resultingLabelById = new Map()
    const usedSavedIds = new Set()
    const matches = new Array(parsedTasks.length).fill(null)

    const associate = (task, saved) => {
        if (resultingLabelById.has(saved.editorId) && resultingLabelById.get(saved.editorId) !== task.timeframe) {
            throw new Error(
                `The Traqo section marker for "${saved.label}" is attached to multiple section names. `
                + 'Keep one section marker with one resulting section.'
            )
        }
        resultingLabelById.set(saved.editorId, task.timeframe)
        usedSavedIds.add(saved.editorId)
        return saved
    }

    parsedTasks.forEach((task, index) => {
        if (task.sectionEditorId) {
            const saved = savedById.get(task.sectionEditorId)
            if (!saved) {
                throw new Error(
                    `Section "${task.timeframe}" has an unknown Traqo section marker. `
                    + 'Restore the original marker or reload the editor.'
                )
            }
            matches[index] = associate(task, saved)
            return
        }

        const candidates = savedByLabel.get(task.timeframe) || []
        if (candidates.length > 1) {
            throw new Error(
                `Section label "${task.timeframe}" appears more than once in this roadmap. `
                + 'Restore its Traqo section marker so the correct occurrence can be identified.'
            )
        }
        if (candidates[0]) matches[index] = associate(task, candidates[0])
    })

    const unmatchedNewSectionLabels = new Set(
        parsedTasks.filter((_, index) => !matches[index]).map((task) => task.timeframe),
    )
    const unmatchedMetadataSections = savedSections.filter((section) => (
        !usedSavedIds.has(section.editorId) && sectionHasMetadata(section)
    ))

    if (unmatchedNewSectionLabels.size > 0 && unmatchedMetadataSections.length > 0) {
        throw new Error(
            'Traqo stopped this save because section markers were removed while sections were also renamed, added, or deleted. '
            + 'No changes were sent. Restore the markers, or reload and keep each <!-- traqo-section:... --> marker attached to its section heading. '
            + 'For an intentional scheduled-section deletion, save that deletion before adding new unmarked sections.'
        )
    }

    return matches
}

export function prepareEditableRoadmap(roadmapData) {
    const sourceTasks = Array.isArray(roadmapData?.tasks) ? roadmapData.tasks : []
    const savedTasks = []
    const savedSections = []
    const groups = []
    const groupsByTimeframeId = new Map()
    let previousFallbackGroup = null

    sourceTasks.forEach((task, index) => {
        const timeframe = task.timeframe || 'General'
        const timeframeId = normalizedTimeframeId(task.timeframe_id)
        let group = timeframeId === null ? null : groupsByTimeframeId.get(timeframeId)
        if (
            !group
            && timeframeId === null
            && previousFallbackGroup?.section.label === timeframe
        ) {
            group = previousFallbackGroup
        }
        if (!group) {
            const section = {
                editorId: `section-${savedSections.length + 1}`,
                label: timeframe,
                timeframeId,
            }
            SECTION_METADATA_KEYS.forEach((key) => {
                if (task[key] !== undefined) section[key] = task[key]
            })
            savedSections.push(section)
            group = { section, tasks: [] }
            groups.push(group)
            if (timeframeId !== null) groupsByTimeframeId.set(timeframeId, group)
        } else {
            SECTION_METADATA_KEYS.forEach((key) => {
                if (group.section[key] === undefined && task[key] !== undefined) {
                    group.section[key] = task[key]
                }
            })
        }

        const savedTask = {
            editorId: `task-${index + 1}`,
            sectionEditorId: group.section.editorId,
            timeframe,
            title: task.title || '',
            properties: task.properties || {},
            blocks: Array.isArray(task.blocks) ? task.blocks : [],
        }
        savedTasks.push(savedTask)
        group.tasks.push({ ...task, editorId: savedTask.editorId })
        previousFallbackGroup = timeframeId === null ? group : null
    })

    const text = groups.map(({ section, tasks }) => {
        const lines = [`${section.label} ${sectionMarker(section.editorId)}:`]
        tasks.forEach((task) => {
            lines.push(`${task.is_done ? '[x]' : '-'} ${task.title} ${taskMarker(task.editorId)}`)
        })
        return lines.join('\n')
    }).join('\n\n')

    return { text, savedTasks, savedSections }
}

export function mergeEditableRoadmap(text, savedTasks = [], savedSections = []) {
    const parsedTasks = parseEditableTasks(text)
    const sectionMatches = resolveSavedSections(parsedTasks, savedSections)
    const savedById = new Map(savedTasks.map((task) => [task.editorId, task]))
    const usedSavedIds = new Set()
    const matches = new Array(parsedTasks.length).fill(null)

    parsedTasks.forEach((task, index) => {
        if (!task.editorId) return
        const saved = savedById.get(task.editorId)
        if (!saved) {
            throw new Error(`Task "${task.title}" has an unknown Traqo marker. Restore the original marker or reload the editor.`)
        }
        if (usedSavedIds.has(task.editorId)) {
            throw new Error(`The Traqo marker on "${task.title}" is duplicated. Every existing task marker must remain unique.`)
        }
        usedSavedIds.add(task.editorId)
        matches[index] = saved
    })

    const exactMatches = new Map()
    savedTasks.forEach((saved) => {
        if (usedSavedIds.has(saved.editorId)) return
        const key = taskKey(saved.sectionEditorId, saved.timeframe, saved.title)
        if (!exactMatches.has(key)) exactMatches.set(key, [])
        exactMatches.get(key).push(saved)
    })

    parsedTasks.forEach((task, index) => {
        if (matches[index] || task.editorId) return
        const saved = exactMatches.get(taskKey(
            sectionMatches[index]?.editorId,
            task.timeframe,
            task.title,
        ))?.shift()
        if (!saved) return
        usedSavedIds.add(saved.editorId)
        matches[index] = saved
    })

    const unmatchedNewTasks = parsedTasks.filter((_, index) => !matches[index])
    const unmatchedMetadataTasks = savedTasks.filter((saved) => (
        !usedSavedIds.has(saved.editorId) && taskHasMetadata(saved)
    ))
    if (unmatchedNewTasks.length > 0 && unmatchedMetadataTasks.length > 0) {
        throw new Error(
            'Traqo stopped this save because task markers were removed while tasks were also renamed, added, or deleted. '
            + 'No changes were sent. Restore the markers, or reload and keep each <!-- traqo-task:... --> marker attached to its task. '
            + 'For an intentional metadata-task deletion, save that deletion before adding new unmarked tasks.'
        )
    }

    return parsedTasks.map((task, index) => (
        metadataForTask(task, matches[index], sectionMatches[index])
    ))
}
