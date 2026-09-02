import { useMemo, useState } from 'react'
import { Braces, ChevronDown, FileText, List, MessageSquare, Table2, Text } from 'lucide-react'
import { normalizeDocumentElements } from '../utils/documentElements'

const TYPE_ICONS = {
    heading: Text,
    paragraph: FileText,
    list: List,
    callout: MessageSquare,
    code: Braces,
    table: Table2,
}
const TABLE_PREVIEW_ROWS = 100

function ElementIcon({ type }) {
    const Icon = TYPE_ICONS[type] || FileText
    return <Icon size={14} aria-hidden="true" />
}

function SourceTable({ columns, rows, index }) {
    const [showAllRows, setShowAllRows] = useState(false)
    const visibleRows = showAllRows ? rows : rows.slice(0, TABLE_PREVIEW_ROWS)
    const hiddenRowCount = rows.length - visibleRows.length

    return (
        <>
            <div className="source-table-scroll">
                <table>
                    {columns.length > 0 && (
                        <thead><tr>{columns.map((column, columnIndex) => <th key={`${index}-h-${columnIndex}`}>{column}</th>)}</tr></thead>
                    )}
                    <tbody>
                        {visibleRows.map((row, rowIndex) => (
                            <tr key={`${index}-r-${rowIndex}`}>
                                {(Array.isArray(row) ? row : [row]).map((cell, cellIndex) => (
                                    <td key={`${index}-${rowIndex}-${cellIndex}`}>{cell == null ? '' : String(cell)}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {hiddenRowCount > 0 && (
                <button type="button" className="btn-quiet" onClick={() => setShowAllRows(true)}>
                    Show {hiddenRowCount} more rows
                </button>
            )}
        </>
    )
}

function DocumentElement({ element, index }) {
    const type = element?.type || 'paragraph'

    if (type === 'heading') {
        const level = Math.min(6, Math.max(3, Number(element.level || 3) + 2))
        const Heading = `h${level}`
        return (
            <div className="source-block source-heading">
                <ElementIcon type={type} />
                <Heading>{element.text}</Heading>
            </div>
        )
    }

    if (type === 'list') {
        return (
            <div className="source-block source-list">
                <ElementIcon type={type} />
                <ul>{(element.items || []).map((item, itemIndex) => <li key={`${index}-${itemIndex}`}>{item}</li>)}</ul>
            </div>
        )
    }

    if (type === 'callout') {
        return (
            <aside className="source-block source-callout">
                <ElementIcon type={type} />
                <div>
                    {element.title && <strong>{element.title}</strong>}
                    {element.text && <p>{element.text}</p>}
                </div>
            </aside>
        )
    }

    if (type === 'code') {
        return (
            <div className="source-block source-code">
                <ElementIcon type={type} />
                <pre><code>{element.text}</code></pre>
            </div>
        )
    }

    if (type === 'table') {
        const columns = Array.isArray(element.columns) ? element.columns : []
        const rows = Array.isArray(element.rows) ? element.rows : []
        return (
            <div className="source-block source-table">
                <ElementIcon type={type} />
                <SourceTable columns={columns} rows={rows} index={index} />
            </div>
        )
    }

    return (
        <div className="source-block source-paragraph">
            <ElementIcon type={type} />
            <p>{element.text || ''}</p>
        </div>
    )
}

function DocumentSection({ section, sectionIndex }) {
    const [isOpen, setIsOpen] = useState(false)

    return (
        <details
            className="source-document-section"
            onToggle={(event) => setIsOpen(event.currentTarget.open)}
        >
            <summary>
                <strong>{section.title}</strong>
                <small>{section.elements.length} preserved blocks</small>
                <ChevronDown size={15} aria-hidden="true" />
            </summary>
            {isOpen && (
                <div className="source-blocks">
                    {section.elements.map((element, index) => (
                        <DocumentElement
                            key={`${sectionIndex}-${element.page || 0}-${element.type || 'block'}-${index}`}
                            element={element}
                            index={index}
                        />
                    ))}
                </div>
            )}
        </details>
    )
}

function splitDocumentSections(elements) {
    const levelTwoCount = elements.filter((element) => (
        element?.type === 'heading' && Number(element.level) === 2 && element.text
    )).length
    if (levelTwoCount < 2) return null

    const introduction = []
    const sections = []
    let current = null

    elements.forEach((element) => {
        if (element?.type === 'heading' && Number(element.level) === 2 && element.text) {
            current = { title: element.text, elements: [] }
            sections.push(current)
            return
        }
        if (current) current.elements.push(element)
        else introduction.push(element)
    })

    return { introduction, sections }
}

export default function ImportedDocument({ elements }) {
    const [isOpen, setIsOpen] = useState(false)
    const safeElements = useMemo(() => normalizeDocumentElements(elements), [elements])
    const counts = useMemo(() => safeElements.reduce((result, element) => {
        const type = element?.type || 'paragraph'
        result[type] = (result[type] || 0) + 1
        return result
    }, {}), [safeElements])
    const documentSections = useMemo(() => splitDocumentSections(safeElements), [safeElements])

    if (safeElements.length === 0) return null

    const supportingCount = (counts.callout || 0) + (counts.code || 0) + (counts.list || 0) + (counts.paragraph || 0)

    return (
        <section className="imported-document" aria-labelledby="imported-document-title">
            <button
                type="button"
                className="imported-document-toggle"
                onClick={() => setIsOpen((current) => !current)}
                aria-expanded={isOpen}
                aria-controls="imported-document-content"
            >
                <span className="imported-document-icon"><FileText size={17} aria-hidden="true" /></span>
                <span>
                    <strong id="imported-document-title">Imported source</strong>
                    <small>{safeElements.length} preserved blocks{supportingCount ? ` · ${supportingCount} notes and references` : ''}</small>
                </span>
                <ChevronDown size={16} className={isOpen ? 'rotated' : ''} aria-hidden="true" />
            </button>

            {isOpen && (
                <div className="imported-document-content" id="imported-document-content">
                    <p className="source-document-intro">This is the PDF’s preserved structure. Roadmap tables are trackable above; guidance, callouts, code, and reference tables stay here instead of becoming fake tasks.</p>
                    {documentSections ? (
                        <div className="source-document-sections">
                            {documentSections.introduction.length > 0 && (
                                <div className="source-blocks source-document-introduction">
                                    {documentSections.introduction.map((element, index) => (
                                        <DocumentElement
                                            key={`intro-${element.page || 0}-${element.type || 'block'}-${index}`}
                                            element={element}
                                            index={index}
                                        />
                                    ))}
                                </div>
                            )}
                            {documentSections.sections.map((section, sectionIndex) => (
                                <DocumentSection
                                    key={`${section.title}-${sectionIndex}`}
                                    section={section}
                                    sectionIndex={sectionIndex}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="source-blocks">
                            {safeElements.map((element, index) => (
                                <DocumentElement
                                    key={`${element.page || 0}-${element.type || 'block'}-${index}`}
                                    element={element}
                                    index={index}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}
        </section>
    )
}
