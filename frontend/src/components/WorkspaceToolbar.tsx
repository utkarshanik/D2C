import {
    CodeXml,
    Copy,
    Check,
    Download,
    Eye,
    Monitor,
    MoreHorizontal,
    Smartphone,
    Square,
    Tablet,
    Undo2,
} from "lucide-react"
import { MenuButton } from "./MenuButton"
import type { DeviceMode, WorkspaceView } from "../workspace"

type Props = {
    view: WorkspaceView
    onView: (view: WorkspaceView) => void
    device: DeviceMode
    onDevice: (device: DeviceMode) => void
    busy: boolean
    copied: boolean
    canCopy: boolean
    canDownload: boolean
    canUndo: boolean
    canMatch: boolean
    canRegenerate: boolean
    onCopy: () => void
    onDownload: () => void
    onUndo: () => void
    onStop: () => void
    onMatch: () => void
    onRegenerate: () => void
}

const DEVICES: { id: DeviceMode; label: string; icon: typeof Monitor }[] = [
    { id: "desktop", label: "Desktop", icon: Monitor },
    { id: "tablet", label: "Tablet", icon: Tablet },
    { id: "mobile", label: "Mobile", icon: Smartphone },
]

export const WorkspaceToolbar = ({
    view,
    onView,
    device,
    onDevice,
    busy,
    copied,
    canCopy,
    canDownload,
    canUndo,
    canMatch,
    canRegenerate,
    onCopy,
    onDownload,
    onUndo,
    onStop,
    onMatch,
    onRegenerate,
}: Props) => (
    <div className="toolbar">
        <div className="seg" role="group" aria-label="Workspace focus">
            <button
                type="button"
                id="preview-tab"
                className="seg-btn"
                aria-pressed={view === "preview"}
                aria-controls="preview-panel"
                onClick={() => onView("preview")}
            >
                <Eye size={15} aria-hidden="true" />
                Preview
            </button>
            <button
                type="button"
                id="code-tab"
                className="seg-btn"
                aria-pressed={view === "code"}
                aria-controls="code-panel"
                onClick={() => onView("code")}
            >
                <CodeXml size={15} aria-hidden="true" />
                Code
            </button>
        </div>
        <div className="toolbar-tools">
            <div className="device-group" role="group" aria-label="Preview size">
                {DEVICES.map((item) => {
                    const Icon = item.icon
                    return (
                        <button
                            key={item.id}
                            type="button"
                            className="tool-btn"
                            aria-pressed={device === item.id}
                            aria-label={item.label}
                            title={item.label}
                            onClick={() => onDevice(item.id)}
                        >
                            <Icon size={16} aria-hidden="true" />
                        </button>
                    )
                })}
            </div>
            <button
                type="button"
                className="tool-btn"
                aria-label="Download code"
                title="Download code"
                disabled={!canDownload}
                onClick={onDownload}
            >
                <Download size={16} aria-hidden="true" />
            </button>
            <MenuButton
                label="More actions"
                hideLabel
                icon={MoreHorizontal}
                items={[
                    { id: "again", label: "Generate again", onSelect: onRegenerate, disabled: busy || !canRegenerate },
                    { id: "match", label: "Match original more closely", onSelect: onMatch, disabled: busy || !canMatch },
                    { id: "undo", label: "Undo", icon: Undo2, onSelect: onUndo, disabled: busy || !canUndo },
                    { id: "stop", label: "Stop", icon: Square, onSelect: onStop, disabled: !busy },
                ]}
            />
            <span className="tool-divider" aria-hidden="true" />
            <button
                type="button"
                className="tool-btn copy-btn"
                aria-label={copied ? "Copied" : "Copy code"}
                title={copied ? "Copied" : "Copy code"}
                disabled={!canCopy}
                onClick={onCopy}
            >
                {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
            </button>
            <span className="sr-only" role="status">{copied ? "Copied" : ""}</span>
        </div>
        {busy && <span className="toolbar-progress" aria-hidden="true" />}
    </div>
)
