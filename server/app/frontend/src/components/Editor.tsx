import { Link } from "react-router-dom";

const Editor = () => {
  return (
    <main className="editor-page">
      <section className="editor-card">
        <div className="editor-header">
          <span className="editor-badge">Editor Workspace</span>

          <h1>Editor Dashboard</h1>

          <p>
            This area is reserved for users with an assigned Editor role. From
            here, authorized editors can manage platform content, review updates,
            and prepare TradeAdviser resources before publishing.
          </p>
        </div>

        <div className="editor-grid">
          <div className="editor-feature">
            <h2>Market Content</h2>
            <p>
              Review market notes, educational content, and trading insights.
            </p>
          </div>

          <div className="editor-feature">
            <h2>Publishing Queue</h2>
            <p>
              Prepare drafts, validate changes, and submit updates for approval.
            </p>
          </div>

          <div className="editor-feature">
            <h2>Access Control</h2>
            <p>
              Your current session has editor-level access to this workspace.
            </p>
          </div>
        </div>

        <div className="editor-actions">
          <Link to="/" className="editor-button editor-button-secondary">
            Back Home
          </Link>

          <Link to="/dashboard" className="editor-button editor-button-primary">
            Go to Dashboard
          </Link>
        </div>
      </section>
    </main>
  );
};

export default Editor;