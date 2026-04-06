import { useRef, useEffect } from 'react';
import type { AgentTurn, ScoredPlace, ParsedPlace, CompareResult } from '../types';
import PlaceCard from './PlaceCard';
import ReasoningPanel from './ReasoningPanel';
import ComparePanel from './ComparePanel';

interface Props {
  turns: AgentTurn[];
  isLoading: boolean;
  onSelectPlace: (place: ScoredPlace) => void;
  onSelectParsedPlace: (parsed: ParsedPlace) => void;
  compareResult?: CompareResult | null;
  onCompareClose: () => void;
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

/** Render assistant text with **bold** preserved as <strong> */
function renderMessage(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>,
  );
}

/** Version badge shown next to assistant bubble */
function VersionBadge({ text }: { text: string }) {
  const map: Record<string, { label: string; color: string }> = {
    v1: { label: 'v1 ReAct', color: '#6366f1' },
    v2: { label: 'v2 LangGraph', color: '#10b981' },
    'no-tools': { label: 'LLM only', color: '#f59e0b' },
  };
  const meta = map[text];
  if (!meta) return null;
  return (
    <span className="version-badge" style={{ background: meta.color }}>
      {meta.label}
    </span>
  );
}

export default function ChatWindow({ turns, isLoading, onSelectPlace, onSelectParsedPlace, compareResult, onCompareClose }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, isLoading]);

  return (
    <>
      <div className="chat" ref={chatRef} role="log" aria-live="polite">
        {turns.length === 0 && !isLoading && (
          <div className="welcome">
            <div className="welcome-icon">🍜</div>
            <h2>Chào bạn!</h2>
            <p>Hãy hỏi tôi về quán ăn gần bạn.<br />Ví dụ: <em>"Tìm quán phở ngon gần đây"</em></p>
          </div>
        )}

        {turns.map((turn, idx) => {
          // Get version from previous user message (first turn = first user message)
          const prevUserTurn = turns.slice(0, idx).reverse().find((t) => t.role === 'user');
          const isLast = idx === turns.length - 1;

          return (
            <div key={turn.timestamp} className={`msg ${turn.role}`}>
              {/* Bubble */}
              <div className="msg-bubble">
                {turn.role === 'user' ? (
                  <span>{turn.message}</span>
                ) : (
                  <>
                    {turn.message && (
                      <div className="assistant-content">
                        <div className="assistant-text">{renderMessage(turn.message)}</div>
                      </div>
                    )}

                    {/* Places */}
                    {turn.places && turn.places.length > 0 && (
                      <div className="places-list">
                        {turn.places.map((place, i) => (
                          <PlaceCard
                            key={place.place_id}
                            place={place}
                            rank={i + 1}
                            onSelect={() => onSelectPlace(place)}
                          />
                        ))}
                      </div>
                    )}

                    {/* Tool debug log (legacy) */}
                    {turn.toolCalls && turn.toolCalls.length > 0 && (
                      <div className="tool-log">
                        {turn.toolCalls.map((tc, i) => (
                          <div key={i} className="tool-log-entry">
                            <span className="tool-name">[{tc.tool}]</span>
                            <span className={tc.error ? 'tool-error' : 'tool-success'}>
                              {tc.error ? `Error: ${tc.error}` : `OK — ${String(tc.result ?? '').substring(0, 80)}`}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Meta row: time + version badge */}
              <div className="msg-meta">
                {turn.role === 'assistant' && isLast && (
                  <VersionBadge text={prevUserTurn?.message.includes('v1') ? 'v1' : prevUserTurn?.message.includes('no-tools') ? 'no-tools' : 'v2'} />
                )}
                <span className="msg-time">{formatTime(turn.timestamp)}</span>
              </div>

              {/* Reasoning panel — OUTSIDE bubble */}
              {turn.role === 'assistant' && turn.reasoningSteps && turn.reasoningSteps.length > 0 && (
                <div className="reasoning-wrapper">
                  <ReasoningPanel
                    steps={turn.reasoningSteps}
                    toolResults={turn.toolResults || []}
                  />
                </div>
              )}
            </div>
          );
        })}

        {/* Typing indicator */}
        {isLoading && (
          <div className="msg assistant">
            <div className="msg-bubble typing-bubble">
              <div className="typing">
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Compare modal overlay — only shown when compareResult exists */}
      {compareResult && (
        <ComparePanel
          result={compareResult}
          onSelectPlace={onSelectPlace}
          onSelectParsedPlace={onSelectParsedPlace}
          onClose={onCompareClose}
        />
      )}
    </>
  );
}