import { useState } from "react";
import GameCanvas from "./components/GameCanvas";
import TopBar from "./components/panels/TopBar";
import InspectorPanel from "./components/panels/InspectorPanel";
import LiveFeed from "./components/panels/LiveFeed";
import GodModePanel from "./components/panels/GodModePanel";
import Dashboard from "./components/panels/Dashboard";
import StoryHighlights from "./components/panels/StoryHighlights";
import WorldTimeline from "./components/panels/WorldTimeline";
import InnovationTree from "./components/panels/InnovationTree";
import { useWebSocket } from "./hooks/useWebSocket";
import { useSimulationStore } from "./stores/simulationStore";

function App() {
  const { send } = useWebSocket();
  const [godMode, setGodMode] = useState(false);
  const [dashboard, setDashboard] = useState(false);
  const [timeline, setTimeline] = useState(false);
  const [innovations, setInnovations] = useState(false);
  const autobiography = useSimulationStore((s) => s.autobiography);
  const selectedAgentId = useSimulationStore((s) => s.selectedAgentId);

  const handleSpeedChange = (speed: number) => {
    useSimulationStore.getState().setSpeed(speed);
    send({ type: "set_speed", speed });
  };

  const handleInspect = (agentId: string) => {
    useSimulationStore.getState().selectAgent(agentId);
    useSimulationStore.getState().setFollowAgent(agentId);
    send({ type: "inspect_agent", agentId });
  };

  const handleViewStory = () => {
    if (selectedAgentId) {
      send({ type: "request_autobiography", agentId: selectedAgentId });
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-950 text-gray-100">
      <TopBar
        onSpeedChange={handleSpeedChange}
        onDashboard={() => setDashboard(true)}
        onGodMode={() => setGodMode(true)}
        onTimeline={() => setTimeline(true)}
        onInnovations={() => setInnovations(true)}
      />

      <div className="flex flex-1 min-h-0">
        {/* Game Canvas */}
        <div className="flex-1 bg-gray-950 relative overflow-hidden">
          <GameCanvas onAgentClick={handleInspect} />
          <StoryHighlights onAgentClick={handleInspect} />
        </div>

        {/* Inspector Panel */}
        <div className="w-80 bg-gray-900/95 border-l border-gray-800 flex flex-col shrink-0 overflow-hidden">
          {selectedAgentId && (
            <div className="flex gap-1.5 px-3 pt-2 pb-1">
              <button
                onClick={handleViewStory}
                className="px-2.5 py-1 text-[10px] bg-purple-900/40 hover:bg-purple-800/60 text-purple-300 rounded border border-purple-800/30 transition-colors"
              >
                View Story
              </button>
            </div>
          )}
          <div className="flex-1 min-h-0 flex flex-col">
            <InspectorPanel onInspect={handleInspect} />
          </div>
        </div>
      </div>

      {/* Live Feed */}
      <div className="h-32 bg-gray-900/95 border-t border-gray-800 shrink-0">
        <LiveFeed onAgentClick={handleInspect} />
      </div>

      {/* Overlays */}
      {godMode && <GodModePanel onSend={send} onClose={() => setGodMode(false)} />}
      {dashboard && <Dashboard onSend={send} onClose={() => setDashboard(false)} />}
      {timeline && <WorldTimeline onClose={() => setTimeline(false)} />}
      {innovations && <InnovationTree onClose={() => setInnovations(false)} />}

      {/* Autobiography Modal */}
      {autobiography && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => useSimulationStore.getState().setAutobiography(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700/50 rounded-xl max-w-lg p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-amber-400 font-bold text-sm">
                {(() => {
                  const agents = useSimulationStore.getState().agents;
                  return agents[autobiography.agentId]?.name || "Agent";
                })()}'s Story
              </h2>
              <button
                onClick={() => navigator.clipboard.writeText(autobiography.text)}
                className="text-[10px] text-gray-500 hover:text-gray-300 px-2 py-0.5 rounded bg-gray-800 transition-colors"
              >
                Copy
              </button>
            </div>
            <p className="text-gray-300 text-sm leading-relaxed italic">
              "{autobiography.text}"
            </p>
            <button
              onClick={() => useSimulationStore.getState().setAutobiography(null)}
              className="mt-4 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
