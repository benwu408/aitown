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
  const buildingContainerRef = useRef<Container | null>(null);
  const overlayRef = useRef<Graphics | null>(null);
  const agentSpritesRef = useRef<Map<string, Container>>(new Map());
  const agentPosRef = useRef<Map<string, { tx: number; ty: number; cx: number; cy: number }>>(new Map());
  const speechSpriteRef = useRef<Map<string, Container>>(new Map());
  const animatedTreesRef = useRef<Array<{ canopy: Container; baseX: number; phase: number; sway: number }>>([]);
  const dragRef = useRef({ dragging: false, lastX: 0, lastY: 0, moved: false });
  const unsubRef = useRef<(() => void) | null>(null);
  const unsubBuildingsRef = useRef<(() => void) | null>(null);
  const unsubGridRef = useRef<(() => void) | null>(null);

  const map = useWorldStore((s) => s.map);

  // Update agent visuals on each tick
  const agents = useSimulationStore((s) => s.agents);
  const selectedAgentId = useSimulationStore((s) => s.selectedAgentId);

  const updateAgents = useCallback(
    (agentMap: Record<string, AgentData>) => {
      const layer = agentLayerRef.current;
      if (!layer) return;

      const sprites = agentSpritesRef.current;

      const positions = agentPosRef.current;

      for (const [id, agent] of Object.entries(agentMap)) {
        let sprite = sprites.get(id);

        if (!sprite) {
          sprite = createAgentSprite(agent);
          layer.addChild(sprite);
          sprites.set(id, sprite);
        }

        // Set TARGET position (lerp happens in ticker)
        const { x, y } = gridToScreen(agent.position[0], agent.position[1]);
        const targetY = y - 12;
        let pos = positions.get(id);
        if (!pos) {
          // First time — snap to position
          pos = { tx: x, ty: targetY, cx: x, cy: targetY };
          positions.set(id, pos);
          sprite.x = x;
          sprite.y = targetY;
        }
        pos.tx = x;
        pos.ty = targetY;

        sprite.zIndex = agent.position[0] + agent.position[1] + 100;

        // Update label & icon
        updateAgentSprite(sprite, agent, id === selectedAgentId);
      }
    },
    [selectedAgentId]
  );

  // Update agent targets when tick data changes (lerp happens in ticker)
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
      const centerTile = gridToScreen(20, 20);
      worldContainer.x = app.screen.width / 2 - centerTile.x;
      worldContainer.y = app.screen.height / 4 - centerTile.y;

      // Tile layer — will be rendered from backend data
      const tileContainer = new Container();
      worldContainer.addChild(tileContainer);

      // Building layer
      const buildingContainer = new Container();
      buildingContainer.sortableChildren = true;
      worldContainer.addChild(buildingContainer);
      buildingContainerRef.current = buildingContainer;

      // Render map from backend tileGrid when available
      const renderFromBackend = () => {
        const state = useSimulationStore.getState();
        const grid = state.tileGrid;
        if (grid && grid.length > 0) {
          tileContainer.removeChildren();
          animatedTreesRef.current = [];
          renderMapFromGrid(tileContainer, grid);
          // Re-render buildings too
          const bc = buildingContainerRef.current;
          if (bc) {
            bc.removeChildren();
            if (state.buildings && state.buildings.length > 0) {
              renderBuildingsInto(bc, state.buildings.map((b: any) => ({
                type: b.type || b.id, label: b.label,
                col: b.col, row: b.row, width: b.width, height: b.height, color: "",
              })));
            }
          }
          return true;
        }
        return false;
      };

      // Try immediately (might have data from previous connection)
      if (!renderFromBackend()) {
        // No backend data yet — render placeholder from local map
        renderMapFromGrid(tileContainer, map.tiles.map((row: any[]) =>
          row.map((t: any) => ({ col: t.col, row: t.row, type: t.type, decoration: t.decoration, structure: t.building ? { label: "" } : null }))
        ));
        renderBuildingsInto(buildingContainer, map.buildings.map((b: any) => ({
          type: b.type, label: b.label, col: b.col, row: b.row, width: b.width, height: b.height, color: "",
        })));
      }

      // Subscribe: re-render when backend sends tile data
      unsubGridRef.current = useSimulationStore.subscribe((state, prev) => {
        if (state.tileGrid && state.tileGrid !== prev.tileGrid) {
          renderFromBackend();
        }
        if (state.buildings && state.buildings !== prev.buildings && state.buildings.length !== (prev.buildings?.length || 0)) {
          const bc = buildingContainerRef.current;
          if (bc) {
            bc.removeChildren();
            renderBuildingsInto(bc, state.buildings.map((b: any) => ({
              type: b.type || b.id, label: b.label,
              col: b.col, row: b.row, width: b.width, height: b.height, color: "",
            })));
          }
        }
      });

      // Agent layer on top
      const agentLayer = new Container();
      agentLayer.sortableChildren = true;
      worldContainer.addChild(agentLayer);
      agentLayerRef.current = agentLayer;

      // Smooth movement ticker — lerps agent sprites toward target positions every frame
      app.ticker.add(() => {
        const sprites = agentSpritesRef.current;
        const positions = agentPosRef.current;
        for (const [id, pos] of positions.entries()) {
          const sprite = sprites.get(id);
          if (!sprite) continue;
          // Lerp toward target
          const lerpSpeed = 0.06;
          pos.cx += (pos.tx - pos.cx) * lerpSpeed;
          pos.cy += (pos.ty - pos.cy) * lerpSpeed;
          if (Math.abs(pos.tx - pos.cx) < 0.3) pos.cx = pos.tx;
          if (Math.abs(pos.ty - pos.cy) < 0.3) pos.cy = pos.ty;
          sprite.x = pos.cx;
          sprite.y = pos.cy;
        }

        // Camera follow — smooth tracking using lerped position
        const followId = useSimulationStore.getState().followAgentId;
        if (followId && worldContainerRef.current) {
          const pos = positions.get(followId);
          if (pos) {
            const wc = worldContainerRef.current;
            const targetX = app.screen.width / 2 - pos.cx * wc.scale.x;
            const targetY = app.screen.height / 2 - pos.cy * wc.scale.y;
            wc.x += (targetX - wc.x) * 0.08;
            wc.y += (targetY - wc.y) * 0.08;
          }
        }

        const treeTime = performance.now() * 0.0015;
        for (const tree of animatedTreesRef.current) {
          tree.canopy.x = tree.baseX + Math.sin(treeTime + tree.phase) * tree.sway;
          tree.canopy.rotation = Math.sin(treeTime * 0.8 + tree.phase) * 0.018;
        }

        // Speech bubbles — keyed by agentId (one bubble per agent, replaces on new speech)
        const bubbles = useSimulationStore.getState().speechBubbles;
        const now = Date.now();

        // Filter to active bubbles, deduplicate per agent (keep newest), cap at 2
        const activeBubbles = bubbles.filter(b => b.expires > now);
        const latestByAgent = new Map<string, typeof activeBubbles[0]>();
        for (const b of activeBubbles) {
          const existing = latestByAgent.get(b.agentId);
          if (!existing || b.expires > existing.expires) {
            latestByAgent.set(b.agentId, b);
          }
        }
        // Keep only the 2 most recent bubbles
        const visibleBubbles = [...latestByAgent.values()]
          .sort((a, b) => b.expires - a.expires)
          .slice(0, 2);
        const visibleAgentIds = new Set(visibleBubbles.map(b => b.agentId));

        // Remove sprites for agents no longer showing a bubble
        for (const [agentId, sprite] of speechSpriteRef.current.entries()) {
          if (!visibleAgentIds.has(agentId)) {
            sprite.destroy();
            speechSpriteRef.current.delete(agentId);
          }
        }

        // Create or update bubble for each visible agent
        // First pass: build all bubbles and compute their screen rects
        const bubbleRects: Array<{ agentId: string; x: number; y: number; w: number; h: number }> = [];

        for (const bubble of visibleBubbles) {
          const pos = positions.get(bubble.agentId);
          if (!pos || !agentLayerRef.current) continue;

          const agentState = useSimulationStore.getState().agents[bubble.agentId];
          const agentName = agentState?.name?.split(" ")[0] || "";
          const displayText = `${agentName}: ${bubble.text}`;

          let container = speechSpriteRef.current.get(bubble.agentId);
          if (container) {
            container.removeChildren();
          } else {
            container = new Container();
            container.zIndex = 9999;
            agentLayerRef.current.addChild(container);
            speechSpriteRef.current.set(bubble.agentId, container);
          }

          // Wrap width scales with text length — short text stays compact, long text gets wider
          const charCount = displayText.length;
          const maxWrapWidth = Math.min(160, Math.max(50, charCount * 2.5));

          const textObj = new Text({
            text: displayText,
            style: new TextStyle({
              fontFamily: "sans-serif",
              fontSize: 7,
              fill: 0x333333,
              wordWrap: true,
              wordWrapWidth: maxWrapWidth,
            }),
          });
          const padding = 4;
          const bubbleW = textObj.width + padding * 2;
          const bubbleH = textObj.height + padding * 2;

          // Background sized to actual text
          const bg = new Graphics();
          bg.roundRect(-padding, -padding, bubbleW, bubbleH, 3);
          bg.fill({ color: 0xffffff, alpha: 0.9 });
          bg.stroke({ width: 0.5, color: 0x999999 });

          // Trailing pointer/tail from bubble bottom center to agent
          const tailX = bubbleW / 2 - padding;
          const tailY = bubbleH - padding;
          bg.moveTo(tailX - 3, tailY);
          bg.lineTo(tailX, tailY + 6);
          bg.lineTo(tailX + 3, tailY);
          bg.closePath();
          bg.fill({ color: 0xffffff, alpha: 0.9 });
          bg.stroke({ width: 0.5, color: 0x999999 });

          container.addChild(bg);
          container.addChild(textObj);

          // Initial position: centered above agent
          let bx = pos.cx - bubbleW / 2 + padding;
          let by = pos.cy - 40 - bubbleH;

          // Push up if it overlaps a previously placed bubble
          for (const prev of bubbleRects) {
            const overlapX = bx < prev.x + prev.w && bx + bubbleW > prev.x;
            const overlapY = by < prev.y + prev.h + 6 && by + bubbleH > prev.y; // +6 for tail
            if (overlapX && overlapY) {
              by = prev.y - bubbleH - 4; // stack above with a small gap
            }
          }

          container.x = bx;
          container.y = by;
          bubbleRects.push({ agentId: bubble.agentId, x: bx, y: by, w: bubbleW, h: bubbleH });
        }
      });

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

      // Old building subscription removed — handled by unsubGrid above

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
      unsubBuildingsRef.current?.();
      unsubGridRef.current?.();
      if (appRef.current) {
        appRef.current.destroy(true);
        appRef.current = null;
      }
    };
  }, []);

  function renderMapFromGrid(container: Container, grid: any[][]) {
    const seed = (col: number, row: number) => ((col * 7 + row * 13) % 100) / 100;
    const mapHeight = grid.length;
    const mapWidth = grid[0]?.length || 40;

    for (let row = 0; row < mapHeight; row++) {
      for (let col = 0; col < mapWidth; col++) {
        const tile = grid[row][col];
        const { x, y } = gridToScreen(col, row);
        const s = seed(col, row);

        const tileContainer = new Container();
        tileContainer.x = x;
        tileContainer.y = y;
        const g = new Graphics();
        tileContainer.addChild(g);
        let baseColor = TILE_COLORS[tile.type] || TILE_COLORS.grass;

        // Subtle color variation for grass
        if (tile.type === "grass" || tile.type === "dark_grass") {
          const variation = Math.floor(s * 3);
          const grassColors = [0x4a7c3f, 0x4e8243, 0x467838, 0x528847];
          baseColor = tile.type === "dark_grass"
            ? [0x3d6b34, 0x3a6530, 0x40702e][variation % 3]
            : grassColors[variation % 4];
        }

        // Water shimmer
        if (tile.type === "water") {
          baseColor = [0x3a6ea5, 0x3570a8, 0x3f72a0][Math.floor(s * 3)];
        }

        // Path texture variation
        if (tile.type === "path") {
          baseColor = [0xc4a86b, 0xc8ac70, 0xbfa465][Math.floor(s * 3)];
        }

        // Draw tile diamond
        g.poly([
          { x: 0, y: -TILE_HEIGHT / 2 },
          { x: TILE_WIDTH / 2, y: 0 },
          { x: 0, y: TILE_HEIGHT / 2 },
          { x: -TILE_WIDTH / 2, y: 0 },
        ]);
        g.fill(baseColor);

        // Subtle grid lines
        g.poly([
          { x: 0, y: -TILE_HEIGHT / 2 },
          { x: TILE_WIDTH / 2, y: 0 },
          { x: 0, y: TILE_HEIGHT / 2 },
          { x: -TILE_WIDTH / 2, y: 0 },
        ]);
        g.stroke({ width: 0.3, color: 0x000000, alpha: 0.06 });

        // Path cobblestone dots
        if (tile.type === "path" && s > 0.3) {
          for (let i = 0; i < 3; i++) {
            const px = (((col * 3 + i * 7) % 11) - 5) * 2;
            const py = (((row * 5 + i * 3) % 7) - 3);
            g.circle(px, py, 1);
            g.fill({ color: 0x9e8b5e, alpha: 0.4 });
          }
        }

        // Grass tufts
        if ((tile.type === "grass" || tile.type === "dark_grass") && s > 0.7 && !tile.building && !tile.decoration) {
          g.moveTo(-2, 0);
          g.lineTo(-1, -4);
          g.lineTo(0, 0);
          g.stroke({ width: 1, color: 0x3a6b2e, alpha: 0.5 });
          g.moveTo(1, -1);
          g.lineTo(2, -5);
          g.lineTo(3, -1);
          g.stroke({ width: 1, color: 0x3a6b2e, alpha: 0.4 });
        }

        // Trees — multi-layered and animated according to remaining wood
        if (tile.decoration === "tree") {
          const woodLevel = Math.max(1, Math.min(3, tile.resourceState?.wood || 3));
          const trunk = new Graphics();
          trunk.rect(-2, -2, 4, 8);
          trunk.fill(0x5c3a1e);
          trunk.rect(-1, -1, 2, 6);
          trunk.fill(0x6b4423);
          tileContainer.addChild(trunk);

          const canopy = new Container();
          const canopyGraphic = new Graphics();
          const treeColors = [0x2d5a1e, 0x357a24, 0x2a5219];
          const tc = treeColors[Math.floor(s * 3)];
          const widthScale = woodLevel === 3 ? 1 : woodLevel === 2 ? 0.82 : 0.62;
          const heightScale = woodLevel === 3 ? 1 : woodLevel === 2 ? 0.88 : 0.74;
          canopyGraphic.poly([{ x: 0, y: -22 * heightScale }, { x: 10 * widthScale, y: -4 }, { x: -10 * widthScale, y: -4 }]);
          canopyGraphic.fill(darkenColor(tc, 0.8));
          canopyGraphic.poly([{ x: 0, y: -26 * heightScale }, { x: 8 * widthScale, y: -10 }, { x: -8 * widthScale, y: -10 }]);
          canopyGraphic.fill(tc);
          canopyGraphic.poly([{ x: 0, y: -29 * heightScale }, { x: 5 * widthScale, y: -16 }, { x: -5 * widthScale, y: -16 }]);
          canopyGraphic.fill(darkenColor(tc, 1.2));
          canopy.addChild(canopyGraphic);
          tileContainer.addChild(canopy);
          animatedTreesRef.current.push({
            canopy,
            baseX: 0,
            phase: (col * 0.37) + (row * 0.61),
            sway: 0.35 + (woodLevel * 0.18),
          });
        }

        if (tile.decoration === "stump") {
          g.ellipse(0, 0, 5, 3);
          g.fill(0x6b4423);
          g.ellipse(0, -1, 4, 2);
          g.fill(0x8a5a35);
        }

        // Flowers — varied
        if (tile.decoration === "flower") {
          const flowerTypes = [0xff6b9d, 0xffd93d, 0xff8a5c, 0xc084fc, 0x64b5f6, 0xff7043];
          for (let i = 0; i < 5; i++) {
            const fx = (((col * 3 + i * 11) % 13) - 6);
            const fy = (((row * 7 + i * 5) % 9) - 4);
            const fc = flowerTypes[(col + row + i) % flowerTypes.length];
            // Stem
            g.moveTo(fx, fy + 2);
            g.lineTo(fx, fy - 1);
            g.stroke({ width: 0.8, color: 0x2d8a2d, alpha: 0.6 });
            // Petals
            g.circle(fx, fy - 2, 2);
            g.fill(fc);
            g.circle(fx, fy - 2, 0.8);
            g.fill(0xffffff);
          }
        }

        // Water ripple circles
        if (tile.type === "water") {
          g.circle((s * 10 - 5), (s * 6 - 3), 3 + s * 4);
          g.stroke({ width: 0.5, color: 0x5090c0, alpha: 0.3 });
        }

        container.addChild(tileContainer);
      }
    }
  }

  function renderBuildingsInto(container: Container, buildings: any[]) {
    for (const b of buildings) {
      const group = new Container();
      group.zIndex = b.col + b.row + b.width + b.height;
      container.addChild(group);

      const color = BUILDING_COLORS[b.type] || 0x888888;
      const g = new Graphics();
      const tl = gridToScreen(b.col, b.row);
      const tr = gridToScreen(b.col + b.width, b.row);
      const br = gridToScreen(b.col + b.width, b.row + b.height);
      const bl = gridToScreen(b.col, b.row + b.height);
      const center = gridToScreen(b.col + b.width / 2, b.row + b.height / 2);

      const bh =
        b.type === "church" ? 32
        : b.type === "town_hall" ? 28
        : b.type === "tavern" ? 24
        : b.type.startsWith("house") ? 18
        : b.type === "pond" || b.type === "park" || b.type === "farm" ? 0
        : 22;

      if (bh > 0) {
        // Foundation shadow
        g.poly([
          { x: bl.x + 3, y: bl.y + 2 },
          { x: br.x + 3, y: br.y + 2 },
          { x: tr.x + 3, y: tr.y + 2 },
          { x: tl.x + 3, y: tl.y + 2 },
        ]);
        g.fill({ color: 0x000000, alpha: 0.15 });

        // Front face
        g.poly([
          { x: bl.x, y: bl.y - bh },
          { x: br.x, y: br.y - bh },
          { x: br.x, y: br.y },
          { x: bl.x, y: bl.y },
        ]);
        g.fill(darkenColor(color, 0.65));

        // Side face
        g.poly([
          { x: br.x, y: br.y - bh },
          { x: tr.x, y: tr.y - bh },
          { x: tr.x, y: tr.y },
          { x: br.x, y: br.y },
        ]);
        g.fill(darkenColor(color, 0.8));

        // Roof — slightly different color
        const roofColor = b.type === "church" ? 0x8b0000
          : b.type === "tavern" ? 0x6b3410
          : b.type === "town_hall" ? 0x4a5568
          : b.type.startsWith("house") ? darkenColor(color, 1.1)
          : darkenColor(color, 1.05);

        g.poly([
          { x: tl.x, y: tl.y - bh },
          { x: tr.x, y: tr.y - bh },
          { x: br.x, y: br.y - bh },
          { x: bl.x, y: bl.y - bh },
        ]);
        g.fill(roofColor);

        // Roof edge highlight
        g.moveTo(tl.x, tl.y - bh);
        g.lineTo(tr.x, tr.y - bh);
        g.stroke({ width: 1, color: 0xffffff, alpha: 0.15 });

        // Windows and door on front face — isometric aligned
        if (!["pond", "park", "farm"].includes(b.type)) {
          // Front face wall direction: bl → br
          const wallDx = br.x - bl.x;
          const wallDy = br.y - bl.y;
          const wallLen = Math.sqrt(wallDx * wallDx + wallDy * wallDy);
          // Normalized wall direction
          const nx = wallDx / wallLen;
          const ny = wallDy / wallLen;

          // Helper: get point on front face at (u, v) where u=0..1 along wall, v=0..1 up the wall
          const facePt = (u: number, v: number) => ({
            x: bl.x + wallDx * u,
            y: bl.y + wallDy * u - bh * v,
          });

          // Windows at 25% and 75% along the wall, 50-70% up
          const windowPositions = bh > 24 ? [
            [0.25, 0.4], [0.75, 0.4], [0.25, 0.7], [0.75, 0.7],
          ] : [
            [0.3, 0.5], [0.7, 0.5],
          ];

          const ws = 5; // window half-size along wall
          const wh = 5; // window height
          for (const [wu, wv] of windowPositions) {
            const c = facePt(wu, wv);
            // Window frame (isometric parallelogram)
            g.poly([
              { x: c.x - nx * ws, y: c.y - ny * ws - wh },
              { x: c.x + nx * ws, y: c.y + ny * ws - wh },
              { x: c.x + nx * ws, y: c.y + ny * ws + wh },
              { x: c.x - nx * ws, y: c.y - ny * ws + wh },
            ]);
            g.fill(0x2a2a3e);
            // Window glow (slightly smaller)
            const gs = ws - 1;
            const gh = wh - 1;
            g.poly([
              { x: c.x - nx * gs, y: c.y - ny * gs - gh },
              { x: c.x + nx * gs, y: c.y + ny * gs - gh },
              { x: c.x + nx * gs, y: c.y + ny * gs + gh },
              { x: c.x - nx * gs, y: c.y - ny * gs + gh },
            ]);
            g.fill(0xfff4c2);
          }

          // Door at center-bottom of front face
          const dc = facePt(0.5, 0.0);
          const dw = 4; // door half-width along wall
          const dh = bh * 0.35; // door height
          g.poly([
            { x: dc.x - nx * dw, y: dc.y - ny * dw - dh },
            { x: dc.x + nx * dw, y: dc.y + ny * dw - dh },
            { x: dc.x + nx * dw, y: dc.y + ny * dw },
            { x: dc.x - nx * dw, y: dc.y - ny * dw },
          ]);
          g.fill(0x3a2510);
          // Door handle
          g.circle(dc.x + nx * 2, dc.y + ny * 2 - dh * 0.4, 1);
          g.fill(0xd4af37);
        }

        // Church steeple
        if (b.type === "church") {
          const cx = (tl.x + br.x) / 2;
          const cy = tl.y - bh;
          g.poly([{ x: cx, y: cy - 18 }, { x: cx + 6, y: cy }, { x: cx - 6, y: cy }]);
          g.fill(0xddd8c4);
          // Cross
          g.rect(cx - 1, cy - 24, 2, 8);
          g.fill(0xd4af37);
          g.rect(cx - 4, cy - 20, 8, 2);
          g.fill(0xd4af37);
        }

        // Tavern sign
        if (b.type === "tavern") {
          g.rect(br.x - 2, br.y - bh - 5, 2, 10);
          g.fill(0x5c3a1e);
          g.roundRect(br.x - 10, br.y - bh - 8, 12, 8, 1);
          g.fill(0xc4883a);
          g.stroke({ width: 0.5, color: 0x5c3a1e });
        }

        // Chimney on houses — placed on the roof
        if (b.type.startsWith("house")) {
          const chPt = gridToScreen(b.col + b.width * 0.75, b.row + b.height * 0.25);
          const chx = chPt.x;
          const chy = chPt.y - bh;
          // Chimney body (isometric-ish)
          g.poly([
            { x: chx - 3, y: chy - 10 },
            { x: chx + 3, y: chy - 8 },
            { x: chx + 3, y: chy },
            { x: chx - 3, y: chy - 2 },
          ]);
          g.fill(0x8b4513);
          // Chimney top
          g.poly([
            { x: chx - 4, y: chy - 11 },
            { x: chx + 4, y: chy - 9 },
            { x: chx + 4, y: chy - 8 },
            { x: chx - 4, y: chy - 10 },
          ]);
          g.fill(0x6b3510);
        }

      } else {
        // Flat features with more detail
        if (b.type === "pond") {
          // Water with depth gradient
          g.poly([{ x: tl.x, y: tl.y }, { x: tr.x, y: tr.y }, { x: br.x, y: br.y }, { x: bl.x, y: bl.y }]);
          g.fill(0x2a5a8a);
          // Inner lighter area
          const inset = 8;
          g.ellipse(center.x, center.y, (br.x - tl.x) / 2 - inset, (br.y - tl.y) / 2 - inset);
          g.fill(0x3a7ab0);
          // Lily pads
          g.circle(center.x - 8, center.y - 3, 3);
          g.fill(0x228b22);
          g.circle(center.x + 6, center.y + 4, 2.5);
          g.fill(0x2a9a2a);
        } else if (b.type === "park") {
          g.poly([{ x: tl.x, y: tl.y }, { x: tr.x, y: tr.y }, { x: br.x, y: br.y }, { x: bl.x, y: bl.y }]);
          g.fill(0x2d8a2d);
          // Benches
          g.rect(center.x - 8, center.y - 2, 6, 2);
          g.fill(0x8b6914);
          g.rect(center.x + 4, center.y + 2, 6, 2);
          g.fill(0x8b6914);
          // Fountain in center
          g.circle(center.x, center.y, 5);
          g.fill(0x778899);
          g.circle(center.x, center.y, 3);
          g.fill(0x4a8ab5);
        } else if (b.type === "farm") {
          // Farm field rows
          g.poly([{ x: tl.x, y: tl.y }, { x: tr.x, y: tr.y }, { x: br.x, y: br.y }, { x: bl.x, y: bl.y }]);
          g.fill(0x6b5b3a);
          // Crop rows
          for (let i = 0; i < 6; i++) {
            const ry = tl.y + (br.y - tl.y) * (i / 6);
            const rx = tl.x + (br.x - tl.x) * (i / 6);
            g.moveTo(rx + (tr.x - tl.x) * 0.1, ry + (tr.y - tl.y) * 0.1);
            g.lineTo(rx + (tr.x - tl.x) * 0.9, ry + (tr.y - tl.y) * 0.9);
            g.stroke({ width: 2, color: 0x5a8a2a, alpha: 0.6 });
          }
        } else {
          g.poly([{ x: tl.x, y: tl.y }, { x: tr.x, y: tr.y }, { x: br.x, y: br.y }, { x: bl.x, y: bl.y }]);
          g.fill(color);
        }
      }

      group.addChild(g);

      // Label with better styling
      const label = new Text({
        text: b.label,
        style: new TextStyle({
          fontFamily: "monospace",
          fontSize: 8,
          fill: 0xffffff,
          fontWeight: "bold",
          dropShadow: {
            alpha: 0.9,
            blur: 3,
            color: 0x000000,
            distance: 1,
          },
        }),
      });
      label.x = center.x - label.width / 2;
      label.y = center.y - Math.max(bh, 5) - 16;
      group.addChild(label);
    }
  }

  return <div ref={containerRef} className="w-full h-full cursor-grab" />;
}

function createAgentSprite(agent: AgentData): Container {
  const container = new Container();
  const color = AGENT_COLORS[agent.colorIndex % AGENT_COLORS.length];
  const skinTone = [0xf5d0a9, 0xe8b88a, 0xd4956b, 0xc68642, 0x8d5524][agent.colorIndex % 5];
  const hairColor = [0x2c1b0e, 0x4a3728, 0x8b6914, 0xa52a2a, 0x666666, 0xffffff][agent.colorIndex % 6];

  const body = new Graphics();

  // Shadow
  body.ellipse(0, 4, 5, 2);
  body.fill({ color: 0x000000, alpha: 0.25 });

  // Legs
  body.rect(-3, 0, 2, 4);
  body.fill(0x333355);
  body.rect(1, 0, 2, 4);
  body.fill(0x333355);

  // Body/shirt
  body.roundRect(-5, -8, 10, 9, 2);
  body.fill(color);
  body.stroke({ width: 0.5, color: darkenColor(color, 0.6), alpha: 0.5 });

  // Head
  body.circle(0, -12, 4);
  body.fill(skinTone);

  // Hair
  body.ellipse(0, -15, 4, 2.5);
  body.fill(hairColor);

  // Eyes
  body.circle(-1.5, -12, 0.7);
  body.fill(0x222222);
  body.circle(1.5, -12, 0.7);
  body.fill(0x222222);

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
  nameText.y = -24;
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
  iconText.y = -22;
  iconText.label = "icon";
  container.addChild(iconText);

  // Selection ring (hidden by default)
  const ring = new Graphics();
  ring.circle(0, -4, 12);
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
