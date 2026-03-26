export const TILE_WIDTH = 64;
export const TILE_HEIGHT = 32;

/** Convert grid coordinates to screen pixel position */
export function gridToScreen(
  col: number,
  row: number
): { x: number; y: number } {
  return {
    x: (col - row) * (TILE_WIDTH / 2),
    y: (col + row) * (TILE_HEIGHT / 2),
  };
}

/** Convert screen pixel position back to grid coordinates */
export function screenToGrid(
  screenX: number,
  screenY: number
): { col: number; row: number } {
  const col = Math.floor(
    (screenX / (TILE_WIDTH / 2) + screenY / (TILE_HEIGHT / 2)) / 2
  );
  const row = Math.floor(
    (screenY / (TILE_HEIGHT / 2) - screenX / (TILE_WIDTH / 2)) / 2
  );
  return { col, row };
}

/** Get depth/z-index for isometric sorting (higher = rendered later = on top) */
export function getTileDepth(col: number, row: number): number {
  return col + row;
}

/** Lerp between two screen positions */
export function lerpPosition(
  from: { x: number; y: number },
  to: { x: number; y: number },
  t: number
): { x: number; y: number } {
  return {
    x: from.x + (to.x - from.x) * t,
    y: from.y + (to.y - from.y) * t,
  };
}
