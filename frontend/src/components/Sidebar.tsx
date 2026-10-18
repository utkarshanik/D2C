import { Crown, ChevronRight, Loader2, MoreHorizontal, Plus, Sparkles } from "lucide-react"
import { MenuButton } from "./MenuButton"
import { PROFILE } from "../profile"
import { isToday, projectIcon, projectTitle } from "../projects"
import type { ProjectSummary } from "../types"

type Props = {
    open: boolean
    narrow: boolean
    projects: ProjectSummary[]
    projectId: string | null
    busy: boolean
    projectsReady: boolean
    onNewChat: () => void
    onOpenProject: (id: string) => void
    onUpgrade: () => void
    onClose: () => void
}

const ChatList = ({
    projects,
    projectId,
    busy,
    onOpenProject,
}: {
    projects: ProjectSummary[]
    projectId: string | null
    busy: boolean
    onOpenProject: (id: string) => void
}) => (
    <>
        {projects.map((project) => {
            const Icon = projectIcon(project.id)
            const active = project.id === projectId
            const title = projectTitle(project)
            const versions = `${project.version_count} ${project.version_count === 1 ? "version" : "versions"}`
            return (
                <button
                    key={project.id}
                    type="button"
                    className={active ? "chat active" : "chat"}
                    onClick={() => onOpenProject(project.id)}
                    disabled={busy}
                    aria-current={active ? "true" : undefined}
                    title={`${title} · ${versions}`}
                >
                    {busy && active
                        ? <Loader2 size={16} className="spin-icon" aria-hidden="true" />
                        : <Icon size={16} aria-hidden="true" />}
                    <span>{title}</span>
                </button>
            )
        })}
    </>
)

export const Sidebar = ({
    open,
    narrow,
    projects,
    projectId,
    busy,
    projectsReady,
    onNewChat,
    onOpenProject,
    onUpgrade,
    onClose,
}: Props) => {
    const today = projects.filter((project) => isToday(project.created_at))
    const previous = projects.filter((project) => !isToday(project.created_at))

    return (
        <aside className={open ? "sidebar open" : "sidebar"} aria-label="Chats" inert={narrow && !open}>
            <div className="brand">
                <span className="brand-mark" aria-hidden="true"><Sparkles size={16} /></span>
                <strong>Design to Code</strong>
                <span className="beta">Beta</span>
            </div>
            <button type="button" className="new-chat" onClick={onNewChat}>
                <Plus size={16} aria-hidden="true" />
                New chat
            </button>
            <div className="history">
                {!projectsReady && <p className="history-empty">Loading chats…</p>}
                {projectsReady && projects.length === 0 && (
                    <p className="history-empty">No designs yet. Generate one and it will show up here.</p>
                )}
                {today.length > 0 && (
                    <>
                        <p className="history-label">Today</p>
                        <ChatList projects={today} projectId={projectId} busy={busy} onOpenProject={onOpenProject} />
                    </>
                )}
                {previous.length > 0 && (
                    <>
                        <p className="history-label">Previous</p>
                        <ChatList projects={previous} projectId={projectId} busy={busy} onOpenProject={onOpenProject} />
                    </>
                )}
            </div>
            <button type="button" className="upgrade" onClick={onUpgrade}>
                <span className="upgrade-icon" aria-hidden="true"><Crown size={16} /></span>
                <span className="upgrade-copy">
                    <strong>Upgrade to Pro</strong>
                    <span>Get higher accuracy and more features</span>
                </span>
                <span className="upgrade-arrow" aria-hidden="true"><ChevronRight size={16} /></span>
            </button>
            <div className="profile">
                <span className="avatar" aria-hidden="true">{PROFILE.initials}</span>
                <span className="profile-copy">
                    <strong>{PROFILE.name}</strong>
                    <span>{PROFILE.plan}</span>
                </span>
                <MenuButton
                    label="Account menu"
                    hideLabel
                    direction="up"
                    icon={MoreHorizontal}
                    items={[
                        { id: "new", label: "New chat", icon: Plus, onSelect: onNewChat, disabled: busy },
                        { id: "upgrade", label: "Upgrade to Pro", icon: Crown, onSelect: onUpgrade },
                    ]}
                />
            </div>
            <button type="button" className="sidebar-close" onClick={onClose}>
                Close
            </button>
        </aside>
    )
}
