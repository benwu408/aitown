import { useState } from "react";
import { useSimulationStore } from "../../stores/simulationStore";

const WORLD_EVENTS = [
  { type: "natural_disaster", label: "Natural Disaster", desc: "Earthquake, flood, or fire strikes the settlement" },
  { type: "resource_discovery", label: "Resource Discovery", desc: "A new resource deposit is found nearby" },
  { type: "stranger_arrives", label: "Stranger Arrives", desc: "A mysterious visitor with news from afar" },
  { type: "weather_change", label: "Weather Change", desc: "Sudden shift in weather conditions" },
  { type: "drought", label: "Drought", desc: "Water dries up, farm output drops" },
  { type: "festival", label: "Festival", desc: "Agents gather to celebrate" },
  { type: "harsh_winter", label: "Harsh Winter", desc: "Food and fuel demand increases" },
  { type: "building_fire", label: "Building Fire", desc: "A random building catches fire" },
  { type: "illness", label: "Plague", desc: "Sickness spreads through the population" },
  { type: "bountiful_harvest", label: "Bountiful Harvest", desc: "Extra food and resources appear" },
];

interface Props {
  onSend: (msg: object) => void;
  onClose: () => void;
}

export default function GodModePanel({ onSend, onClose }: Props) {
  const agents = useSimulationStore((s) => s.agents);
  const [whisperAgent, setWhisperAgent] = useState("");
  const [whisperText, setWhisperText] = useState("");
  const [freeCommand, setFreeCommand] = useState("");
  const [secretAgent, setSecretAgent] = useState("");
  const [secretText, setSecretText] = useState("");

  const agentList = Object.values(agents);

  const injectEvent = (eventType: string, params: Record<string, string> = {}) => {
    onSend({
      type: "god_command",
      command: "inject_event",
      params: { event_type: eventType, params },
    });
  };

  const sendWhisper = () => {
    if (!whisperAgent || !whisperText) return;
    onSend({
      type: "god_command",
      command: "whisper",
      params: { agent_id: whisperAgent, thought: whisperText },
    });
    setWhisperText("");
  };

  const sendFreeCommand = () => {
    if (!freeCommand.trim()) return;
    onSend({
      type: "god_command",
      command: "free_text",
      params: { text: freeCommand.trim() },
    });
    setFreeCommand("");
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-gray-900 border border-red-900/50 rounded-lg w-[520px] max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h2 className="text-red-400 font-bold text-sm uppercase tracking-wider">
            God Mode
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-lg leading-none"
          >
            x
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Free-text command */}
          <div>
            <h3 className="text-xs text-gray-400 uppercase mb-2">
              Free Command
            </h3>
            <p className="text-[10px] text-gray-600 mb-2">
              Type any command in natural language. The backend action system will interpret it.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={freeCommand}
                onChange={(e) => setFreeCommand(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendFreeCommand()}
                placeholder="e.g. 'spawn a wolf at the farm' or 'create a gold deposit near the river'"
                className="flex-1 bg-gray-800 text-gray-200 text-xs rounded px-2 py-1.5 border border-gray-700 placeholder-gray-600"
              />
              <button
                onClick={sendFreeCommand}
                className="px-3 py-1 bg-red-900 hover:bg-red-800 text-red-200 text-xs rounded whitespace-nowrap"
              >
                Execute
              </button>
            </div>
          </div>

          {/* World Events */}
          <div>
            <h3 className="text-xs text-gray-400 uppercase mb-2">
              Inject World Events
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {WORLD_EVENTS.map((e) => (
                <button
                  key={e.type}
                  onClick={() => injectEvent(e.type)}
                  className="p-2 bg-gray-800 hover:bg-gray-700 rounded text-left transition-colors"
                >
                  <div className="text-xs text-gray-200">{e.label}</div>
                  <div className="text-[10px] text-gray-500">{e.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Reveal a Secret */}
          <div>
            <h3 className="text-xs text-gray-400 uppercase mb-2">
              Reveal a Secret
            </h3>
            <select
              value={secretAgent}
              onChange={(e) => setSecretAgent(e.target.value)}
              className="w-full bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700 mb-2"
            >
              <option value="">Select agent...</option>
              {agentList.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <input
                type="text"
                value={secretText}
                onChange={(e) => setSecretText(e.target.value)}
                placeholder="has been stealing from the treasury..."
                className="flex-1 bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700"
              />
              <button
                onClick={() => {
                  if (secretAgent && secretText) {
                    injectEvent("secret_revealed", {
                      agent_id: secretAgent,
                      secret: secretText,
                    });
                    setSecretText("");
                  }
                }}
                className="px-3 py-1 bg-pink-900 hover:bg-pink-800 text-pink-200 text-xs rounded"
              >
                Reveal
              </button>
            </div>
          </div>

          {/* Whisper to Agent */}
          <div>
            <h3 className="text-xs text-gray-400 uppercase mb-2">
              Whisper to Agent
            </h3>
            <select
              value={whisperAgent}
              onChange={(e) => setWhisperAgent(e.target.value)}
              className="w-full bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700 mb-2"
            >
              <option value="">Select agent...</option>
              {agentList.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <input
                type="text"
                value={whisperText}
                onChange={(e) => setWhisperText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendWhisper()}
                placeholder="Plant a thought in their mind..."
                className="flex-1 bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700"
              />
              <button
                onClick={sendWhisper}
                className="px-3 py-1 bg-purple-900 hover:bg-purple-800 text-purple-200 text-xs rounded"
              >
                Whisper
              </button>
            </div>
          </div>

          {/* World Edit */}
          <div>
            <h3 className="text-xs text-gray-400 uppercase mb-2">
              Build Structure
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {["house", "bakery", "workshop", "tavern", "clinic", "general_store", "barn", "meeting_hall", "common_house"].map((type) => (
                <button
                  key={type}
                  onClick={() => {
                    onSend({
                      type: "god_command",
                      command: "world_edit",
                      params: {
                        action: "build",
                        col: 0, row: 0,
                        width: 2, height: 2,
                        structure_type: type,
                        label: `New ${type.charAt(0).toUpperCase() + type.slice(1)}`,
                        auto_place: true,
                      },
                    });
                  }}
                  className="p-1.5 bg-gray-800 hover:bg-gray-700 rounded text-[10px] text-gray-300 capitalize"
                >
                  {type.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
