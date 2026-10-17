import { SandpackPreview, SandpackProvider } from "@codesandbox/sandpack-react"

// Same versions the backend screenshot page loads, so the preview and the
// refine screenshot are looking at the same React and MUI.
const DEPENDENCIES = {
    react: "18.3.1",
    "react-dom": "18.3.1",
    "@mui/material": "5.18.0",
    "@emotion/react": "11.13.3",
    "@emotion/styled": "11.13.0",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
}

const ENTRY = `import { createRoot } from "react-dom/client"
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material"
import App from "./App"

const root = createRoot(document.getElementById("root")!)
root.render(
  <ThemeProvider theme={createTheme()}>
    <CssBaseline />
    <App />
  </ThemeProvider>
)
`

export default function ReactPreview({ code }: { code: string }) {
    return (
        <div className="react-preview">
            <SandpackProvider
                template="react-ts"
                theme="light"
                files={{ "/App.tsx": code, "/index.tsx": ENTRY }}
                customSetup={{ dependencies: DEPENDENCIES }}
                options={{ recompileMode: "delayed", recompileDelay: 400 }}
            >
                <SandpackPreview
                    showOpenInCodeSandbox={false}
                    showRefreshButton={false}
                    style={{ height: "100%" }}
                />
            </SandpackProvider>
        </div>
    )
}
