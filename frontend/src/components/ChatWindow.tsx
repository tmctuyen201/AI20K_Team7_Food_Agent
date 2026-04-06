import { useState, useRef, useEffect } from 'react';
import type { AgentTurn, ScoredPlace } from '../types';
import PlaceCard from './PlaceCard';
import Toast from './Toast';

interface Props {
  turns: AgentTurn[];
  isLoading: boolean;
  onSelectPlace: (place: ScoredPlace) => void;
}

export default function ChatWindow({ turns, isLoading, onSelectPlace }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, isLoading]);

  const formatTime = (ts: number) =>
    new Date(ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="chat" role="log" aria-live="polite">
      {turns.length === 0 && !isLoading && (
        <div className="welcome">
          <div className="welcome-icon">🍜</div>
          <h2>Chào bạn!</h2>
          <p>Hãy hỏi tôi về quán ăn gần bạn. Ví dụ: "Tìm quán phở ngon gần đây"</p>
        </div>
      )}

      {turns.map((turn) => (
        <div key={turn.timestamp} className={`msg ${turn.role}`}>
          <div className="msg-bubble">
            {/* User message */}
            {turn.role === 'user' && <span>{turn.message}</span>}

            {/* Assistant message */}
            {turn.role === 'assistant' && (
              <>
                {turn.message && <span>{turn.message}</span>}

                {/* Tool call debug log */}
                {turn.toolCalls && turn.toolCalls.length > 0 && (
                  <div className="tool-log" title="Tool calls">
                    {turn.toolCalls.map((tc, i) => (
                      <div key={i} className="tool-log-entry">
                        <span className="tool-name">[{tc.tool}]</span>
                        {tc.error ? (
                          <span className="tool-error">Error: {tc.error}</span>
                        ) : (
                          <span className="tool-success">
                            OK — {tc.result?.substring(0, 120)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Rendered places */}
                {turn.places && turn.places.length > 0 && (
                  <div className="places-list">
                    {turn.places.map((place, idx) => (
                      <PlaceCard
                        key={place.place_id}
                        place={place}
                        rank={idx + 1}
                        onSelect={() => onSelectPlace(place)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="msg-time">{formatTime(turn.timestamp)}</div>
        </div>
      ))}

      {/* LLM typing indicator */}
      {isLoading && (
        <div className="msg assistant">
          <div className="typing" aria-label="Đang suy nghĩ...">
            <div className="typing-dot" />
            <div className="typing-dot" />
            <div className="typing-dot" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
