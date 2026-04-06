import { useState } from "react";
import type { ReasoningStep, ToolResultEntry } from "../types";

interface Props {
  steps: ReasoningStep[];
  toolResults: ToolResultEntry[];
}

const STEP_ICONS: Record<string, string> = {
  think: "🤖",
  search_google_places: "🔍",
  calculate_scores: "📊",
  get_user_location: "📍",
  save_user_selection: "💾",
  get_user_preference: "❤️",
};

function getIcon(tool: string | null): string {
  if (!tool) return "🤖";
  return STEP_ICONS[tool] || "⚙️";
}

export default function ReasoningPanel({ steps, toolResults }: Props) {
  const [open, setOpen] = useState(true);

  if (!steps.length && !toolResults.length) return null;

  const toolResultMap = new Map(toolResults.map((tr) => [tr.tool, tr]));

  return (
    <div className="reasoning-panel">
      <button className="reasoning-toggle" onClick={() => setOpen((o) => !o)}>
        <span className="reasoning-toggle-icon">{open ? "▼" : "▶"}</span>
        Reasoning
        <span className="reasoning-count">{steps.length} steps</span>
      </button>
      {open && (
        <ol className="reasoning-steps">
          {steps.map((s, i) => {
            const tr = s.tool ? toolResultMap.get(s.tool) : null;
            return (
              <li key={i} className={`reasoning-step${s.tool ? " reasoning-step--tool" : ""}`}>
                <span className="reasoning-step-icon">{getIcon(s.tool)}</span>
                <span className="reasoning-step-num">{s.step}.</span>
                <span className="reasoning-step-text">{s.text}</span>
                {tr && (
                  <span className={`reasoning-step-result ${tr.error ? "error" : "success"}`}>
                    {tr.error
                      ? `❌ ${tr.error}`
                      : typeof tr.result === "object" && tr.result !== null
                        ? `✅ ${JSON.stringify(tr.result)}`
                        : ""}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}