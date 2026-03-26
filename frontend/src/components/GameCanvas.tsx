import { useEffect, useRef, useCallback } from "react";
import { Application, Graphics, Container, Text, TextStyle } from "pixi.js";
import { useWorldStore } from "../stores/worldStore";
import { useSimulationStore } from "../stores/simulationStore";
import { TILE_WIDTH, TILE_HEIGHT, gridToScreen } from "../utils/isometric";
import { TILE_COLORS, BUILDING_COLORS, AGENT_COLORS, ACTION_ICONS } from "../utils/formatting";
import { AgentData } from "../types/agent";

interface Props {
  onAgentClick?: (agentId: string) => void;
}

export default function GameCanvas({ onAgentClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const worldContainerRef = useRef<Container | null>(null);
  const agentLayerRef = useRef<Container | null>(null);
  const overlayRef = useRef<Graphics | null>(null);
  const agentSpritesRef = useRef<Map<string, Container>>(new Map());
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0, moved: false });
  const unsubRef = useRef<(() => void) | null>(null);

  const map = useWorldStore((s) => s.map);

  // Update agent visuals on each tick
  const agents = useSimulationStore((s) => s.agents);
  const selectedAgentId = useSimulationStore((s) => s.selectedAgentId);

  const updateAgents = useCallback(
    (agentMap: Record<string, AgentData>) => {
      const layer = agentLayerRef.current;
      if (!layer) return;

      const sprites = agentSpritesRef.current;

      for (const [id, agent] of Object.entries(agentMap)) {
        let sprite = sprites.get(id);

        if (!sprite) {
          sprite = createAgentSprite(agent);
          layer.addChild(sprite);
          sprites.set(id, sprite);
        }

        // Update position
        const { x, y } = gridToScreen(agent.position[0], agent.position[1]);
        sprite.x = x;
        sprite.y = y - 12; // Offset up to stand on tile
        sprite.zIndex = agent.position[0] + agent.position[1] + 100;

        // Update label & icon
        updateAgentSprite(sprite, agent, id === selectedAgentId);
      }
    },
    [selectedAgentId]
  );

  // Re-render agents when they change
  useEffect(() => {
    updateAgents(agents);
  }, [agents, updateAgents]);

  useEffect(() => {
    if (!containerRef.current) return;

    const app = new Application();
    let mounted = true;

    const init = async () => {
      await app.init({
        background: 0x1a1a2e,
        resizeTo: containerRef.current!,
        antialias: false,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      });

      if (!mounted) {
        app.destroy(true);
        return;
      }

      containerRef.current!.appendChild(app.canvas as HTMLCanvasElement);
      appRef.current = app;

      const worldContainer = new Container();
      app.stage.addChild(worldContainer);
      worldContainerRef.current = worldContainer;

      // Center the map
      const centerTile = gridToScreen(map.width / 2, map.height / 2);
      worldContainer.x = app.screen.width / 2 - centerTile.x;
      worldContainer.y = app.screen.height / 4 - centerTile.y;

      renderMap(worldContainer);
      renderBuildings(worldContainer);

      // Agent layer on top
      const agentLayer = new Container();
      agentLayer.sortableChildren = true;
      worldContainer.addChild(agentLayer);
      agentLayerRef.current = agentLayer;

      // Day/night overlay (covers entire viewport, rendered on stage not world)
      const overlay = new Graphics();
      overlay.rect(0, 0, app.screen.width * 2, app.screen.height * 2);
      overlay.fill({ color: 0x000033, alpha: 0 });
      app.stage.addChild(overlay);
      overlayRef.current = overlay;

      // Day/night cycle ticker
      unsubRef.current = useSimulationStore.subscribe((state) => {
        if (!state.time || !overlayRef.current) return;
        const hour = state.time.hour;
        const g = overlayRef.current;
        g.clear();
        g.rect(-2000, -2000, 6000, 6000);

        let alpha = 0;
        let tintColor = 0x000033;

        if (hour < 5) {
          // Night
          alpha = 0.45;
          tintColor = 0x000044;
        } else if (hour < 7) {
          // Dawn
          alpha = 0.45 - ((hour - 5) / 2) * 0.4;
          tintColor = 0x442200;
        } else if (hour < 17) {
          // Day
          alpha = 0;
        } else if (hour < 20) {
          // Dusk
          alpha = ((hour - 17) / 3) * 0.35;
          tintColor = 0x331100;
        } else {
          // Night
          alpha = 0.35 + ((hour - 20) / 4) * 0.1;
          tintColor = 0x000044;
        }

        // Weather overlay
        if (state.time.weather === "rain" || state.time.weather === "storm") {
          alpha = Math.min(0.55, alpha + 0.15);
          tintColor = 0x222233;
        } else if (state.time.weather === "cloudy") {
          alpha = Math.min(0.4, alpha + 0.08);
        }

        g.fill({ color: tintColor, alpha });
      });

      // Mouse drag for panning
      const canvas = app.canvas as HTMLCanvasElement;

      canvas.addEventListener("pointerdown", (e: PointerEvent) => {
        dragRef.current = { dragging: true, lastX: e.clientX, lastY: e.clientY, moved: false };
      });

      window.addEventListener("pointerup", (e: PointerEvent) => {
        // Only handle agent clicks when the click target is the canvas
        if (
          !dragRef.current.moved &&
          worldContainerRef.current &&
          (e.target === canvas || canvas.contains(e.target as Node))
        ) {
          const rect = canvas.getBoundingClientRect();
          const mouseX = e.clientX - rect.left;
          const mouseY = e.clientY - rect.top;
          const wc = worldContainerRef.current;
          const worldX = (mouseX - wc.x) / wc.scale.x;
          const worldY = (mouseY - wc.y) / wc.scale.y;

          const currentAgents = useSimulationStore.getState().agents;
          let closestId: string | null = null;
          let closestDist = 20;

          for (const [id, agent] of Object.entries(currentAgents)) {
            const { x, y } = gridToScreen(agent.position[0], agent.position[1]);
            const dx = worldX - x;
            const dy = worldY - (y - 12);
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < closestDist) {
              closestDist = dist;
              closestId = id;
            }
          }

          if (closestId && onAgentClick) {
            onAgentClick(closestId);
          }
        }
        dragRef.current.dragging = false;
      });

      window.addEventListener("pointermove", (e: PointerEvent) => {
        if (!dragRef.current.dragging || !worldContainerRef.current) return;
        const dx = e.clientX - dragRef.current.lastX;
        const dy = e.clientY - dragRef.current.lastY;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
          dragRef.current.moved = true;
        }
        worldContainerRef.current.x += dx;
        worldContainerRef.current.y += dy;
        dragRef.current.lastX = e.clientX;
        dragRef.current.lastY = e.clientY;
      });

      // Zoom
      containerRef.current!.addEventListener("wheel", (e: WheelEvent) => {
        e.preventDefault();
        if (!worldContainerRef.current) return;
        const wc = worldContainerRef.current;
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
        const newScale = Math.max(0.3, Math.min(3, wc.scale.x * zoomFactor));

        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const worldX = (mouseX - wc.x) / wc.scale.x;
        const worldY = (mouseY - wc.y) / wc.scale.y;

        wc.scale.set(newScale);
        wc.x = mouseX - worldX * newScale;
        wc.y = mouseY - worldY * newScale;
      });
    };

    init();

    return () => {
      mounted = false;
      agentSpritesRef.current.clear();
      unsubRef.current?.();
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
    };
  }, []);

  function renderMap(container: Container) {
    const tileLayer = new Container();
    container.addChild(tileLayer);

    for (let row = 0; row < map.height; row++) {
      for (let col = 0; col < map.width; col++) {
        const tile = map.tiles[row][col];
        const { x, y } = gridToScreen(col, row);

        const g = new Graphics();
        const color = TILE_COLORS[tile.type] || TILE_COLORS.grass;

        g.poly([
          { x: x, y: y - TILE_HEIGHT / 2 },
          { x: x + TILE_WIDTH / 2, y: y },
          { x: x, y: y + TILE_HEIGHT / 2 },
          { x: x - TILE_WIDTH / 2, y: y },
        ]);
        g.fill(color);
        g.stroke({ width: 0.5, color: 0x000000, alpha: 0.1 });

        if (tile.decoration === "tree") {
          g.poly([
            { x: x, y: y - 20 },
            { x: x + 8, y: y },
            { x: x - 8, y: y },
          ]);
          g.fill(0x2d5a1e);
          g.rect(x - 2, y, 4, 6);
          g.fill(0x5c3a1e);
        }

        if (tile.decoration === "flower") {
          for (const [dx, dy] of [
            [-4, -2],
            [3, 1],
            [0, -5],
            [5, -1],
          ]) {
            g.circle(x + dx, y + dy, 2);
            g.fill(
              [0xff6b9d, 0xffd93d, 0xff8a5c, 0xc084fc][
                Math.floor(Math.random() * 4)
              ]
            );
          }
        }

        tileLayer.addChild(g);
      }
    }
  }

  function renderBuildings(container: Container) {
    const buildingLayer = new Container();
    buildingLayer.sortableChildren = true;
    container.addChild(buildingLayer);

    for (const b of map.buildings) {
      const group = new Container();
      group.zIndex = b.col + b.row + b.width + b.height;
      buildingLayer.addChild(group);

      const color = BUILDING_COLORS[b.type] || 0x888888;

      const g = new Graphics();
      const tl = gridToScreen(b.col, b.row);
      const tr = gridToScreen(b.col + b.width, b.row);
      const br = gridToScreen(b.col + b.width, b.row + b.height);
      const bl = gridToScreen(b.col, b.row + b.height);

      const bh =
        b.type.startsWith("house")
          ? 18
          : b.type === "church"
            ? 30
            : b.type === "pond" || b.type === "park" || b.type === "farm"
              ? 0
              : 22;

      if (bh > 0) {
        // Front face
        g.poly([
          { x: bl.x, y: bl.y - bh },
          { x: br.x, y: br.y - bh },
          { x: br.x, y: br.y },
          { x: bl.x, y: bl.y },
        ]);
        g.fill(darkenColor(color, 0.7));

        // Side face
        g.poly([
          { x: br.x, y: br.y - bh },
          { x: tr.x, y: tr.y - bh },
          { x: tr.x, y: tr.y },
          { x: br.x, y: br.y },
        ]);
        g.fill(darkenColor(color, 0.85));

        // Roof
        g.poly([
          { x: tl.x, y: tl.y - bh },
          { x: tr.x, y: tr.y - bh },
          { x: br.x, y: br.y - bh },
          { x: bl.x, y: bl.y - bh },
        ]);
        g.fill(color);

        // Windows
        if (!["pond", "park", "farm"].includes(b.type)) {
          const midX = (bl.x + br.x) / 2;
          const midY = (bl.y + br.y) / 2;
          for (let i = -1; i <= 1; i += 2) {
            g.rect(midX + i * 8 - 3, midY - bh / 2 - 3, 6, 6);
            g.fill(0xfff4c2);
          }
        }
      } else {
        // Flat features (pond, park, farm) — just the footprint
        g.poly([
          { x: tl.x, y: tl.y },
          { x: tr.x, y: tr.y },
          { x: br.x, y: br.y },
          { x: bl.x, y: bl.y },
        ]);
        g.fill(color);
        g.stroke({ width: 1, color: darkenColor(color, 0.7) });
      }

      group.addChild(g);

      // Label
      const label = new Text({
        text: b.label,
        style: new TextStyle({
          fontFamily: "monospace",
          fontSize: 9,
          fill: 0xffffff,
          dropShadow: {
            alpha: 0.8,
            blur: 2,
            color: 0x000000,
            distance: 1,
          },
        }),
      });
      const center = gridToScreen(b.col + b.width / 2, b.row + b.height / 2);
      label.x = center.x - label.width / 2;
      label.y = center.y - Math.max(bh, 5) - 14;
      group.addChild(label);
    }
  }

  return <div ref={containerRef} className="w-full h-full cursor-grab" />;
}

function createAgentSprite(agent: AgentData): Container {
  const container = new Container();

  // Body circle
  const body = new Graphics();
  const color = AGENT_COLORS[agent.colorIndex % AGENT_COLORS.length];
  body.circle(0, 0, 6);
  body.fill(color);
  body.stroke({ width: 1.5, color: 0xffffff, alpha: 0.6 });
  body.label = "body";
  container.addChild(body);

  // Name label
  const nameText = new Text({
    text: agent.name.split(" ")[0],
    style: new TextStyle({
      fontFamily: "monospace",
      fontSize: 7,
      fill: 0xffffff,
      dropShadow: {
        alpha: 0.9,
        blur: 2,
        color: 0x000000,
        distance: 0,
      },
    }),
  });
  nameText.x = -nameText.width / 2;
  nameText.y = -18;
  nameText.label = "name";
  container.addChild(nameText);

  // Activity icon
  const iconText = new Text({
    text: "",
    style: new TextStyle({
      fontSize: 10,
    }),
  });
  iconText.x = 8;
  iconText.y = -16;
  iconText.label = "icon";
  container.addChild(iconText);

  // Selection ring (hidden by default)
  const ring = new Graphics();
  ring.circle(0, 0, 10);
  ring.stroke({ width: 2, color: 0xffd700, alpha: 0.8 });
  ring.visible = false;
  ring.label = "ring";
  container.addChild(ring);

  return container;
}

function updateAgentSprite(
  sprite: Container,
  agent: AgentData,
  selected: boolean
) {
  // Update icon
  const iconChild = sprite.children.find((c) => c.label === "icon") as Text;
  if (iconChild) {
    const icon = ACTION_ICONS[agent.currentAction] || "";
    if (iconChild.text !== icon) {
      iconChild.text = icon;
    }
  }

  // Update selection ring
  const ring = sprite.children.find((c) => c.label === "ring");
  if (ring) {
    ring.visible = selected;
  }
}

function darkenColor(color: number, factor: number): number {
  const r = Math.floor(((color >> 16) & 0xff) * factor);
  const g = Math.floor(((color >> 8) & 0xff) * factor);
  const b = Math.floor((color & 0xff) * factor);
  return (r << 16) | (g << 8) | b;
}
