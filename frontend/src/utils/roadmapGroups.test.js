import assert from 'node:assert/strict'
import test from 'node:test'

import {
    groupRoadmapTasks,
    roadmapGroupDisplayLabel,
    taskCreatePayload,
} from './roadmapGroups.js'

test('keeps duplicate timeframe labels separated by occurrence id', () => {
    const grouped = groupRoadmapTasks([
        { id: 1, timeframe_id: 10, timeframe_label: 'Medium', properties: {} },
        { id: 2, timeframe_id: 20, timeframe_label: 'Hard', properties: {} },
        { id: 3, timeframe_id: 30, timeframe_label: 'Medium', properties: {} },
        { id: 4, timeframe_id: 10, timeframe_label: 'Medium', properties: {} },
    ])
    const keys = Object.keys(grouped.tasks)

    assert.equal(keys.length, 3)
    assert.deepEqual(grouped.tasks[keys[0]].map((task) => task.id), [1, 4])
    assert.deepEqual(grouped.tasks[keys[1]].map((task) => task.id), [2])
    assert.deepEqual(grouped.tasks[keys[2]].map((task) => task.id), [3])
    assert.equal(grouped.meta[keys[0]].timeframeId, 10)
    assert.equal(grouped.meta[keys[2]].timeframeId, 30)
})

test('selected group scopes bulk tasks and new-task payload to the same timeframe id', () => {
    const grouped = groupRoadmapTasks([
        { id: 11, timeframe_id: 41, timeframe_label: 'Medium', properties: {} },
        { id: 12, timeframe_id: 42, timeframe_label: 'Medium', properties: {} },
        { id: 13, timeframe_id: 42, timeframe_label: 'Medium', properties: {} },
    ])
    const selectedKey = Object.keys(grouped.tasks).find((key) => grouped.meta[key].timeframeId === 42)

    assert.deepEqual(grouped.tasks[selectedKey].map((task) => task.id), [12, 13])
    assert.deepEqual(taskCreatePayload(9, 'New task', grouped.meta[selectedKey]), {
        roadmap_id: 9,
        timeframe_label: 'Medium',
        title: 'New task',
        timeframe_id: 42,
    })
})

test('retains label fallback for tasks from older API responses', () => {
    const grouped = groupRoadmapTasks([
        { id: 1, timeframe_label: 'General', properties: {} },
        { id: 2, timeframe_label: 'General', properties: {} },
    ])
    const key = Object.keys(grouped.tasks)[0]

    assert.deepEqual(grouped.tasks[key].map((task) => task.id), [1, 2])
    assert.deepEqual(taskCreatePayload(3, 'Fallback task', grouped.meta[key]), {
        roadmap_id: 3,
        timeframe_label: 'General',
        title: 'Fallback task',
    })
})

test('resolves a timeline child display label instead of exposing its opaque group key', () => {
    const grouped = groupRoadmapTasks([
        { id: 1, timeframe_id: 70, timeframe_label: 'Phase 1', properties: {} },
        { id: 2, timeframe_id: 71, timeframe_label: 'Node A - Networking Basics', properties: {} },
    ])
    const childKey = Object.keys(grouped.tasks)[1]

    assert.notEqual(childKey, 'Node A - Networking Basics')
    assert.equal(
        roadmapGroupDisplayLabel(childKey, grouped.meta),
        'Node A - Networking Basics',
    )
})
