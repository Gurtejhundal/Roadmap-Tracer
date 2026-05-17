const headingRegex = /^(#{1,6}\s*)?((phase|month|week|day|module|unit|section|part|step|sprint|milestone|quarter|q)\s*[\divx]*|learning path|foundation|foundations|advanced|capstone|project|projects|assessment|review|final full mock|core strategy|version\s*[\d.]+\s*upgrades|target profile by month\s*\d+|non-negotiable operating rules|weekly time budget|milestone gates|roadmap overview|final checklist|final priority list|final coding revision set|mock mcqs|coding question\s*\d*)\b[\s:.-]*/i
const bulletRegex = /^\s*(-|\*|\+|\d+[.)]|\[[ xX]\]|[\u2022\u25e6\u2023\u2043\u2219\u2192])\s*/u
const dayRegex = /^(day\s*\d+\b.*)$/i
const timeRangeRegex = /^\d{1,2}(?::\d{2})?\s*(am|pm)?\s*[-\u2013\u2014]\s*\d{1,2}(?::\d{2})?\s*(am|pm)?(\b.*)?$/i
const noteSectionRegex = /^(.+\s+revision notes?|.+\s+mcq points?|coding practice(\s+for .+)?|practice(\s+.+)?|requirements|queries|cover these topics( properly)?|advantages|disadvantages|types|examples|commands|uses|steps|features|important points|mock mcqs|what not to do|the exact codetantra method|final checklist for 30\/30|final priority list)$/i
const questionAnswerRegex = /^(.+\?)\s+(.+)$/
const numberedHeadingRegex = /^\d{1,2}\.\s+[A-Z][A-Za-z0-9 ,'+/&().:-]{3,}$/
const percentRegex = /^\d+\s*%/
const sqlStatementRegex = /^(select|insert|update|delete|create|alter|drop|truncate|grant|revoke|commit|rollback|savepoint|explain)\b/i
const acronymRegex = /^[A-Z0-9]{2,8}$/

const normalizeLine = (line) => line.trim().replace(/\u2013|\u2014/g, '-')

const cleanHeading = (line) => normalizeLine(line)
    .replace(/^\s*#{1,6}\s*/, '')
    .replace(/:$/, '')
    .trim()

const cleanTask = (line) => normalizeLine(line).replace(bulletRegex, '').replace(/\s+/g, ' ').trim()

const isHeading = (line) => {
    if (!line) return false
    if (numberedHeadingRegex.test(line)) return true
    if (bulletRegex.test(line)) return false
    if (timeRangeRegex.test(line) || noteSectionRegex.test(line)) return true
    if (percentRegex.test(line) || sqlStatementRegex.test(line) || acronymRegex.test(line)) return false
    if (line.endsWith(':') || /^\s*#{1,6}\s+\S+/.test(line) || numberedHeadingRegex.test(line) || headingRegex.test(line)) return true

    return false
}

const composeTimeframe = (dayLabel, heading) => {
    const clean = cleanHeading(heading)
    if (dayLabel && clean && !clean.toLowerCase().startsWith(dayLabel.toLowerCase())) {
        return `${dayLabel} - ${clean}`
    }
    return clean || dayLabel || 'General'
}

const appendToTimeframe = (baseLabel, heading) => {
    const clean = cleanHeading(heading)
    if (baseLabel && clean && !baseLabel.toLowerCase().includes(clean.toLowerCase())) {
        return `${baseLabel} - ${clean}`
    }
    return clean || baseLabel || 'General'
}

export const parseRoadmapText = (text) => {
    const lines = text.split('\n').map(normalizeLine).filter(Boolean)
    const tasks = []
    let currentTimeframe = 'General'
    let baseTimeframe = 'General'
    let currentDay = ''
    let pendingTime = ''

    lines.forEach((line, index) => {
        if (index === 0 && currentTimeframe === 'General' && !bulletRegex.test(line)) {
            currentTimeframe = cleanHeading(line)
            baseTimeframe = currentTimeframe
            return
        }

        if (isHeading(line)) {
            const heading = cleanHeading(line)

            if (dayRegex.test(heading)) {
                currentDay = heading
                pendingTime = ''
                currentTimeframe = heading
                baseTimeframe = heading
                return
            }

            if (timeRangeRegex.test(heading)) {
                pendingTime = heading
                currentTimeframe = composeTimeframe(currentDay, pendingTime)
                baseTimeframe = currentTimeframe
                return
            }

            if (pendingTime) {
                currentTimeframe = composeTimeframe(currentDay, `${pendingTime} - ${heading}`)
                baseTimeframe = currentTimeframe
                pendingTime = ''
            } else if (noteSectionRegex.test(heading) && baseTimeframe !== 'General') {
                currentTimeframe = appendToTimeframe(baseTimeframe, heading)
            } else {
                currentTimeframe = composeTimeframe(currentDay, heading)
                baseTimeframe = currentTimeframe
            }
            return
        }

        const shouldTrack = bulletRegex.test(line) || questionAnswerRegex.test(line) || currentTimeframe !== 'General'
        if (!shouldTrack) return

        const title = cleanTask(line)
        if (!title) return

        tasks.push({
            title,
            timeframe: currentTimeframe,
            is_done: /\[[xX]\]/.test(line),
        })
    })

    if (tasks.length === 0 && text.trim()) {
        return [{ title: text.trim(), timeframe: 'General', is_done: false }]
    }

    if (tasks.length === 0) {
        throw new Error('Could not detect any tasks.')
    }

    return tasks
}

export const formatRoadmapToText = (roadmapData) => {
    if (!roadmapData || !roadmapData.tasks) return ''

    const grouped = roadmapData.tasks.reduce((acc, task) => {
        const timeframe = task.timeframe || 'General'
        if (!acc[timeframe]) acc[timeframe] = []
        acc[timeframe].push(task)
        return acc
    }, {})

    return Object.entries(grouped)
        .map(([timeframe, tasks]) => {
            const lines = [`${timeframe}:`]
            tasks.forEach((task) => {
                lines.push(`${task.is_done ? '[x]' : '-'} ${task.title}`)
            })
            return lines.join('\n')
        })
        .join('\n\n')
}
