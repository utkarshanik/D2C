import { useEffect, useRef, useState } from "react"
import { Maximize2, ZoomIn, ZoomOut } from "lucide-react"
import { Preview } from "./Preview"
import type { ImageMeta } from "../types"
import { DEVICE_WIDTH, type DeviceMode } from "../workspace"

const MIN_ZOOM = 50
const MAX_ZOOM = 200

type Props = {
    html: string
    target: string
    device: DeviceMode
    zoom: number
    onZoom: (zoom: number) => void
    busy: boolean
    status: string
    meta: ImageMeta | null
}

export const PreviewStage = ({ html, target, device, zoom, onZoom, busy, status, meta }: Props) => {
    const canvasRef = useRef<HTMLDivElement>(null)
    const [size, setSize] = useState({ width: 0, height: 0 })

    useEffect(() => {
        const node = canvasRef.current
        if (!node) return
        const measure = () => setSize({ width: node.clientWidth, height: node.clientHeight })
        measure()
        const observer = new ResizeObserver(measure)
        observer.observe(node)
        return () => observer.disconnect()
    }, [])

    const naturalWidth = device === "desktop" ? Math.max(size.width - 32, 280) : DEVICE_WIDTH[device]
    const naturalHeight = Math.max(size.height - 88, 240)
    const scale = zoom / 100

    return (
        <div className="stage">
            {meta && <p className="meta-pill">{meta.width} × {meta.height}</p>}
            <div className="stage-canvas" ref={canvasRef}>
                {!html ? (
                    <div className="stage-message" role="status">
                        {busy && <span className="spinner" aria-hidden="true" />}
                        <p>{busy ? (status || "Generating your design…") : "The preview appears here when generation finishes."}</p>
                    </div>
                ) : (
                    <div className="stage-scale" style={{ width: naturalWidth * scale, height: naturalHeight * scale }}>
                        <div
                            className={device === "desktop" ? "stage-frame" : "stage-frame is-device"}
                            style={{ width: naturalWidth, height: naturalHeight, transform: `scale(${scale})` }}
                        >
                            <Preview html={html} target={target} />
                        </div>
                    </div>
                )}
            </div>
            <div className="zoombar" role="group" aria-label="Zoom">
                <button type="button" aria-label="Zoom out" disabled={zoom <= MIN_ZOOM} onClick={() => onZoom(Math.max(MIN_ZOOM, zoom - 10))}>
                    <ZoomOut size={15} aria-hidden="true" />
                </button>
                <span>{zoom}%</span>
                <button type="button" aria-label="Zoom in" disabled={zoom >= MAX_ZOOM} onClick={() => onZoom(Math.min(MAX_ZOOM, zoom + 10))}>
                    <ZoomIn size={15} aria-hidden="true" />
                </button>
                <button type="button" aria-label="Reset zoom" title="Reset zoom" onClick={() => onZoom(100)}>
                    <Maximize2 size={15} aria-hidden="true" />
                </button>
            </div>
        </div>
    )
}
