import { CircleHelp, Crown, History, PanelLeft, Plus } from "lucide-react"
import { useRef, useState } from "react"
import { useDismiss } from "../hooks/useDismiss"
import { PROFILE } from "../profile"
import { projectIcon, projectTitle } from "../projects"
import type { ProjectSummary } from "../types"
import { MenuButton } from "./MenuButton"

type Props = {
    projects: ProjectSummary[]
    projectId: string | null
    busy: boolean
    onOpenProject: (id: string) => void
    onNewChat: () => void
    onUpgrade: () => void
    onMenu: () => void
}

const HelpButton = () => {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)
    useDismiss(open, () => setOpen(false), rootRef)

    return (
        <div className="menu right down" ref={rootRef}>
            <button
                type="button"
                className="text-btn"
                aria-expanded={open}
                aria-label="Help"
                title="Help"
                onClick={() => setOpen((current) => !current)}
            >
                <CircleHelp size={16} aria-hidden="true" />
                <span>Help</span>
            </button>
            {open && (
                <div className="menu-panel help-panel" role="dialog" aria-label="Help">
                    <p className="help-title">Design to code</p>
                    <ol>
                        <li>Add a screenshot or a Figma link.</li>
                        <li>Choose HTML + Tailwind or React + MUI.</li>
                        <li>Add optional details, then generate.</li>
                    </ol>
                    <p>After a result, describe a change and send it to refine. Undo and a closer match are in the more menu.</p>
                </div>
            )}
        </div>
    )
}

export const TopBar = ({ projects, projectId, busy, onOpenProject, onNewChat, onUpgrade, onMenu }: Props) => {
    const history = projects.length
        ? projects.map((project) => ({
            id: project.id,
            label: projectTitle(project),
            icon: projectIcon(project.id),
            disabled: busy,
            active: project.id === projectId,
            onSelect: () => onOpenProject(project.id),
        }))
        : [{ id: "empty", label: "No saved designs yet", disabled: true, onSelect: () => undefined }]

    return (
        <header className="topbar">
            <button type="button" className="tool-btn nav-toggle" aria-label="Open menu" onClick={onMenu}>
                <PanelLeft size={16} aria-hidden="true" />
            </button>
            <span className="topbar-spacer" />
            <MenuButton label="History" icon={History} items={history} />
            <HelpButton />
            <MenuButton
                label="Account"
                hideLabel
                items={[
                    { id: "new", label: "New chat", icon: Plus, onSelect: onNewChat },
                    { id: "upgrade", label: "Upgrade to Pro", icon: Crown, onSelect: onUpgrade },
                ]}
            >
                <span className="avatar" aria-hidden="true">{PROFILE.initials}</span>
            </MenuButton>
        </header>
    )
}
