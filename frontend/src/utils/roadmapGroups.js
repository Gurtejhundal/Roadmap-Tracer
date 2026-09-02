import { getTaskRoadmap } from './taskSemantics.js'

function timeframeId(value) {
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function roadmapGroupKey(task) {
    const roadmap = getTaskRoadmap(task)
    const label = String(task?.timeframe_label || 'Unassigned').trim() || 'Unassigned'
    const id = timeframeId(task?.timeframe_id)
    return id !== null
        ? JSON.stringify(['timeframe', id, roadmap])
        : JSON.stringify(['label', label, roadmap])
}

export function groupRoadmapTasks(tasks) {
    return (Array.isArray(tasks) ? tasks : []).reduce((result, task) => {
        const key = roadmapGroupKey(task)
        if (!result.tasks[key]) {
            result.tasks[key] = []
            result.meta[key] = {
                key,
                timeframe: String(task?.timeframe_label || 'Unassigned').trim() || 'Unassigned',
                timeframeId: timeframeId(task?.timeframe_id),
                roadmap: getTaskRoadmap(task),
            }
        }
        result.tasks[key].push(task)
        return result
    }, { tasks: Object.create(null), meta: Object.create(null) })
}

export function roadmapGroupDisplayLabel(group, groupMeta = {}) {
    return groupMeta[group]?.timeframe || group
}

export function taskCreatePayload(roadmapId, title, groupMeta = {}) {
    const payload = {
        roadmap_id: Number(roadmapId),
        timeframe_label: String(groupMeta.timeframe || 'Unassigned'),
        title,
    }
    const id = timeframeId(groupMeta.timeframeId)
    if (id !== null) payload.timeframe_id = id
    return payload
}
