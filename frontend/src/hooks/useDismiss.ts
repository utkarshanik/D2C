import { useEffect, useRef, type RefObject } from "react"

export const useDismiss = (open: boolean, onClose: () => void, ref: RefObject<HTMLElement | null>) => {
    const closeRef = useRef(onClose)
    closeRef.current = onClose

    useEffect(() => {
        if (!open) return
        const onPointer = (event: PointerEvent) => {
            if (!ref.current?.contains(event.target as Node)) closeRef.current()
        }
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") closeRef.current()
        }
        document.addEventListener("pointerdown", onPointer)
        document.addEventListener("keydown", onKey)
        return () => {
            document.removeEventListener("pointerdown", onPointer)
            document.removeEventListener("keydown", onKey)
        }
    }, [open, ref])
}
