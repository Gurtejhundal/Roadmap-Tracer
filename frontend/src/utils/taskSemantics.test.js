import assert from 'node:assert/strict'
import test from 'node:test'

import { getSemanticBlockDisplay } from './taskSemantics.js'

test('normalizes malformed imported block labels and values before React rendering', () => {
    assert.deepEqual(
        getSemanticBlockDisplay({
            type: 'note',
            data: {
                source: 'import',
                label: { kind: 'Prerequisite', order: 2 },
                text: { topic: 'Docker', steps: ['Install', 'Run'] },
            },
        }),
        {
            label: 'kind: Prerequisite; order: 2',
            value: 'topic: Docker; steps: Install, Run',
        },
    )
})

test('uses a safe label fallback for missing or unusable block data', () => {
    assert.deepEqual(getSemanticBlockDisplay({ data: null }), { label: 'Detail', value: '' })
    assert.deepEqual(getSemanticBlockDisplay({ data: { label: {} } }), { label: 'Detail', value: '' })
})
