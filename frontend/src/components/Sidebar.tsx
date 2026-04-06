import type { ChatSession, AgentVersion } from "../types";

const MODELS = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
];

const VERSIONS: { value: AgentVersion; label: string; desc: string }[] = [
  { value: "v1", label: "ReAct", desc: "Loop với tools" },
  { value: "v2", label: "LangGraph", desc: "Linear graph" },
  { value: "no-tools", label: "LLM only", desc: "Không tool" },
];

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "vừa xong";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

interface Props {
  open: boolean;
  sessions: ChatSession[];
  selectedModel: string;
  selectedVersion: AgentVersion;
  isComparing: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onModelChange: (model: string) => void;
  onVersionChange: (version: AgentVersion) => void;
  onCompareToggle: () => void;
  currentSessionId: string;
}

export default function Sidebar({
  open,
  sessions,
  selectedModel,
  selectedVersion,
  isComparing,
  onToggle,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onModelChange,
  onVersionChange,
  onCompareToggle,
  currentSessionId,
}: Props) {
  return (
    <aside className={`sidebar${open ? " sidebar--open" : " sidebar--closed"}`}>
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span>🍜</span>
          <span>Foodie Agent</span>
        </div>
        <button className="sidebar-close" onClick={onToggle} title="Đóng">✕</button>
      </div>

      {open && (
        <>
          {/* New Chat */}
          <div className="sidebar-top">
            <button className="btn-new-chat" onClick={onNewChat}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M12 4v16m-8-8h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/>
              </svg>
              New Chat
            </button>
          </div>

          {/* Settings */}
          <div className="sidebar-settings">
            <div className="settings-group">
              <label className="settings-label">Model</label>
              <select
                className="settings-select"
                value={selectedModel}
                onChange={(e) => onModelChange(e.target.value)}
              >
                {MODELS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            <div className="settings-group">
              <label className="settings-label">Agent Version</label>
              <div className="version-cards">
                {VERSIONS.map((v) => (
                  <button
                    key={v.value}
                    className={`version-card${selectedVersion === v.value ? " version-card--active" : ""}`}
                    onClick={() => onVersionChange(v.value)}
                    title={v.desc}
                  >
                    <span className="version-card-name">{v.label}</span>
                    <span className="version-card-desc">{v.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <button
              className={`btn-compare${isComparing ? " btn-compare--active" : ""}`}
              onClick={onCompareToggle}
            >
              <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
                <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" fill="none"/>
              </svg>
              {isComparing ? "Compare Mode ON" : "Compare 3 Versions"}
            </button>
          </div>

          {/* History */}
          <div className="sidebar-history">
            <div className="sidebar-section-title">
              <span>Lịch sử</span>
              <span className="history-count">{sessions.length}</span>
            </div>

            <div className="session-list">
              {sessions.length === 0 && (
                <div className="session-empty">
                  <span>💬</span>
                  <p>Chưa có cuộc trò chuyện nào</p>
                </div>
              )}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`session-item${s.id === currentSessionId ? " session-item--active" : ""}`}
                  onClick={() => onSelectSession(s.id)}
                >
                  <div className="session-item-body">
                    <div className="session-item-title">{s.title || "New conversation"}</div>
                    {s.preview && (
                      <div className="session-item-preview">{s.preview}</div>
                    )}
                    <div className="session-item-meta">
                      <span className="session-meta-badge">{s.user_id}</span>
                      <span className="session-meta-badge">{s.version}</span>
                      <span className="session-meta-time">{timeAgo(s.updated_at)}</span>
                    </div>
                  </div>
                  <button
                    className="session-delete"
                    onClick={(e) => { e.stopPropagation(); onDeleteSession(s.id); }}
                    title="Xóa"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}