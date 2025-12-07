
export const parseRoadmapText = (text) => {
    const lines = text.split('\n').map(l => l.trim()).filter(l => l)
    const tasks = []
    let currentTimeframe = "General"

    // Improved Heuristics for "Natural" typing
    const explicitHeaderRegex = /^(#{1,3}|phase|month|week|day|step|part|learning path|section)\s*\d*/i
    const explicitTaskRegex = /^(\-|\*|\d+\.|\[\s*\]|\[x\]|•|→)\s+/i

    lines.forEach(line => {
        const isExplicitHeader = explicitHeaderRegex.test(line) || line.endsWith(':')

        if (isExplicitHeader) {
            // Remove Markdown chars (#) and trailing colons
            currentTimeframe = line.replace(/^(#{1,3}\s*)/, '').replace(/:$/, '').trim()
        }
        else {
            // It's a task.
            const title = line.replace(/^(\-|\*|\d+\.|\[\s*\]|\[x\]|•|→)\s+/, '').trim()
            const isDone = line.toLowerCase().includes('[x]')

            tasks.push({
                title: title,
                timeframe: currentTimeframe,
                is_done: isDone
            })
        }
    })

    if (tasks.length === 0) {
        if (text.trim()) {
            tasks.push({ title: text.trim(), timeframe: "General", is_done: false })
        } else {
            throw new Error("Could not detect any tasks.")
        }
    }

    return tasks
}

export const formatRoadmapToText = (roadmapData) => {
    if (!roadmapData || !roadmapData.tasks) return ""

    let text = ""
    const grouped = {}
    const explicitHeaderRegex = /^(phase|month|week|day|step|part|learning path|section)/i

    // Group tasks
    roadmapData.tasks.forEach(t => {
        const tf = t.timeframe || "General"
        if (!grouped[tf]) grouped[tf] = []
        grouped[tf].push(t)
    })

    // Format to text
    Object.entries(grouped).forEach(([timeframe, tasks]) => {
        // Output clean header. If it's a known keyword (Week 1), just print it.
        // If it's custom (e.g. "Intro"), add colon so parser knows it's a header.
        const isKeyword = explicitHeaderRegex.test(timeframe)
        const header = isKeyword ? timeframe : `${timeframe}:`

        text += `${header}\n`
        tasks.forEach(t => {
            // Remove bullet, just text. Keep [x] if done.
            // If user wants purely minimal, maybe strict "Task" is fine.
            // But let's support [x] for done tasks at least.
            // User requested purely minimal format: no [x] or [ ]
            const prefix = ""
            text += `${prefix}${t.title}\n`
        })
        text += "\n"
    })

    return text.trim()
}
