import { useRef, useState, type ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { useDismiss } from "../hooks/useDismiss"

export type MenuEntry = {
    id: string
    label: string
    icon?: LucideIcon
    disabled?: boolean
    active?: boolean
    onSelect: () => void
}

type Props = {
    label: string
    icon?: LucideIcon
    items: MenuEntry[]
    align?: "left" | "right"
    direction?: "up" | "down"
    hideLabel?: boolean
    disabled?: boolean
    children?: ReactNode
}

export const MenuButton = ({
    label,
    icon: Icon,
    items,
    align = "right",
    direction = "down",
    hideLabel = false,
    disabled = false,
    children,
}: Props) => {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)
    useDismiss(open, () => setOpen(false), rootRef)
    const appearance = children ? "avatar-btn" : hideLabel ? "tool-btn" : "text-btn"

    return (
        <div className={`menu ${align} ${direction}`} ref={rootRef}>
            <button
                type="button"
                className={appearance}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label={label}
                title={label}
                disabled={disabled}
                onClick={() => setOpen((current) => !current)}
            >
                {children ?? (
                    <>
                        {Icon && <Icon size={16} aria-hidden="true" />}
                        {!hideLabel && <span>{label}</span>}
                    </>
                )}
            </button>
            {open && (
                <div className="menu-panel" role="menu" aria-label={label}>
                    {items.map((item) => {
                        const ItemIcon = item.icon
                        return (
                            <button
                                key={item.id}
                                type="button"
                                role="menuitem"
                                className={item.active ? "menu-item active" : "menu-item"}
                                disabled={item.disabled}
                                onClick={() => {
                                    setOpen(false)
                                    item.onSelect()
                                }}
                            >
                                {ItemIcon && <ItemIcon size={16} aria-hidden="true" />}
                                <span>{item.label}</span>
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
