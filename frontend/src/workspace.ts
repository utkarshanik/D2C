export type WorkspaceView = "preview" | "code"
export type DeviceMode = "desktop" | "tablet" | "mobile"
export type DesignSource = "screenshot" | "figma"

export const DEVICE_WIDTH: Record<Exclude<DeviceMode, "desktop">, number> = {
    tablet: 768,
    mobile: 390,
}
