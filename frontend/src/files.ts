export const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"]
export const MAX_BYTES = 5 * 1024 * 1024

export const validateDesignFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) return "Use a PNG, JPEG or WEBP image."
    if (file.size > MAX_BYTES) return "Image is larger than 5 MB."
    return null
}
