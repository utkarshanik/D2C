import { useEffect, useState } from "react"

const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export default function ReactPreview({ code }: { code: string }) {
    const [html, setHtml] = useState("")
    const [error, setError] = useState("")

    useEffect(() => {
        const form = new FormData()
        form.append("code", code)
        let cancelled = false
        setError("")

        fetch(`${API_URL}/preview-html`, { method: "POST", body: form })
            .then(async (response) => {
                if (!response.ok) throw new Error("Preview failed")
                return response.text()
            })
            .then((page) => {
                if (!cancelled) setHtml(page)
            })
            .catch(() => {
                if (!cancelled) setError("The preview could not be built.")
            })

        return () => {
            cancelled = true
        }
    }, [code])

    if (error) return <div className="empty">{error}</div>
    if (!html) return <div className="empty">Loading preview...</div>

    // Same sandbox as the HTML preview: scripts can run, the page cannot read the app.
    return (
        <iframe
            title="Generated preview"
            srcDoc={html}
            sandbox="allow-scripts"
            className="preview-frame"
        />
    )
}
