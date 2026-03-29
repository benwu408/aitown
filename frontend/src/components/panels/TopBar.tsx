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
  onTimeline?: () => void;
  onInnovations?: () => void;
}

export default function TopBar({ onSpeedChange, onDashboard, onGodMode, onTimeline, onInnovations }: Props) {
  const time = useSimulationStore((s) => s.time);
  const tick = useSimulationStore((s) => s.tick);
  const speed = useSimulationStore((s) => s.speed);
  const connected = useSimulationStore((s) => s.connected);
  const agents = useSimulationStore((s) => s.agents);
  const worldObjects = useSimulationStore((s) => s.worldObjects);
  const innovations = useSimulationStore((s) => s.innovations);
  const patterns = useSimulationStore((s) => s.patterns);

  const agentCount = Object.keys(agents).length;
  const avgMood = agentCount > 0
    ? Object.values(agents).reduce((sum, a) => sum + a.state.mood, 0) / agentCount
    : 0;

  // Derived stats
  const foodCount = worldObjects.filter((o) => o.category === "food").length;
  const institutionCount = patterns.filter((p) => p.type === "social" || p.type === "norm").length;
  const innovationCount = innovations.length;

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
          {time ? `Day ${time.day} - ${time.time_string}` : "Loading..."}
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
        {foodCount > 0 && (
          <span className="text-green-400">\uD83C\uDF3E {foodCount}</span>
        )}
        {institutionCount > 0 && (
          <span className="text-blue-400">\uD83C\uDFDB {institutionCount}</span>
        )}
        {innovationCount > 0 && (
          <span className="text-pink-400">\uD83D\uDCA1 {innovationCount}</span>
        )}
      </div>

      {/* Right side */}
      <div className="ml-auto flex items-center gap-2">
        {onTimeline && (
          <button
            onClick={onTimeline}
            className="px-2.5 py-1 text-[10px] bg-amber-900/40 hover:bg-amber-800/60 text-amber-300 rounded border border-amber-800/30 transition-colors"
          >
            Timeline
          </button>
        )}
        {onInnovations && (
          <button
            onClick={onInnovations}
            className="px-2.5 py-1 text-[10px] bg-pink-900/40 hover:bg-pink-800/60 text-pink-300 rounded border border-pink-800/30 transition-colors"
          >
            Innovations
          </button>
        )}
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
