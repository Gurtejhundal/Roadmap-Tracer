import assert from 'node:assert/strict'
import test from 'node:test'

import { mergeEditableRoadmap, prepareEditableRoadmap } from './editableRoadmap.js'

const roadmap = {
    tasks: [
        {
            title: 'Alpha task',
            timeframe: 'Phase 1',
            is_done: false,
            properties: { Priority: 'High' },
            blocks: [{ id: 1, type: 'note', data: { text: 'Keep me' } }],
            granularity: 'section',
            start_date: '2026-08-01',
            end_date: '2026-08-02',
        },
        {
            title: 'Delete task',
            timeframe: 'Phase 1',
            is_done: false,
            properties: {},
            blocks: [],
            granularity: 'section',
            start_date: '2026-08-01',
            end_date: '2026-08-02',
        },
        {
            title: 'Gamma task',
            timeframe: 'Phase 2',
            is_done: false,
            properties: {},
            blocks: [{ id: 2, type: 'counter', data: { value: 3 } }],
            granularity: 'week',
            start_date: '2026-09-01',
            end_date: '2026-09-30',
        },
    ],
}

test('task moves preserve task metadata but use the destination section schedule', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    const phase2Heading = 'Phase 2 <!-- traqo-section:section-2 -->:\n'
    const edited = prepared.text
        .replace('- Alpha task <!-- traqo-task:task-1 -->\n', '')
        .replace(/- Delete task <!-- traqo-task:task-2 -->\n?/, '')
        .replace(
            phase2Heading,
            `${phase2Heading}- Renamed alpha task <!-- traqo-task:task-1 -->\n- Brand new task\n`,
        )

    const tasks = mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections)
    const renamed = tasks.find((task) => task.title === 'Renamed alpha task')
    const added = tasks.find((task) => task.title === 'Brand new task')
    const gamma = tasks.find((task) => task.title === 'Gamma task')

    assert.equal(tasks.length, 3)
    assert.equal(Object.hasOwn(prepared.savedTasks[0], 'start_date'), false)
    assert.deepEqual(renamed.properties, { Priority: 'High' })
    assert.equal(renamed.blocks[0].data.text, 'Keep me')
    assert.equal(renamed.timeframe, 'Phase 2')
    assert.equal(renamed.granularity, 'week')
    assert.equal(renamed.start_date, '2026-09-01')
    assert.equal(renamed.end_date, '2026-09-30')
    assert.equal(added.start_date, '2026-09-01')
    assert.equal(gamma.start_date, '2026-09-01')
    assert.deepEqual(added.properties, {})
    assert.deepEqual(added.blocks, [])
    assert.equal(tasks.some((task) => task.title === 'Delete task'), false)
})

test('section rename preserves schedule through its own stable marker', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    const edited = prepared.text.replace(
        'Phase 1 <!-- traqo-section:section-1 -->:',
        'Foundation <!-- traqo-section:section-1 -->:',
    )
    const tasks = mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections)
    const renamedSectionTasks = tasks.filter((task) => task.timeframe === 'Foundation')

    assert.equal(renamedSectionTasks.length, 2)
    renamedSectionTasks.forEach((task) => {
        assert.equal(task.granularity, 'section')
        assert.equal(task.start_date, '2026-08-01')
        assert.equal(task.end_date, '2026-08-02')
    })
})

test('editor section markers keep semantic-looking labels as independent sections', () => {
    const prepared = prepareEditableRoadmap({
        tasks: [
            { title: 'Learn', timeframe: 'Day 1', granularity: 'day' },
            { title: 'Review', timeframe: 'Revision Notes', granularity: 'section' },
            { title: 'Query task', timeframe: 'SELECT queries', granularity: 'section' },
            { title: 'Percent task', timeframe: '100%', granularity: 'section' },
        ],
    })
    const tasks = mergeEditableRoadmap(prepared.text, prepared.savedTasks, prepared.savedSections)

    assert.deepEqual(
        tasks.map((task) => task.timeframe),
        ['Day 1', 'Revision Notes', 'SELECT queries', '100%'],
    )
    assert.deepEqual(tasks.map((task) => task.granularity), ['day', 'section', 'section', 'section'])
})

test('no-op edit preserves duplicate label occurrences by timeframe id', () => {
    const prepared = prepareEditableRoadmap({
        tasks: [
            {
                title: 'First medium task',
                timeframe: 'Medium',
                timeframe_id: 101,
                granularity: 'section',
                start_date: '2026-01-01',
            },
            {
                title: 'Intervening hard task',
                timeframe: 'Hard',
                timeframe_id: 202,
                granularity: 'section',
            },
            {
                title: 'Second medium task',
                timeframe: 'Medium',
                timeframe_id: 303,
                granularity: 'section',
                start_date: '2026-03-01',
            },
        ],
    })
    const tasks = mergeEditableRoadmap(prepared.text, prepared.savedTasks, prepared.savedSections)

    assert.equal(prepared.savedSections.length, 3)
    assert.equal((prepared.text.match(/^Medium /gm) || []).length, 2)
    assert.deepEqual(tasks.map((task) => task.title), [
        'First medium task',
        'Intervening hard task',
        'Second medium task',
    ])
    assert.deepEqual(tasks.map((task) => task.timeframe_id), [101, 202, 303])
    assert.deepEqual(tasks.map((task) => task.start_date), ['2026-01-01', undefined, '2026-03-01'])
})

test('duplicate section labels reject ambiguous marker fallback', () => {
    const prepared = prepareEditableRoadmap({
        tasks: [
            { title: 'First', timeframe: 'Medium', timeframe_id: 11 },
            { title: 'Second', timeframe: 'Medium', timeframe_id: 22 },
        ],
    })
    const edited = prepared.text.replace('<!-- traqo-section:section-1 -->', '')

    assert.throws(
        () => mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections),
        /appears more than once.*Restore its Traqo section marker/s,
    )
})

test('legacy exports preserve noncontiguous duplicate label occurrences', () => {
    const prepared = prepareEditableRoadmap({
        tasks: [
            { title: 'First medium', timeframe: 'Medium' },
            { title: 'Hard task', timeframe: 'Hard' },
            { title: 'Second medium', timeframe: 'Medium' },
        ],
    })
    const tasks = mergeEditableRoadmap(prepared.text, prepared.savedTasks, prepared.savedSections)

    assert.equal(prepared.savedSections.length, 3)
    assert.equal((prepared.text.match(/^Medium /gm) || []).length, 2)
    assert.deepEqual(tasks.map((task) => task.title), ['First medium', 'Hard task', 'Second medium'])
})

test('completion edits are retained while task and section metadata stay attached', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    const edited = prepared.text.replace(
        '- Alpha task <!-- traqo-task:task-1 -->',
        '[x] Alpha task <!-- traqo-task:task-1 -->',
    )
    const tasks = mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections)

    assert.equal(tasks[0].is_done, true)
    assert.equal(tasks[0].blocks[0].data.text, 'Keep me')
    assert.equal(tasks[0].start_date, '2026-08-01')
})

test('ambiguous task marker removal blocks the save before payload creation', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    const edited = prepared.text
        .replace('- Alpha task <!-- traqo-task:task-1 -->', '- Renamed without marker')
        .replace(
            'Phase 2 <!-- traqo-section:section-2 -->:\n',
            'Phase 2 <!-- traqo-section:section-2 -->:\n- Another new task\n',
        )

    assert.throws(
        () => mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections),
        /Traqo stopped this save because task markers were removed/,
    )
})

test('ambiguous section marker removal blocks schedule reassignment', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    const edited = prepared.text.replace(
        'Phase 1 <!-- traqo-section:section-1 -->:',
        'Renamed without a section marker:',
    )

    assert.throws(
        () => mergeEditableRoadmap(edited, prepared.savedTasks, prepared.savedSections),
        /Traqo stopped this save because section markers were removed/,
    )
})

test('duplicate or unknown task markers are rejected', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    assert.throws(
        () => mergeEditableRoadmap(
            `${prepared.text}\n- Duplicate <!-- traqo-task:task-1 -->`,
            prepared.savedTasks,
            prepared.savedSections,
        ),
        /duplicated/,
    )
    assert.throws(
        () => mergeEditableRoadmap(
            `${prepared.text}\n- Unknown <!-- traqo-task:task-999 -->`,
            prepared.savedTasks,
            prepared.savedSections,
        ),
        /unknown Traqo marker/,
    )
})

test('unknown or conflicting section markers are rejected', () => {
    const prepared = prepareEditableRoadmap(roadmap)
    assert.throws(
        () => mergeEditableRoadmap(
            prepared.text.replace('traqo-section:section-1', 'traqo-section:section-999'),
            prepared.savedTasks,
            prepared.savedSections,
        ),
        /unknown Traqo section marker/,
    )
    assert.throws(
        () => mergeEditableRoadmap(
            prepared.text.replace('traqo-section:section-2', 'traqo-section:section-1'),
            prepared.savedTasks,
            prepared.savedSections,
        ),
        /attached to multiple section names/,
    )
})
