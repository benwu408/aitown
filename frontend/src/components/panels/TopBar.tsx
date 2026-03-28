import { useSimulationStore } from "../../stores/simulationStore";

const WEATHER_ICONS: Record<string, string> = {
  clear: "\u2600\uFE0F",
  cloudy: "\u2601\uFE0F",
  rain: "\uD83C\uDF27\uFE0F",
  storm: "\u26C8\uFE0F",
};

const SEASON_ICONS: Record<string, string> = {
  spring: "\uD83C\uDF38",
  summer: "\u2600\uFE0F",
  autumn: "\uD83C\uDF42",
  winter: "\u2744\uFE0F",
};

const SPEED_OPTIONS = [0, 1, 2, 5, 10];

interface Props {
  onSpeedChange: (speed: number) => void;
  onDashboard: () => void;
  onGodMode: () => void;
}

export default function TopBar({ onSpeedChange, onDashboard, onGodMode }: Props) {
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
    <div className="h-11 bg-gray-900/95 border-b border-gray-800 flex items-center px-4 gap-4 shrink-0 backdrop-blur-sm">
      {/* Brand */}
      <span className="text-base font-bold text-amber-400 tracking-tight">Polis</span>

      {/* Divider */}
      <div className="w-px h-5 bg-gray-700" />

      {/* Time & Weather */}
      <div className="flex items-center gap-2">
        {time && <span className="text-sm">{SEASON_ICONS[time.season] || ""}</span>}
        <span className="text-xs text-gray-300 font-medium">
          {time ? `Day ${time.day} \u2014 ${time.time_string}` : "Loading..."}
        </span>
        <span className="text-sm">{time ? WEATHER_ICONS[time.weather] || "" : ""}</span>
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-gray-700" />

      {/* Speed controls */}
      <div className="flex items-center gap-0.5">
        {SPEED_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            className={`px-1.5 py-0.5 text-[10px] rounded transition-colors ${
              speed === s
                ? "bg-amber-600 text-white"
                : "bg-gray-800/60 text-gray-500 hover:bg-gray-700 hover:text-gray-300"
            }`}
          >
            {s === 0 ? "\u23F8" : `${s}x`}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-3 text-[10px] text-gray-500">
        {agentCount > 0 && (
          <>
            <span>\uD83D\uDC65 {agentCount}</span>
            <span className={avgMood > 0.6 ? "text-green-500" : avgMood > 0.3 ? "text-yellow-500" : "text-red-500"}>
              Mood {Math.round(avgMood * 100)}%
            </span>
          </>
        )}
      </div>

      {/* Right side */}
      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={onDashboard}
          className="px-2.5 py-1 text-[10px] bg-blue-900/40 hover:bg-blue-800/60 text-blue-300 rounded border border-blue-800/30 transition-colors"
        >
          Dashboard
        </button>
        <button
          onClick={onGodMode}
          className="px-2.5 py-1 text-[10px] bg-red-900/40 hover:bg-red-800/60 text-red-300 rounded border border-red-800/30 transition-colors"
        >
          God Mode
        </button>

        <div className="w-px h-5 bg-gray-700" />

        <span
          className={`text-[10px] px-1.5 py-0.5 rounded ${
            connected
              ? "bg-green-900/30 text-green-400"
              : "bg-red-900/30 text-red-400"
          }`}
        >
          {connected ? "Live" : "Offline"}
        </span>
      </div>
    </div>
  );
}
