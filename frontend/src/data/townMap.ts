import { Building, Tile, WorldMap } from "../types/world";

const MAP_SIZE = 40;

// Building definitions with grid positions and sizes
export const BUILDINGS: Building[] = [
  { type: "town_hall", label: "Town Hall", col: 18, row: 18, width: 3, height: 3, color: "#8B7355" },
  { type: "general_store", label: "General Store", col: 22, row: 22, width: 3, height: 2, color: "#CD853F" },
  { type: "farm", label: "Farm", col: 6, row: 6, width: 4, height: 4, color: "#8B8B00" },
  { type: "barn", label: "Barn", col: 11, row: 8, width: 2, height: 2, color: "#8B4513" },
  { type: "bakery", label: "Bakery", col: 25, row: 20, width: 2, height: 2, color: "#DEB887" },
  { type: "workshop", label: "Workshop", col: 14, row: 24, width: 3, height: 2, color: "#696969" },
  { type: "tavern", label: "Tavern", col: 22, row: 26, width: 3, height: 2, color: "#A0522D" },
  { type: "school", label: "School", col: 28, row: 24, width: 2, height: 2, color: "#4682B4" },
  { type: "church", label: "Church", col: 26, row: 16, width: 2, height: 3, color: "#F5F5DC" },
  { type: "house_1", label: "House (Eleanor)", col: 14, row: 14, width: 2, height: 2, color: "#BC8F8F" },
  { type: "house_2", label: "House (John)", col: 10, row: 12, width: 2, height: 2, color: "#D2B48C" },
  { type: "house_3", label: "House (Kowalskis)", col: 16, row: 28, width: 2, height: 2, color: "#C4A882" },
  { type: "house_4", label: "House (Reeves)", col: 30, row: 20, width: 2, height: 2, color: "#B8A090" },
  { type: "house_5", label: "House (Brennans)", col: 12, row: 20, width: 2, height: 2, color: "#A89080" },
  { type: "house_6", label: "House (Others)", col: 30, row: 28, width: 2, height: 2, color: "#C8B8A0" },
  { type: "park", label: "Park", col: 18, row: 12, width: 3, height: 2, color: "#228B22" },
  { type: "pond", label: "Pond", col: 8, row: 32, width: 3, height: 3, color: "#4169E1" },
];

// Path connections between buildings (grid coordinates for path tiles)
function generatePaths(): Set<string> {
  const pathSet = new Set<string>();

  const addPath = (
    fromCol: number,
    fromRow: number,
    toCol: number,
    toRow: number
  ) => {
    let c = fromCol;
    let r = fromRow;
    // Walk horizontally first, then vertically
    while (c !== toCol) {
      pathSet.add(`${c},${r}`);
      c += c < toCol ? 1 : -1;
    }
    while (r !== toRow) {
      pathSet.add(`${c},${r}`);
      r += r < toRow ? 1 : -1;
    }
    pathSet.add(`${toCol},${toRow}`);
  };

  // Main road: horizontal through center
  for (let c = 4; c < 35; c++) {
    pathSet.add(`${c},21`);
  }

  // Main road: vertical through center
  for (let r = 4; r < 35; r++) {
    pathSet.add(`20,${r}`);
  }

  // Connect buildings to main roads
  addPath(19, 19, 20, 21); // Town Hall → crossroads
  addPath(23, 22, 23, 21); // General Store → main road
  addPath(8, 10, 8, 21);   // Farm area → main road
  addPath(12, 9, 12, 21);  // Barn → main road
  addPath(26, 21, 26, 21); // Bakery → main road
  addPath(15, 25, 15, 21); // Workshop → main road
  addPath(23, 27, 23, 21); // Tavern → main road
  addPath(29, 25, 29, 21); // School → main road
  addPath(27, 18, 27, 21); // Church → main road
  addPath(15, 15, 15, 21); // House 1 → main road
  addPath(11, 13, 11, 21); // House 2 → main road
  addPath(17, 29, 20, 29); // House 3 → vertical road
  addPath(31, 21, 31, 21); // House 4 → main road
  addPath(13, 21, 13, 21); // House 5 → main road
  addPath(31, 29, 31, 21); // House 6 → main road
  addPath(19, 13, 20, 13); // Park → vertical road
  addPath(9, 33, 9, 21);   // Pond → main road

  // Secondary paths
  addPath(15, 21, 15, 15); // Workshop area to houses
  addPath(23, 21, 23, 27); // Store to tavern
  addPath(20, 13, 20, 8);  // Park to barn area

  return pathSet;
}

// Decoration spots
const TREE_SPOTS = [
  [3, 3], [5, 15], [7, 28], [13, 5], [16, 10], [24, 8],
  [32, 10], [35, 15], [33, 25], [36, 30], [4, 35], [15, 35],
  [25, 5], [30, 5], [35, 8], [2, 20], [37, 20], [10, 30],
  [22, 10], [28, 12], [32, 16], [6, 25], [34, 22], [17, 7],
  [26, 32], [12, 34], [33, 33], [3, 10], [38, 12], [5, 38],
];

const FLOWER_SPOTS = [
  [17, 12], [19, 12], [21, 12], // Around park
  [19, 20], [21, 20],           // Around town hall
  [15, 16], [16, 16],           // Near house 1
  [27, 15], [28, 15],           // Near church
];

export function generateWorldMap(): WorldMap {
  const paths = generatePaths();
  const tiles: Tile[][] = [];

  // Build a set of building-occupied tiles
  const buildingTiles = new Set<string>();
  for (const b of BUILDINGS) {
    for (let dc = 0; dc < b.width; dc++) {
      for (let dr = 0; dr < b.height; dr++) {
        buildingTiles.add(`${b.col + dc},${b.row + dr}`);
      }
    }
  }

  const treeSet = new Set(TREE_SPOTS.map(([c, r]) => `${c},${r}`));
  const flowerSet = new Set(FLOWER_SPOTS.map(([c, r]) => `${c},${r}`));

  for (let row = 0; row < MAP_SIZE; row++) {
    const tileRow: Tile[] = [];
    for (let col = 0; col < MAP_SIZE; col++) {
      const key = `${col},${row}`;
      const isBuilding = buildingTiles.has(key);
      const isPath = paths.has(key);
      const isTree = treeSet.has(key);
      const isFlower = flowerSet.has(key);

      // Determine tile type
      let type: Tile["type"] = "grass";
      let building: Tile["building"] = undefined;
      let decoration: string | undefined;
      let walkable = true;

      if (isBuilding) {
        // Find which building
        for (const b of BUILDINGS) {
          if (
            col >= b.col &&
            col < b.col + b.width &&
            row >= b.row &&
            row < b.row + b.height
          ) {
            building = b.type;
            break;
          }
        }
        if (building === "pond") {
          type = "water";
          walkable = false;
        } else if (building === "farm") {
          type = "dirt";
          walkable = true;
        } else if (building === "park") {
          type = "dark_grass";
          walkable = true;
        } else {
          walkable = false;
        }
      } else if (isPath) {
        type = "path";
      } else if (isTree) {
        decoration = "tree";
        walkable = false;
      } else if (isFlower) {
        type = "flowers";
        decoration = "flower";
      } else {
        // Slight variety in grass
        type =
          Math.random() < 0.05
            ? "dark_grass"
            : "grass";
      }

      tileRow.push({ col, row, type, building, walkable, decoration });
    }
    tiles.push(tileRow);
  }

  return { width: MAP_SIZE, height: MAP_SIZE, tiles, buildings: BUILDINGS };
}
