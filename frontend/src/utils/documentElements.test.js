import assert from 'node:assert/strict'
import test from 'node:test'

import { formatDocumentValue, normalizeDocumentElements } from './documentElements.js'

test('normalizes malformed legacy document values into render-safe primitives', () => {
    const elements = normalizeDocumentElements([
        { type: 'heading', text: { label: 'Safe heading' }, level: { invalid: true } },
        { type: 'callout', title: { kind: 'Warning' }, text: { message: 'Read this' } },
        { type: 'paragraph', text: ['First', { second: 2 }] },
        { type: 'list', items: { invalid: 'not an array' } },
        { type: 'table', headers: { invalid: true }, rows: 'not an array' },
        {
            type: 'table',
            headers: ['Name', { label: 'Status' }],
            rows: [[{ value: 'Docker' }, true], { note: 'single cell' }],
        },
        null,
    ])

    assert.deepEqual(elements, [
        { type: 'heading', text: 'label: Safe heading', level: 3 },
        { type: 'callout', title: 'kind: Warning', text: 'message: Read this' },
        { type: 'paragraph', text: 'First, second: 2' },
        {
            type: 'table',
            columns: ['Name', 'label: Status'],
            rows: [['value: Docker', 'true'], ['note: single cell']],
        },
    ])
})

test('returns safe output for cyclic and unsupported values', () => {
    const cyclic = { label: 'Kept' }
    cyclic.self = cyclic

    assert.equal(formatDocumentValue(cyclic), 'label: Kept')
    assert.deepEqual(normalizeDocumentElements({ elements: [] }), [])
})
