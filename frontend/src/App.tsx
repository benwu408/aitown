import { useState } from "react";
import GameCanvas from "./components/GameCanvas";
import TopBar from "./components/panels/TopBar";
import InspectorPanel from "./components/panels/InspectorPanel";
import LiveFeed from "./components/panels/LiveFeed";
import GodModePanel from "./components/panels/GodModePanel";
import Dashboard from "./components/panels/Dashboard";
import { useWebSocket } from "./hooks/useWebSocket";
import { useSimulationStore } from "./stores/simulationStore";

function App() {
  const { send } = useWebSocket();
  const [godMode, setGodMode] = useState(false);
  const [dashboard, setDashboard] = useState(false);

  const handleSpeedChange = (speed: number) => {
    useSimulationStore.getState().setSpeed(speed);
    send({ type: "set_speed", speed });
  };

  const handleInspect = (agentId: string) => {
    useSimulationStore.getState().selectAgent(agentId);
    send({ type: "inspect_agent", agentId });
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-950 text-gray-100">
      <TopBar onSpeedChange={handleSpeedChange} />

      <div className="flex flex-1 min-h-0">
        {/* Game Canvas */}
        <div className="flex-1 bg-gray-950 relative">
          <GameCanvas onAgentClick={handleInspect} />
          {/* Buttons */}
          <div className="absolute bottom-4 right-4 flex gap-2">
            <button
              onClick={() => setDashboard(true)}
              className="px-3 py-1.5 bg-blue-900/80 hover:bg-blue-800 text-blue-200 text-xs rounded-full border border-blue-700/50 backdrop-blur-sm"
            >
              Dashboard
            </button>
            <button
              onClick={() => setGodMode(true)}
              className="px-3 py-1.5 bg-red-900/80 hover:bg-red-800 text-red-200 text-xs rounded-full border border-red-700/50 backdrop-blur-sm"
            >
              God Mode
            </button>
          </div>
        </div>

        {/* Inspector Panel */}
        <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col shrink-0 overflow-hidden">
          <InspectorPanel onInspect={handleInspect} />
        </div>
      </div>

      {/* Live Feed */}
      <div className="h-36 bg-gray-900 border-t border-gray-800 shrink-0">
        <LiveFeed onAgentClick={handleInspect} />
      </div>

      {/* Overlays */}
      {godMode && (
        <GodModePanel onSend={send} onClose={() => setGodMode(false)} />
      )}
      {dashboard && (
        <Dashboard onSend={send} onClose={() => setDashboard(false)} />
      )}
    </div>
  );
}

export default App;
