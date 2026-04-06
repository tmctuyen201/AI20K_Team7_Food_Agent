import { useState, useRef, KeyboardEvent } from 'react';
import type { ParsedPlace } from './types';
import { useChat } from './hooks/useChat';
import ChatWindow from './components/ChatWindow';
import Sidebar from './components/Sidebar';
import Toast from './components/Toast';

interface ToastState {
  message: string;
  type: 'success' | 'error';
}

function parsedToScored(parsed: ParsedPlace) {
  return {
    place_id: `parsed_${parsed.name.replace(/\s+/g, '_')}`,
    name: parsed.name,
    rating: parsed.rating,
    distance_km: parsed.distance_km,
    score: parsed.rating,
    cuisine_type: undefined,
    address: parsed.address,
  };
}

export default function App() {
  const {
    status,
    turns,
    selectedUserId,
    setSelectedUserId,
    sendMessage,
    selectPlace,
    reset,
    users,
    selectedModel,
    setSelectedModel,
    selectedVersion,
    setSelectedVersion,
    isComparing,
    setIsComparing,
    compareResult,
    showSidebar,
    setShowSidebar,
    chatSessions,
    currentSessionId,
    createNewChat,
    deleteChatSession,
    loadChatSession,
  } = useChat();

  const [input, setInput] = useState('');
  const [toast, setToast] = useState<ToastState | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text) return;

    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    try {
      await sendMessage(text);
    } catch {
      setToast({ message: 'Lỗi gửi tin nhắn', type: 'error' });
    }
  };

  const handleSelectParsedPlace = async (parsed: ParsedPlace) => {
    await selectPlace(parsedToScored(parsed));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
    }
  };

  const statusLabel: Record<string, string> = {
    connected: 'Đã kết nối',
    connecting: 'Đang kết nối...',
    disconnected: 'Chưa kết nối',
    error: 'Lỗi kết nối',
  };

  return (
    <div className={`app${showSidebar ? ' app--with-sidebar' : ''}`}>
      {/* Main column */}
      <div className="app-column">
        {/* Header */}
        <header className="header">
          <div className="header-left">
            <div className="header-logo">
              <span>🍜</span>
              <span>Foodie Agent</span>
            </div>
          </div>
          <div className="header-right">
            <div className="header-status">
              <div className={`status-dot ${status}`} />
              <span>{statusLabel[status]}</span>
            </div>
            <button
              className="icon-btn"
              onClick={() => setShowSidebar(!showSidebar)}
              title={showSidebar ? 'Ẩn sidebar' : 'Hiện sidebar'}
            >
              {showSidebar ? '✕' : '☰'}
            </button>
          </div>
        </header>

        {/* User selector bar */}
        <div className="user-bar">
          <div className="user-bar-left">
            <label htmlFor="user-select" className="user-bar-label">User:</label>
            <select
              id="user-select"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="user-select"
            >
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.name} — {u.city}
                </option>
              ))}
            </select>
          </div>
          <div className="user-bar-right">
            <button className="text-btn" onClick={reset} title="Reset cuộc trò chuyện">
              🗑️ Reset
            </button>
          </div>
        </div>

        {/* Chat area */}
        <ChatWindow
          turns={turns}
          isLoading={status === 'connecting'}
          onSelectPlace={selectPlace}
          onSelectParsedPlace={handleSelectParsedPlace}
          compareResult={compareResult}
          onCompareClose={() => setIsComparing(false)}
        />

        {/* Input */}
        <div className="input-area">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); handleInput(); }}
            onKeyDown={handleKeyDown}
            placeholder="Hỏi tôi về quán ăn gần bạn..."
            rows={1}
            aria-label="Tin nhắn"
          />
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={!input.trim() || status === 'connecting'}
            aria-label="Gửi"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>

        {/* Toast */}
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onDone={() => setToast(null)}
          />
        )}
      </div>

      {/* Sidebar */}
      <Sidebar
        open={showSidebar}
        sessions={chatSessions}
        selectedModel={selectedModel}
        selectedVersion={selectedVersion}
        isComparing={isComparing}
        onToggle={() => setShowSidebar(!showSidebar)}
        onNewChat={createNewChat}
        onSelectSession={loadChatSession}
        onDeleteSession={deleteChatSession}
        onModelChange={setSelectedModel}
        onVersionChange={setSelectedVersion}
        onCompareToggle={() => setIsComparing(!isComparing)}
        currentSessionId={currentSessionId}
      />
    </div>
  );
}