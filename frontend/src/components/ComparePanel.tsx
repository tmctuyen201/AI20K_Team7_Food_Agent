import { useState } from "react";
import type { CompareResult, ScoredPlace } from "../types";
import PlaceCard from "./PlaceCard";

interface Props {
  result: CompareResult;
  onSelectPlace: (place: ScoredPlace) => void;
  onSelectParsedPlace: (parsed: { name: string; rating: number; distance_km: number; description: string }) => void;
  onClose: () => void;
}

const VERSION_META = {
  v1: { label: "ReAct", color: "#6366f1", desc: "Loop với tools" },
  v2: { label: "LangGraph", color: "#10b981", desc: "Linear graph" },
  "no-tools": { label: "LLM only", color: "#f59e0b", desc: "Không tool" },
} as const;

function VersionPanel({
  version,
  data,
  onSelectPlace,
  onSelectParsedPlace,
}: {
  version: "v1" | "v2" | "no-tools";
  data: CompareResult["v1"];
  onSelectPlace: (p: ScoredPlace) => void;
  onSelectParsedPlace: (p: { name: string; rating: number; distance_km: number; description: string }) => void;
}) {
  const [showSteps, setShowSteps] = useState(false);
  const meta = VERSION_META[version];

  return (
    <div className="compare-version">
      {/* Header */}
      <div className="compare-version-header" style={{ background: meta.color }}>
        <strong>{meta.label}</strong>
        <span>{meta.desc}</span>
      </div>

      {/* Body */}
      <div className="compare-version-body">
        {/* Text response */}
        <div className="compare-text-block">
          <p className="compare-text">{data.text || "(không có phản hồi)"}</p>
        </div>

        {/* Places */}
        {data.places.length > 0 && (
          <div className="compare-places">
            <div className="compare-section-title">🏆 Top Places</div>
            {data.places.slice(0, 3).map((p, i) => (
              <PlaceCard
                key={p.place_id}
                place={p}
                rank={i + 1}
                onSelect={() => onSelectPlace(p)}
              />
            ))}
          </div>
        )}

        {/* Reasoning steps */}
        {data.reasoning_steps.length > 0 && (
          <div className="compare-reasoning">
            <button
              className="compare-reasoning-toggle"
              onClick={() => setShowSteps((s) => !s)}
            >
              <span>🧠 Reasoning ({data.reasoning_steps.length} steps)</span>
              <span className="toggle-arrow">{showSteps ? "▲" : "▼"}</span>
            </button>
            {showSteps && (
              <div className="compare-reasoning-body">
                {data.reasoning_steps.map((s, i) => (
                  <div key={i} className="compare-reasoning-item">
                    <span className="compare-reasoning-num">{s.step}</span>
                    <span className="compare-reasoning-text">
                      {s.tool ? (
                        <>
                          <span className="reasoning-tool-badge">{s.tool}</span>
                          {s.text}
                        </>
                      ) : s.text}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ComparePanel({ result, onSelectPlace, onSelectParsedPlace, onClose }: Props) {
  return (
    <div className="compare-overlay">
      <div className="compare-modal">
        {/* Modal header */}
        <div className="compare-modal-header">
          <div className="compare-modal-title">
            <span>⚖️</span>
            <span>So sánh 3 phiên bản Agent</span>
          </div>
          <button className="compare-close" onClick={onClose} title="Đóng">
            ✕
          </button>
        </div>

        {/* 3-column comparison */}
        <div className="compare-grid">
          <VersionPanel
            version="v1"
            data={result.v1}
            onSelectPlace={onSelectPlace}
            onSelectParsedPlace={onSelectParsedPlace}
          />
          <VersionPanel
            version="v2"
            data={result.v2}
            onSelectPlace={onSelectPlace}
            onSelectParsedPlace={onSelectParsedPlace}
          />
          <VersionPanel
            version="no-tools"
            data={result["no-tools"]}
            onSelectPlace={onSelectPlace}
            onSelectParsedPlace={onSelectParsedPlace}
          />
        </div>

        {/* Footer hint */}
        <div className="compare-modal-footer">
          Click vào quán ăn để chọn • Reasoning steps để xem chi tiết AI suy nghĩ gì
        </div>
      </div>
    </div>
  );
}