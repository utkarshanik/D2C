import { useRef, useState } from "react"
import { Check, ChevronDown, type LucideIcon } from "lucide-react"
import { useDismiss } from "../hooks/useDismiss"

export type SelectOption = {
    value: string
    label: string
    icon?: LucideIcon
}

type Props = {
    label: string
    value: string
    options: SelectOption[]
    onChange: (value: string) => void
    onOpen?: () => void
    disabled?: boolean
}

export const SelectMenu = ({ label, value, options, onChange, onOpen, disabled = false }: Props) => {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement>(null)
    const current = options.find((option) => option.value === value) ?? options[0]
    const CurrentIcon = current?.icon
    useDismiss(open, () => setOpen(false), rootRef)

    return (
        <div className="select" ref={rootRef}>
            <button
                type="button"
                className="chip"
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-label={`${label}: ${current?.label}`}
                title={label}
                disabled={disabled}
                onClick={() => {
                    if (!open) onOpen?.()
                    setOpen((currentOpen) => !currentOpen)
                }}
            >
                {CurrentIcon && <CurrentIcon size={14} aria-hidden="true" />}
                <span>{current?.label}</span>
                <ChevronDown size={14} aria-hidden="true" />
            </button>
            {open && (
                <ul className="select-menu" role="listbox" aria-label={label}>
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
