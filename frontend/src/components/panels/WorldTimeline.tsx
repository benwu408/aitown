import { useSimulationStore } from "../../stores/simulationStore";

const EVENT_TYPE_COLORS: Record<string, string> = {
  innovation: "border-pink-500 bg-pink-950/20",
  pattern: "border-amber-500 bg-amber-950/20",
  institution: "border-blue-500 bg-blue-950/20",
  conflict: "border-red-500 bg-red-950/20",
  structure: "border-teal-500 bg-teal-950/20",
  social: "border-green-500 bg-green-950/20",
  economic: "border-yellow-500 bg-yellow-950/20",
  norm: "border-purple-500 bg-purple-950/20",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  innovation: "Innovation",
  pattern: "Pattern",
  institution: "Institution",
  conflict: "Conflict",
  structure: "Structure",
  social: "Social",
  economic: "Economic",
  norm: "Norm",
};

interface Props {
  onClose: () => void;
}

export default function WorldTimeline({ onClose }: Props) {
  const timelineEvents = useSimulationStore((s) => s.timelineEvents);
  const innovations = useSimulationStore((s) => s.innovations);
  const patterns = useSimulationStore((s) => s.patterns);

  // Combine all events into a unified timeline
  type UnifiedEvent = {
    tick: number;
    day: number;
    type: string;
    title: string;
    description: string;
    agents: string[];
  };

  const allEvents: UnifiedEvent[] = [
    ...timelineEvents.map((e) => ({
      tick: e.tick,
      day: e.day,
      type: e.type,
      title: e.title,
      description: e.description,
      agents: e.agents_involved,
    })),
    ...innovations.map((i) => ({
      tick: i.invented_on,
      day: Math.floor(i.invented_on / 100),
      type: "innovation",
      title: `"${i.name}" discovered`,
      description: `${i.inventor} invented this. ${i.description}. Adoption: ${Math.round(i.adoption_rate * 100)}%`,
      agents: [i.inventor, ...i.adopters.slice(0, 3)],
    })),
    ...patterns.map((p) => ({
      tick: p.emerged_on,
      day: Math.floor(p.emerged_on / 100),
      type: p.type,
      title: p.name,
      description: p.description,
      agents: [] as string[],
    })),
  ].sort((a, b) => b.tick - a.tick);

  // Group by day
  const dayGroups = new Map<number, UnifiedEvent[]>();
  for (const event of allEvents) {
    const day = event.day;
    if (!dayGroups.has(day)) dayGroups.set(day, []);
    dayGroups.get(day)!.push(event);
  }
  const sortedDays = [...dayGroups.keys()].sort((a, b) => b - a);

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-gray-900 border border-gray-700/50 rounded-lg w-[560px] max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-800 shrink-0">
          <h2 className="text-amber-400 font-bold text-sm uppercase tracking-wider">
            World Timeline
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-lg leading-none"
          >
            x
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {allEvents.length === 0 ? (
            <p className="text-sm text-gray-500 italic text-center py-8">
              No significant world events yet. Events will appear as the simulation runs.
            </p>
          ) : (
            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-800" />

              {sortedDays.map((day) => (
                <div key={day} className="mb-4">
                  {/* Day marker */}
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-full bg-gray-800 border-2 border-amber-500/50 flex items-center justify-center text-[10px] text-amber-400 font-bold z-10">
                      D{day}
                    </div>
                    <span className="text-xs text-gray-500 uppercase">Day {day}</span>
                  </div>

                  {/* Events for this day */}
                  <div className="ml-12 space-y-2">
                    {dayGroups.get(day)!.map((event, i) => {
                      const colorClass = EVENT_TYPE_COLORS[event.type] || "border-gray-600 bg-gray-800/30";
                      const typeLabel = EVENT_TYPE_LABELS[event.type] || event.type;
                      return (
                        <div key={`${day}-${i}`} className={`rounded-lg border-l-2 p-3 ${colorClass}`}>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[9px] uppercase text-gray-500">{typeLabel}</span>
                          </div>
                          <div className="text-xs text-gray-200 font-medium">{event.title}</div>
                          <div className="text-[11px] text-gray-400 mt-0.5">{event.description}</div>
                          {event.agents.length > 0 && (
                            <div className="flex gap-1 mt-1">
                              {event.agents.slice(0, 4).map((name, j) => (
                                <span key={j} className="text-[9px] px-1.5 py-0.5 bg-gray-800/60 rounded text-gray-500">
                                  {name}
                                </span>
                              ))}
                              {event.agents.length > 4 && (
                                <span className="text-[9px] text-gray-600">+{event.agents.length - 4}</span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
