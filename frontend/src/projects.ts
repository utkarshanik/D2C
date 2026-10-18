import {
    BadgeDollarSign,
    CircleUser,
    CreditCard,
    LayoutDashboard,
    Monitor,
    Settings,
    Smartphone,
    type LucideIcon,
} from "lucide-react"
import type { ProjectSummary } from "./types"

const ICONS: LucideIcon[] = [LayoutDashboard, CircleUser, BadgeDollarSign, CreditCard, Settings, Monitor, Smartphone]

export const projectTitle = (project: ProjectSummary) => {
    const hint = project.hint.trim()
    return hint || `Design ${project.width}×${project.height}`
}

export const projectIcon = (id: string): LucideIcon => {
    let total = 0
    for (let index = 0; index < id.length; index += 1) total += id.charCodeAt(index)
    return ICONS[total % ICONS.length]
}

export const isToday = (value: string) => {
    const hasZone = /(?:z|[+-]\d{2}:\d{2})$/i.test(value)
    const date = new Date(hasZone ? value : `${value}Z`)
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    return date >= start
}
