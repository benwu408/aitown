import { useSimulationStore } from "../../stores/simulationStore";

const WEATHER_ICONS: Record<string, string> = {
  clear: "\u2600\uFE0F",
  cloudy: "\u2601\uFE0F",
  rain: "\uD83C\uDF27\uFE0F",
  storm: "\u26C8\uFE0F",
};

const SPEED_OPTIONS = [0, 1, 2, 5, 10];

interface Props {
  onSpeedChange: (speed: number) => void;
}

export default function TopBar({ onSpeedChange }: Props) {
  const time = useSimulationStore((s) => s.time);
  const tick = useSimulationStore((s) => s.tick);
  const speed = useSimulationStore((s) => s.speed);
  const connected = useSimulationStore((s) => s.connected);
  const agents = useSimulationStore((s) => s.agents);

  const agentCount = Object.keys(agents).length;
  const avgMood = agentCount > 0
    ? Object.values(agents).reduce((sum, a) => sum + a.state.mood, 0) / agentCount
    : 0;

  return (
    <div className="h-12 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-6 shrink-0">
      <span className="text-lg font-bold text-amber-400">Agentica</span>

      <span className="text-sm text-gray-300">
        {time ? `Day ${time.day} \u2014 ${time.time_string}` : "Loading..."}
      </span>

      <span className="text-sm">
        {time ? WEATHER_ICONS[time.weather] || "" : ""}
      </span>

      {/* Speed controls */}
      <div className="flex items-center gap-1">
        {SPEED_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            className={`px-2 py-0.5 text-xs rounded transition-colors ${
              speed === s
                ? "bg-amber-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {s === 0 ? "\u23F8" : `${s}x`}
          </button>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-4">
        {agentCount > 0 && (
          <>
            <span className="text-xs text-gray-400">
              \uD83D\uDC65 {agentCount}
            </span>
            <span className="text-xs text-gray-400">
              \uD83D\uDE0A {Math.round(avgMood * 100)}%
            </span>
          </>
        )}
        <span className="text-xs text-gray-500">Tick: {tick}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            connected
              ? "bg-green-900/50 text-green-400"
              : "bg-red-900/50 text-red-400"
          }`}
        >
          {connected ? "Live" : "Offline"}
        </span>
      </div>
    </div>
  );
}
