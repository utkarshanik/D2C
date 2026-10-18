import { useEffect, useRef } from "react"
import { Crown, X } from "lucide-react"

type Props = {
    open: boolean
    onClose: () => void
}

export const UpgradeDialog = ({ open, onClose }: Props) => {
    const closeRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
        if (!open) return
        closeRef.current?.focus()
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") onClose()
        }
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [open, onClose])

    if (!open) return null

    return (
        <div className="modal-backdrop" onMouseDown={onClose}>
            <div
                className="modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="upgrade-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <span className="upgrade-icon" aria-hidden="true"><Crown size={18} /></span>
                <h2 id="upgrade-title">Upgrade to Pro</h2>
                <p>Pro is for higher accuracy and longer refine passes. Billing is not connected in this version, so the free plan stays active.</p>
                <button ref={closeRef} type="button" className="modal-close" onClick={onClose}>
                    <X size={16} aria-hidden="true" />
                    <span className="sr-only">Close</span>
                </button>
                <button type="button" className="btn-green" onClick={onClose}>Stay on Free</button>
            </div>
        </div>
    )
}
