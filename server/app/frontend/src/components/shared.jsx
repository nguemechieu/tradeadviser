/**
 * Reusable UI Components for Server Dashboard
 */

export function PillarNav({ activePillar, onChange }) {
  const pillars = [
    { id: "operations", label: "Operations", icon: "⚙️" },
    { id: "risk", label: "Risk", icon: "⚠️" },
    { id: "users-licenses", label: "Users & Licenses", icon: "👥" },
    { id: "agents", label: "Agents & AI", icon: "🤖" },
    { id: "performance-audit", label: "Performance & Audit", icon: "📊" },
  ];

  return (
    <nav className="pillar-nav">
      {pillars.map(pillar => (
        <button
          key={pillar.id}
          className={`pillar-nav__item ${activePillar === pillar.id ? "active" : ""}`}
          onClick={() => onChange(pillar.id)}
        >
          <span className="pillar-nav__icon">{pillar.icon}</span>
          <span className="pillar-nav__label">{pillar.label}</span>
        </button>
      ))}
    </nav>
  );
}

export function StatusIndicator({ status, size = "medium" }) {
  const statusColors = {
    healthy: "#10b981",
    degraded: "#f59e0b",
    unhealthy: "#ef4444",
    offline: "#6b7280",
    active: "#10b981",
    paused: "#f59e0b",
    error: "#ef4444",
    success: "#10b981",
  };

  return (
    <span
      className={`status-indicator status-indicator--${size}`}
      style={{ backgroundColor: statusColors[status] || "#6b7280" }}
      title={status}
    />
  );
}

export function MetricBox({ label, value, subtext, tone = "neutral" }) {
  return (
    <div className={`metric-box metric-box--${tone}`}>
      <p className="metric-box__label">{label}</p>
      <div className="metric-box__value">{value}</div>
      {subtext && <p className="metric-box__subtext">{subtext}</p>}
    </div>
  );
}

export function DataTable({ columns, rows, onRowClick }) {
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} style={{ width: col.width }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={idx}
              onClick={() => onRowClick?.(row)}
              className={onRowClick ? "clickable" : ""}
            >
              {columns.map(col => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Alert({ type, title, message, dismissible = true, onDismiss }) {
  return (
    <div className={`alert alert--${type}`}>
      <div className="alert__content">
        <p className="alert__title">{title}</p>
        {message && <p className="alert__message">{message}</p>}
      </div>
      {dismissible && (
        <button className="alert__dismiss" onClick={onDismiss}>
          ✕
        </button>
      )}
    </div>
  );
}

export function Card({ title, subtitle, action, children }) {
  return (
    <div className="card">
      <div className="card__header">
        <div>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
          {title && <h3 className="card__title">{title}</h3>}
        </div>
        {action && <div className="card__action">{action}</div>}
      </div>
      <div className="card__content">{children}</div>
    </div>
  );
}

export function Button({ variant = "primary", size = "medium", onClick, disabled, children }) {
  return (
    <button
      className={`button button--${variant} button--${size}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export function Badge({ type, children }) {
  return <span className={`badge badge--${type}`}>{children}</span>;
}

export function LoadingSpinner() {
  return <div className="spinner" />;
}

export function EmptyState({ title, message, action }) {
  return (
    <div className="empty-state">
      <p className="empty-state__title">{title}</p>
      {message && <p className="empty-state__message">{message}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  );
}

// ========== Data Visualization ==========

export function PerformanceChart({ title, data, metric }) {
  return (
    <Card title={title}>
      <div style={{ height: "200px", background: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--line)" }}>
        <p style={{ color: "var(--muted)" }}>📈 {metric || "Chart"} visualization</p>
      </div>
    </Card>
  );
}

export function HeatMap({ title, data }) {
  return (
    <Card title={title}>
      <div style={{ height: "200px", background: "linear-gradient(90deg, rgba(103, 226, 163, 0.1), rgba(255, 125, 141, 0.1))", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--line)" }}>
        <p style={{ color: "var(--muted)" }}>🔥 Heat map visualization</p>
      </div>
    </Card>
  );
}

// ========== Detail Panel ==========

export function DetailPanel({ isOpen, title, onClose, children }) {
  if (!isOpen) return null;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.5)", display: "flex", alignItems: "flex-end", zIndex: 1000 }} onClick={onClose}>
      <div
        style={{ width: "100%", maxWidth: "500px", background: "var(--bg-panel)", borderRadius: "16px 16px 0 0", padding: "20px", maxHeight: "80vh", overflow: "auto", boxShadow: "var(--shadow)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <h3 style={{ margin: 0, fontSize: "1.3rem", fontWeight: 600 }}>{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              fontSize: "1.5em",
              cursor: "pointer",
              color: "var(--muted)",
              padding: 0,
            }}
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ========== Filter Controls ==========

export function FilterBar({ filters, onChange }) {
  return (
    <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "20px", flexWrap: "wrap" }}>
      {filters.map((filter) => (
        <select
          key={filter.key}
          value={filter.value}
          onChange={(e) => onChange(filter.key, e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: "8px",
            border: "1px solid var(--line)",
            background: "var(--bg-soft)",
            color: "var(--text)",
            fontSize: "0.9rem",
            cursor: "pointer",
          }}
        >
          {filter.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ))}
    </div>
  );
}

// ========== ComplianceCard ==========

export function ComplianceCard({ icon, title, description, status = "compliant", details }) {
  const statusColor = status === "compliant" ? "var(--positive)" : status === "warning" ? "var(--warn)" : "var(--danger)";

  return (
    <div
      style={{
        padding: "16px",
        border: "1px solid var(--line)",
        borderRadius: "12px",
        background: "var(--bg-soft)",
        display: "flex",
        gap: "12px",
      }}
    >
      <div style={{ fontSize: "1.8em" }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: "0 0 4px", fontWeight: 600, fontSize: "0.95rem" }}>
          {title}{" "}
          <span style={{ color: statusColor, fontSize: "0.8em", fontWeight: "bold" }}>
            ({status.toUpperCase()})
          </span>
        </p>
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)" }}>{description}</p>
        {details && <p style={{ margin: "8px 0 0", fontSize: "0.8rem", color: "var(--muted)" }}>{details}</p>}
      </div>
    </div>
  );
}
