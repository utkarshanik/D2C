import { LayoutDashboard, type LucideIcon } from "lucide-react"
import type { ProjectSummary } from "./types"

export const projectIcon: LucideIcon = LayoutDashboard

export const projectTitle = (project: ProjectSummary) => {
    const hint = project.hint.trim()
    return hint || `Design ${project.width}×${project.height}`
}

export const isToday = (value: string) => {
    const hasZone = /(?:z|[+-]\d{2}:\d{2})$/i.test(value)
    const date = new Date(hasZone ? value : `${value}Z`)
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    return date >= start
}
