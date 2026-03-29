/** Map tile types to colors for procedural rendering */
export const TILE_COLORS: Record<string, number> = {
  grass: 0x4a7c3f,
  dark_grass: 0x3d6b34,
  path: 0xc4a86b,
  water: 0x3a6ea5,
  dirt: 0x8b7355,
  sand: 0xdcc090,
  flowers: 0x5a8c4f,
};

/** Map building types to colors */
export const BUILDING_COLORS: Record<string, number> = {
  town_hall: 0x8b7355,
  general_store: 0xcd853f,
  farm: 0x8b8b00,
  barn: 0x8b4513,
  bakery: 0xdeb887,
  workshop: 0x696969,
  tavern: 0xa0522d,
  meeting_hall: 0x4682b4,
  common_house: 0xf5f5dc,
  built_structure: 0xb08968,
  project: 0x6b8e23,
  house_1: 0xbc8f8f,
  house_2: 0xd2b48c,
  house_3: 0xc4a882,
  house_4: 0xb8a090,
  house_5: 0xa89080,
  house_6: 0xc8b8a0,
  park: 0x228b22,
  pond: 0x4169e1,
};

/** Map action types to emoji icons */
export const ACTION_ICONS: Record<string, string> = {
  talking: "\uD83D\uDCAC",
  working: "\uD83D\uDD28",
  buying: "\uD83D\uDED2",
  selling: "\uD83D\uDED2",
  sleeping: "\uD83D\uDCA4",
  eating: "\uD83C\uDF7D\uFE0F",
  reflecting: "\uD83D\uDCAD",
  arguing: "\uD83D\uDE20",
  celebrating: "\u2764\uFE0F",
  delivering: "\uD83C\uDF81",
  announcing: "\uD83D\uDCE2",
  crafting: "\uD83E\uDDF0",
  building: "\uD83C\uDFD7\uFE0F",
  gathering: "\uD83E\uDEF4",
  exploring: "\uD83D\uDDFA\uFE0F",
  healing: "\uD83D\uDC8A",
  stealing: "\uD83E\uDD77",
  giving: "\uD83C\uDF81",
  idle: "",
  walking: "",
};

/** Agent name colors for visual distinction */
export const AGENT_COLORS = [
  0xe74c3c, 0x3498db, 0x2ecc71, 0xe67e22, 0x9b59b6,
  0x1abc9c, 0xf39c12, 0x2980b9, 0xd35400, 0x27ae60,
  0x8e44ad, 0x16a085, 0xc0392b, 0x2c3e50, 0x7f8c8d,
];
