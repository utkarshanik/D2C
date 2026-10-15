export function Preview({ html }: { html: string }) {
    if (!html) return <div className="empty">The preview appears here when generation finishes.</div>;

    // sandbox="allow-scripts" (and NOT allow-same-origin): the Tailwind script can run, but the
    // generated page can't read your app's cookies, storage or DOM. Model output is untrusted.
    return <iframe title="Generated preview" srcDoc={html} sandbox="allow-scripts" className="preview-frame" />;
}
