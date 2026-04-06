import { useState, useRef, KeyboardEvent } from 'react';
import type { ParsedPlace } from './types';
import { useChat } from './hooks/useChat';
import ChatWindow from './components/ChatWindow';
import Toast from './components/Toast';

interface ToastState {
  message: string;
  type: 'success' | 'error';
}

/** Convert ParsedPlace (from LLM text) → ScoredPlace shape for storage */
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
    } catch (err) {
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
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-logo">
          <span>🍜</span>
          <span>Foodie Agent</span>
        </div>
        <div className="header-status">
          <div className={`status-dot ${status}`} />
          <span>{statusLabel[status]}</span>
        </div>
      </header>

      {/* User selector */}
      <div className="user-selector">
        <label htmlFor="user-select">Đổi user:</label>
        <select
          id="user-select"
          value={selectedUserId}
          onChange={(e) => setSelectedUserId(e.target.value)}
        >
          {users.map((u) => (
            <option key={u.user_id} value={u.user_id}>
              {u.user_id} — {u.name} ({u.city})
            </option>
          ))}
        </select>
        <button
          onClick={reset}
          style={{
            marginLeft: 'auto',
            padding: '5px 12px',
            fontSize: '0.8rem',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-surface)',
            cursor: 'pointer',
          }}
        >
          🔄 Reset
        </button>
      </div>

      {/* Chat area */}
      <ChatWindow
        turns={turns}
        isLoading={status === 'connecting'}
        onSelectPlace={selectPlace}
        onSelectParsedPlace={handleSelectParsedPlace}
      />

      {/* Input */}
      <div className="input-area">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          placeholder="Hỏi tôi về quán ăn gần bạn... (Enter để gửi, Shift+Enter xuống dòng)"
          rows={1}
          aria-label="Tin nhắn"
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || status === 'connecting'}
          aria-label="Gửi"
        >
          ➤
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
  );
}
