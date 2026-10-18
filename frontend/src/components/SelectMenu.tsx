import { useRef, useState } from "react"
import { Check, ChevronDown, type LucideIcon } from "lucide-react"
import { useDismiss } from "../hooks/useDismiss"

export type SelectOption = {
    value: string
    label: string
    icon?: LucideIcon
}

type Props = {
    step: number
    title: string
    value: string
    options: SelectOption[]
    onChange: (value: string) => void
    onOpen?: () => void
    disabled?: boolean
}

export const SelectMenu = ({ step, title, value, options, onChange, onOpen, disabled = false }: Props) => {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)
    const current = options.find((option) => option.value === value) ?? options[0]
    useDismiss(open, () => setOpen(false), rootRef)

    return (
        <div className="select up" ref={rootRef}>
            <button
                type="button"
                className="select-trigger"
                aria-haspopup="listbox"
                aria-expanded={open}
                disabled={disabled}
                onClick={() => {
                    if (!open) onOpen?.()
                    setOpen((currentOpen) => !currentOpen)
                }}
            >
                <span className="step-badge" aria-hidden="true">{step}</span>
                <span className="select-copy">
                    <span className="select-title">{title}</span>
                    <span className="select-value">{current?.label}</span>
                </span>
                <ChevronDown size={16} aria-hidden="true" />
            </button>
            {open && (
                <ul className="select-menu" role="listbox" aria-label={title}>
                    {options.map((option) => {
                        const Icon = option.icon
                        const selected = option.value === value
                        return (
                            <li key={option.value} role="none">
                                <button
                                    type="button"
                                    role="option"
                                    aria-selected={selected}
                                    className={selected ? "select-option active" : "select-option"}
                                    onClick={() => {
                                        onChange(option.value)
                                        setOpen(false)
                                    }}
                                >
                                    {Icon && <Icon size={16} aria-hidden="true" />}
                                    <span>{option.label}</span>
                                    {selected && <Check size={14} aria-hidden="true" />}
                                </button>
                            </li>
                        )
                    })}
                </ul>
            )}
        </div>
    )
}
