import { create } from "zustand";
import { WorldMap } from "../types/world";
import { generateWorldMap } from "../data/townMap";

interface WorldState {
  map: WorldMap;
  camera: { x: number; y: number; zoom: number };
  setCamera: (camera: Partial<WorldState["camera"]>) => void;
}

export const useWorldStore = create<WorldState>((set) => ({
  map: generateWorldMap(),
  camera: { x: 0, y: 0, zoom: 1.0 },
  setCamera: (camera) =>
    set((state) => ({ camera: { ...state.camera, ...camera } })),
}));
