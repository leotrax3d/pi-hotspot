import {
  Keyboard,
  BrickWall,
  Brain,
  Grid3X3,
  Zap,
  Bomb,
  Lightbulb,
  Bird,
} from "lucide-react";

export const singleplayerCatalog = [
  {
    id: "snake",
    name: "Snake",
    icon: Keyboard,
    desc: "Fressen. Wachsen. Ausweichen.",
  },
  {
    id: "breakout",
    name: "Breakout",
    icon: BrickWall,
    desc: "Ein Ball, ein Paddle, alle Steine.",
  },
  {
    id: "memory",
    name: "Memory",
    icon: Brain,
    desc: "Acht Paare. Ein gutes Gedächtnis.",
  },
  {
    id: "2048",
    name: "2048",
    icon: Grid3X3,
    desc: "Wischen und Zahlen verbinden.",
  },
  {
    id: "sprint",
    name: "Klick-Sprint",
    icon: Zap,
    desc: "20 Ziele gegen die Zeit.",
  },
  {
    id: "mines",
    name: "Minesweeper",
    icon: Bomb,
    desc: "Aufdecken. Markieren. Minen meiden.",
  },
  {
    id: "lights",
    name: "Lights Out",
    icon: Lightbulb,
    desc: "Schalte alle Lichter aus.",
  },
  {
    id: "flappy",
    name: "Flappy",
    icon: Bird,
    desc: "Tippen, fliegen, Lücken treffen.",
  },
] as const;
