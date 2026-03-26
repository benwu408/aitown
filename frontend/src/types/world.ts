export type TileType =
  | "grass"
  | "path"
  | "water"
  | "dirt"
  | "sand"
  | "flowers"
  | "dark_grass";

export type BuildingType =
  | "town_hall"
  | "general_store"
  | "farm"
  | "barn"
  | "bakery"
  | "workshop"
  | "tavern"
  | "school"
  | "church"
  | "house_1"
  | "house_2"
  | "house_3"
  | "house_4"
  | "house_5"
  | "house_6"
  | "park"
  | "pond";

export interface Tile {
  col: number;
  row: number;
  type: TileType;
  building?: BuildingType;
  walkable: boolean;
  decoration?: string;
}

export interface Building {
  type: BuildingType;
  label: string;
  col: number;
  row: number;
  width: number;
  height: number;
  color: string;
}

export interface WorldMap {
  width: number;
  height: number;
  tiles: Tile[][];
  buildings: Building[];
}
