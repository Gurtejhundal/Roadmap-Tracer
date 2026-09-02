import assert from 'node:assert/strict'
import test from 'node:test'

import { getApiErrorMessage } from './apiErrors.js'

test('normalizes FastAPI validation arrays into render-safe text', () => {
    const error = {
        response: {
            data: {
                detail: [{
                    loc: ['body', 'name'],
                    msg: 'String should have at most 200 characters',
                    type: 'string_too_long',
                }],
            },
        },
    }

    assert.equal(
        getApiErrorMessage(error, 'fallback'),
        'name: String should have at most 200 characters',
    )
})

test('normalizes string and nested object API errors without returning objects', () => {
    assert.equal(
        getApiErrorMessage({ response: { data: { detail: 'Already exists.' } } }),
        'Already exists.',
    )
    assert.equal(
        getApiErrorMessage({ response: { data: { detail: { message: 'Invalid document.' } } } }),
        'Invalid document.',
    )
    assert.equal(
        getApiErrorMessage({ response: { data: { detail: { unexpected: true } } } }, 'Safe fallback'),
        'Safe fallback',
    )
})
