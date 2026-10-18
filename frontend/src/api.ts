// Vite exposes only VITE_ variables from frontend/.env.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
