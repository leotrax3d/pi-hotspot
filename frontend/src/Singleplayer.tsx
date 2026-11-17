import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Flag,
  Pause,
  Play,
  RotateCcw,
  Trophy,
  Undo2,
  HardDrive,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { singleplayerCatalog } from "./singleplayer-catalog";
import "./singleplayer.css";

type Phase = "ready" | "playing" | "paused" | "over" | "won";
type Direction = "up" | "down" | "left" | "right";
const arrows: Record<string, Direction> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
  w: "up",
  s: "down",
  a: "left",
  d: "right",
};
const random = (n: number) => Math.floor(Math.random() * n);
function shuffle<T>(items: T[]) {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = random(i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function readBest(id: string) {
  try {
    return Number(localStorage.getItem("schuelerwlan:best:" + id)) || 0;
  } catch {
    return 0;
  }
}
function useBest(id: string, lower = false) {
  const [best, setBest] = useState(() => readBest(id));
  return [
    best,
    (value: number) => {
      if (value > 0 && (!best || (lower ? value < best : value > best))) {
        setBest(value);
        try {
          localStorage.setItem("schuelerwlan:best:" + id, String(value));
        } catch {
          /* Storage can be disabled. */
        }
      }
    },
  ] as const;
}
function useKeys(handler: (key: string) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.repeat && (e.key === " " || e.key === "Escape")) {
        e.preventDefault();
        return;
      }
      if (
        e.ctrlKey ||
        e.metaKey ||
        e.altKey ||
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      if (arrows[e.key] || [" ", "Escape"].includes(e.key)) {
        e.preventDefault();
        ref.current(e.key);
      }
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);
}
function Dpad({ onMove }: { onMove: (d: Direction) => void }) {
  return (
    <div className="sp-dpad">
      {(["up", "left", "down", "right"] as Direction[]).map((d, i) => {
        const Icon = [ArrowUp, ArrowLeft, ArrowDown, ArrowRight][i];
        return (
          <Button
            key={d}
            variant="outline"
            size="icon"
            aria-label={
              {
                up: "Nach oben",
                left: "Nach links",
                down: "Nach unten",
                right: "Nach rechts",
              }[d]
            }
            onClick={() => onMove(d)}
          >
            <Icon />
          </Button>
        );
      })}
    </div>
  );
}
function Surface({
  children,
  onSwipe,
}: {
  children: ReactNode;
  onSwipe?: (d: Direction) => void;
}) {
  const start = useRef<[number, number] | null>(null);
  return (
    <div
      className="sp-surface"
      onPointerDown={(e) => {
        start.current = [e.clientX, e.clientY];
      }}
      onPointerUp={(e) => {
        if (!start.current || !onSwipe) return;
        const dx = e.clientX - start.current[0],
          dy = e.clientY - start.current[1];
        start.current = null;
        if (Math.max(Math.abs(dx), Math.abs(dy)) > 24)
          onSwipe(
            Math.abs(dx) > Math.abs(dy)
              ? dx > 0
                ? "right"
                : "left"
              : dy > 0
                ? "down"
                : "up",
          );
      }}
    >
      {children}
    </div>
  );
}
function GameShell({
  id,
  phase,
  setPhase,
  score,
  best,
  unit = "",
  onReset,
  children,
  controls,
  progress,
}: {
  id: string;
  phase: Phase;
  setPhase: (p: Phase) => void;
  score: number | string;
  best?: number | string;
  unit?: string;
  onReset: () => void;
  children: ReactNode;
  controls?: ReactNode;
  progress?: number;
}) {
  const title = singleplayerCatalog.find((g) => g.id === id)?.name || id;
  useEffect(() => {
    const hide = () => {
      if (document.hidden && phase === "playing") setPhase("paused");
    };
    document.addEventListener("visibilitychange", hide);
    return () => document.removeEventListener("visibilitychange", hide);
  }, [phase, setPhase]);
  return (
    <Card className="sp-game">
      <CardHeader className="sp-header">
        <CardTitle>{title}</CardTitle>
        <div className="sp-tools">
          <Button
            variant="outline"
            size="icon"
            aria-label={
              phase === "playing" ? "Spiel pausieren" : "Spiel fortsetzen"
            }
            disabled={phase !== "playing" && phase !== "paused"}
            onClick={() => setPhase(phase === "playing" ? "paused" : "playing")}
          >
            {phase === "paused" ? <Play /> : <Pause />}
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Neu starten"
            onClick={onReset}
          >
            <RotateCcw />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="sp-scoreboard">
          <div>
            <span>
              {id === "memory" || id === "lights"
                ? "Züge"
                : id === "mines"
                  ? "Minen"
                  : id === "sprint"
                    ? "Zeit"
                    : "Punkte"}
            </span>
            <strong>
              {score}
              <small>{unit}</small>
            </strong>
          </div>
          {best !== undefined && (
            <div className="sp-record">
              <span>
                <Trophy size={12} />
                Bestleistung
              </span>
              <strong>
                {best || "—"}
                <small>{best ? unit : ""}</small>
              </strong>
            </div>
          )}
        </div>
        {progress !== undefined && (
          <div
            className="sp-progress"
            role="progressbar"
            aria-label="Spielfortschritt"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
          >
            <i style={{ width: Math.max(0, Math.min(100, progress)) + "%" }} />
          </div>
        )}
        <div className="sp-stage">
          {children}
          {phase !== "playing" && (
            <div className="sp-overlay" role="status" aria-live="polite">
              <div>
                {phase === "won" ? (
                  <Trophy />
                ) : phase === "paused" ? (
                  <Pause />
                ) : phase === "over" ? (
                  <RotateCcw />
                ) : (
                  <Play />
                )}
                <h3>
                  {phase === "ready"
                    ? "Bereit?"
                    : phase === "paused"
                      ? "Pause"
                      : phase === "won"
                        ? "Geschafft!"
                        : "Game over"}
                </h3>
                {(phase === "over" || phase === "won") && (
                  <p>
                    {score}
                    {unit} · {title}
                  </p>
                )}
                <Button
                  onClick={() =>
                    phase === "over" || phase === "won"
                      ? onReset()
                      : setPhase("playing")
                  }
                >
                  {phase === "ready" ? (
                    <>
                      <Play />
                      Spielen
                    </>
                  ) : phase === "paused" ? (
                    <>
                      <Play />
                      Weiter
                    </>
                  ) : (
                    <>
                      <RotateCcw />
                      Nochmal
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
        <div className="sp-controls">{controls}</div>
      </CardContent>
    </Card>
  );
}

type ArcadeKind = "snake" | "breakout" | "flappy";
function Arcade({ kind, onReset }: { kind: ArcadeKind; onReset: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null),
    [phase, setPhase] = useState<Phase>("ready"),
    phaseRef = useRef<Phase>("ready"),
    [score, setScore] = useState(0),
    [best, saveBest] = useBest(kind),
    [lives, setLives] = useState(3),
    [level, setLevel] = useState(1);
  const input = useRef({
      dir: "right" as Direction,
      queue: [] as Direction[],
      left: false,
      right: false,
      x: null as number | null,
      flap: false,
    }),
    scoreRef = useRef(0),
    bestRef = useRef(saveBest);
  phaseRef.current = phase;
  bestRef.current = saveBest;
  useKeys((key) => {
    if (key === "Escape" || (key === " " && kind !== "flappy")) {
      setPhase((p) =>
        p === "playing"
          ? "paused"
          : p === "paused" || p === "ready"
            ? "playing"
            : p,
      );
      return;
    }
    if (kind === "flappy" && (key === " " || key === "ArrowUp")) {
      if (phaseRef.current === "ready") setPhase("playing");
      input.current.flap = true;
    }
    if (kind === "snake" && arrows[key]) {
      const q = input.current.queue;
      if (q.length < 2) q.push(arrows[key]);
    }
  });
  useEffect(() => {
    if (kind !== "breakout") return;
    const down = (e: KeyboardEvent) => {
        if (['ArrowLeft', 'ArrowRight', 'a', 'd'].includes(e.key)) input.current.x = null;
        if (e.key === "ArrowLeft" || e.key === "a") input.current.left = true;
        if (e.key === "ArrowRight" || e.key === "d") input.current.right = true;
      },
      up = (e: KeyboardEvent) => {
        if (e.key === "ArrowLeft" || e.key === "a") input.current.left = false;
        if (e.key === "ArrowRight" || e.key === "d")
          input.current.right = false;
      },
      blur = () => {
        input.current.left = false;
        input.current.right = false;
      };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, [kind]);
  useEffect(() => {
    const c = canvas.current!,
      ctx = c.getContext("2d")!;
    let frame = 0,
      last = 0,
      acc = 0,
      wasPlaying = false;
    const W = 600,
      H = 480;
    let snake = [
        [7, 10],
        [6, 10],
        [5, 10],
      ],
      food = [15, 10],
      direction: Direction = "right";
    let px = 250,
      bx = 300,
      by = 370,
      vx = 155,
      vy = -230,
      life = 3,
      lvl = 1,
      serve = 0;
    let bricks = makeBricks();
    let bird = 220,
      birdV = 0,
      pipeX = 660,
      gap = 210,
      passed = false;
    function makeBricks() {
      return Array.from({ length: 40 }, (_, i) => ({
        x: 22 + (i % 8) * 70,
        y: 42 + Math.floor(i / 8) * 27,
        on: true,
      }));
    }
    const add = (n: number) => {
      scoreRef.current += n;
      setScore(scoreRef.current);
      bestRef.current(scoreRef.current);
    };
    const end = () => {
      phaseRef.current = "over";
      setPhase("over");
    };
    const draw = () => {
      ctx.fillStyle = "#080808";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#f5f5f5";
      if (kind === "snake") {
        ctx.strokeStyle = "#151515";
        for (let x = 0; x < W; x += 20) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, H);
          ctx.stroke();
        }
        for (let y = 0; y < H; y += 20) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(W, y);
          ctx.stroke();
        }
        snake.forEach((p, i) => {
          ctx.fillStyle = i ? "#999999" : "#ffffff";
          ctx.fillRect(p[0] * 20 + 2, p[1] * 20 + 2, 16, 16);
        });
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(food[0] * 20 + 10, food[1] * 20 + 10, 6, 0, Math.PI * 2);
        ctx.fill();
      } else if (kind === "breakout") {
        bricks.forEach((b, i) => {
          if (!b.on) return;
          ctx.fillStyle = [
            "#f5f5f5",
            "#cccccc",
            "#999999",
            "#777777",
            "#555555",
          ][Math.floor(i / 8)];
          ctx.fillRect(b.x, b.y, 64, 20);
        });
        ctx.fillStyle = "#f5f5f5";
        ctx.fillRect(px, H - 30, 100, 10);
        ctx.beginPath();
        ctx.arc(bx, by, 7, 0, Math.PI * 2);
        ctx.fill();
        if (serve > 0) {
          ctx.fillStyle = "#999999";
          ctx.textAlign = "center";
          ctx.font = "18px sans-serif";
          ctx.fillText(String(Math.ceil(serve)), 300, 280);
        }
      } else {
        ctx.fillStyle = "#262626";
        ctx.fillRect(pipeX, 0, 64, gap - 84);
        ctx.fillRect(pipeX, gap + 84, 64, H - gap - 84);
        ctx.strokeStyle = "#999999";
        ctx.strokeRect(pipeX, 0, 64, gap - 84);
        ctx.strokeRect(pipeX, gap + 84, 64, H - gap - 84);
        ctx.fillStyle = "#f5f5f5";
        ctx.beginPath();
        ctx.arc(150, bird, 13, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#080808";
        ctx.fillRect(153, bird - 5, 4, 4);
        ctx.fillStyle = "#999999";
        ctx.fillRect(160, bird, 10, 5);
      }
    };
    const loop = (t: number) => {
      const playing = phaseRef.current === "playing";
      const dt = playing && wasPlaying ? Math.min((t - last) / 1000, 0.035) : 0;
      last = t;
      wasPlaying = playing;
      if (playing) {
        if (kind === "snake") {
          acc += dt;
          const tick = Math.max(0.065, 0.15 - scoreRef.current * 0.003);
          if (acc >= tick) {
            acc -= tick;
            const next = input.current.queue.shift();
            const opposite: Record<Direction, Direction> = {
              up: "down",
              down: "up",
              left: "right",
              right: "left",
            };
            if (next && next !== opposite[direction]) direction = next;
            const [dx, dy] = {
              up: [0, -1],
              down: [0, 1],
              left: [-1, 0],
              right: [1, 0],
            }[direction];
            const head = [snake[0][0] + dx, snake[0][1] + dy],
              eat = head[0] === food[0] && head[1] === food[1];
            if (
              head[0] < 0 ||
              head[0] >= 30 ||
              head[1] < 0 ||
              head[1] >= 24 ||
              snake
                .slice(0, eat ? undefined : -1)
                .some((p) => p[0] === head[0] && p[1] === head[1])
            )
              end();
            else {
              snake.unshift(head);
              if (eat) {
                add(1);
                const free: number[][] = [];
                for (let i = 0; i < 720; i++)
                  if (
                    !snake.some(
                      (p) => p[0] === i % 30 && p[1] === Math.floor(i / 30),
                    )
                  )
                    free.push([i % 30, Math.floor(i / 30)]);
                if (!free.length) {
                  setPhase("won");
                  phaseRef.current = "won";
                } else food = free[random(free.length)];
              } else snake.pop();
            }
          }
        } else if (kind === "breakout") {
          if (input.current.x !== null) px = input.current.x - 50;
          px +=
            (Number(input.current.right) - Number(input.current.left)) *
            420 *
            dt;
          px = Math.max(0, Math.min(W - 100, px));
          if (serve > 0) {
            serve -= dt;
            bx = px + 50;
            by = H - 48;
          } else {
            const steps = 3;
            for (let step = 0; step < steps; step++) {
              const oldY = by;
              bx += (vx * dt) / steps;
              by += (vy * dt) / steps;
              if (bx < 7) {
                bx = 7;
                vx = Math.abs(vx);
              }
              if (bx > W - 7) {
                bx = W - 7;
                vx = -Math.abs(vx);
              }
              if (by < 7) {
                by = 7;
                vy = Math.abs(vy);
              }
              if (
                vy > 0 &&
                oldY + 7 <= H - 30 &&
                by + 7 >= H - 30 &&
                bx >= px - 7 &&
                bx <= px + 107
              ) {
                by = H - 37;
                const ratio = (bx - (px + 50)) / 50;
                vx = ratio * (240 + lvl * 15);
                vy = -Math.sqrt(
                  Math.max(180 * 180, (300 + lvl * 10) ** 2 - vx * vx),
                );
              }
              for (const b of bricks) {
                if (
                  b.on &&
                  bx + 7 > b.x &&
                  bx - 7 < b.x + 64 &&
                  by + 7 > b.y &&
                  by - 7 < b.y + 20
                ) {
                  b.on = false;
                  if (oldY + 7 <= b.y || oldY - 7 >= b.y + 20) vy *= -1;
                  else vx *= -1;
                  add(10);
                  break;
                }
              }
              if (by > H + 10) {
                life--;
                setLives(life);
                if (!life) {
                  end();
                  break;
                }
                serve = 1.5;
                vx = 155;
                vy = -230;
                break;
              }
            }
            if (bricks.every((b) => !b.on)) {
              lvl++;
              setLevel(lvl);
              bricks = makeBricks();
              serve = 1.5;
              vx = 155;
              vy = -230 - lvl * 15;
            }
          }
        } else {
          if (input.current.flap) {
            birdV = -270;
            input.current.flap = false;
          }
          birdV += 760 * dt;
          bird += birdV * dt;
          pipeX -= (155 + Math.min(scoreRef.current * 3, 65)) * dt;
          if (!passed && pipeX + 64 < 137) {
            passed = true;
            add(1);
          }
          if (pipeX < -64) {
            pipeX = 620;
            gap = 110 + random(260);
            passed = false;
          }
          if (
            bird < 13 ||
            bird > H - 13 ||
            (pipeX < 163 &&
              pipeX + 64 > 137 &&
              (bird - 13 < gap - 84 || bird + 13 > gap + 84))
          )
            end();
        }
      }
      if (playing || !wasPlaying) draw();
      if (phaseRef.current === "playing") frame = requestAnimationFrame(loop);
    };
    draw();
    const wake = () => {
      last = 0;
      wasPlaying = false;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(loop);
    };
    const observer = new MutationObserver(wake);
    observer.observe(c, { attributes: true, attributeFilter: ["data-phase"] });
    wake();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [kind]);
  const move = (d: Direction) => {
    if (input.current.queue.length < 2) input.current.queue.push(d);
  };
  return (
    <GameShell
      id={kind}
      phase={phase}
      setPhase={setPhase}
      score={score}
      best={best}
      onReset={onReset}
      controls={
        kind === "snake" ? (
          <Dpad onMove={move} />
        ) : kind === "flappy" ? (
          <Button
            className="sp-flap"
            onPointerDown={() => {
              input.current.flap = true;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") input.current.flap = true;
            }}
          >
            <ArrowUp />
            Fliegen
          </Button>
        ) : (
          <>
            <span className="sp-hint">↔</span>
            <span className="sp-hint">
              {"♥".repeat(lives)} · Level {level}
            </span>
          </>
        )
      }
    >
      <canvas
        ref={canvas}
        width={600}
        height={480}
        data-phase={phase}
        className="sp-canvas"
        aria-label={
          kind === "snake"
            ? "Snake-Spielfeld. Pfeiltasten oder Steuerkreuz."
            : kind === "breakout"
              ? "Breakout-Spielfeld. Paddle ziehen oder Pfeiltasten."
              : "Flappy-Spielfeld. Tippen oder Leertaste zum Fliegen."
        }
        onPointerDown={(e) => {
          if (kind === "flappy") input.current.flap = true;
          else if (kind === "breakout") {
            e.currentTarget.setPointerCapture(e.pointerId);
            input.current.x =
              ((e.clientX - e.currentTarget.getBoundingClientRect().left) *
                600) /
              e.currentTarget.getBoundingClientRect().width;
          }
        }}
        onPointerMove={(e) => {
          if (kind === "breakout" && (e.buttons || e.pointerType === "mouse"))
            input.current.x =
              ((e.clientX - e.currentTarget.getBoundingClientRect().left) *
                600) /
              e.currentTarget.getBoundingClientRect().width;
        }}
        onPointerUp={() => {
          input.current.x = null;
        }}
        onPointerCancel={() => {
          input.current.x = null;
        }}
      />
    </GameShell>
  );
}

function Memory() {
  const [phase, setPhase] = useState<Phase>("ready"),
    [cards, setCards] = useState(() =>
      shuffle([...Array(8).keys(), ...Array(8).keys()]),
    ),
    [open, setOpen] = useState<number[]>([]),
    [matched, setMatched] = useState<number[]>([]),
    [moves, setMoves] = useState(0),
    [best, saveBest] = useBest("memory", true);
  const symbols = ["●", "■", "▲", "◆", "✦", "✚", "○", "◇"];
  useEffect(() => {
    if (open.length !== 2 || phase !== "playing") return;
    const timeout = setTimeout(() => {
      if (cards[open[0]] === cards[open[1]]) {
        const next = [...matched, ...open];
        setMatched(next);
        if (next.length === 16) {
          saveBest(moves);
          setPhase("won");
        }
      }
      setOpen([]);
    }, 650);
    return () => clearTimeout(timeout);
  }, [open, phase, cards, matched, moves, saveBest]);
  const pick = (i: number) => {
    if (
      phase !== "playing" ||
      open.length === 2 ||
      open.includes(i) ||
      matched.includes(i)
    )
      return;
    if (open.length === 1) setMoves((m) => m + 1);
    setOpen([...open, i]);
  };
  return (
    <GameShell
      id="memory"
      phase={phase}
      setPhase={setPhase}
      score={moves}
      best={best}
      onReset={() => {
        setCards(shuffle([...Array(8).keys(), ...Array(8).keys()]));
        setMatched([]);
        setOpen([]);
        setMoves(0);
        setPhase("ready");
      }}
      progress={(matched.length / 16) * 100}
    >
      <div className="sp-grid sp-memory">
        {cards.map((v, i) => (
          <Button
            variant={matched.includes(i) ? "secondary" : "outline"}
            key={i}
            disabled={phase !== "playing" || matched.includes(i)}
            aria-label={
              matched.includes(i)
                ? `Paar ${v + 1} gefunden`
                : open.includes(i)
                  ? `Symbol ${v + 1}`
                  : `Karte ${i + 1} aufdecken`
            }
            className={
              open.includes(i) || matched.includes(i) ? "sp-revealed" : ""
            }
            onClick={() => pick(i)}
          >
            {open.includes(i) || matched.includes(i) ? (
              symbols[v]
            ) : (
              <span className="sp-card-back">·</span>
            )}
          </Button>
        ))}
      </div>
    </GameShell>
  );
}

export function slide2048(board: number[], dir: Direction) {
  const b = [...board];
  let gain = 0;
  for (let n = 0; n < 4; n++) {
    let ids = Array.from({ length: 4 }, (_, i) =>
      dir === "left" || dir === "right" ? n * 4 + i : i * 4 + n,
    );
    if (dir === "right" || dir === "down") ids.reverse();
    const vals = ids.map((i) => board[i]).filter(Boolean),
      out: number[] = [];
    for (let i = 0; i < vals.length; i++) {
      if (vals[i] === vals[i + 1]) {
        out.push(vals[i] * 2);
        gain += vals[i] * 2;
        i++;
      } else out.push(vals[i]);
    }
    ids.forEach((id, i) => (b[id] = out[i] || 0));
  }
  return { board: b, gain, changed: b.some((v, i) => v !== board[i]) };
}
function spawn(board: number[]) {
  const b = [...board],
    free = b.flatMap((v, i) => (v ? [] : [i]));
  if (free.length) b[free[random(free.length)]] = Math.random() < 0.9 ? 2 : 4;
  return b;
}
function Game2048() {
  const [board, setBoard] = useState(() => spawn(spawn(Array(16).fill(0)))),
    [score, setScore] = useState(0),
    [phase, setPhase] = useState<Phase>("ready"),
    [best, saveBest] = useBest("2048"),
    [undo, setUndo] = useState<{ board: number[]; score: number } | null>(null),
    [achieved, setAchieved] = useState(false);
  const move = (dir: Direction) => {
    if (phase !== "playing") return;
    const next = slide2048(board, dir);
    if (!next.changed) return;
    setUndo({ board, score });
    const b = spawn(next.board),
      s = score + next.gain;
    setBoard(b);
    setScore(s);
    saveBest(s);
    if (!achieved && b.includes(2048)) {
      setAchieved(true);
      setPhase("won");
    } else if (
      !(["left", "right", "up", "down"] as Direction[]).some(
        (d) => slide2048(b, d).changed,
      )
    )
      setPhase("over");
  };
  useKeys((key) => {
    if (arrows[key]) move(arrows[key]);
    if (key === "Escape")
      setPhase((p) =>
        p === "playing" ? "paused" : p === "paused" ? "playing" : p,
      );
  });
  return (
    <GameShell
      id="2048"
      phase={phase}
      setPhase={setPhase}
      score={score}
      best={best}
      onReset={() => {
        setBoard(spawn(spawn(Array(16).fill(0))));
        setScore(0);
        setUndo(null);
        setAchieved(false);
        setPhase("ready");
      }}
      controls={
        <>
          <Dpad onMove={move} />
          <Button
            variant="outline"
            size="icon"
            disabled={!undo || phase !== "playing"}
            aria-label="Letzten Zug zurücknehmen"
            onClick={() => {
              if (undo) {
                setBoard(undo.board);
                setScore(undo.score);
                setUndo(null);
              }
            }}
          >
            <Undo2 />
          </Button>
          {phase === "won" && (
            <Button onClick={() => setPhase("playing")}>Weiter zu 4096</Button>
          )}
        </>
      }
    >
      <Surface onSwipe={move}>
        <div
          className="sp-grid sp-numbers"
          role="group"
          aria-label="2048-Spielfeld"
        >
          {board.map((v, i) => (
            <div
              key={i}
              data-filled={!!v}
              style={
                v
                  ? {
                      background: `hsl(0 0% ${Math.max(12, 70 - Math.log2(v) * 5)}%)`,
                      color: Math.log2(v) < 5 ? "#080808" : "#fff",
                    }
                  : {}
              }
            >
              {v || ""}
            </div>
          ))}
        </div>
      </Surface>
    </GameShell>
  );
}

function Sprint() {
  const [phase, setPhase] = useState<Phase>("ready"),
    [count, setCount] = useState(0),
    [elapsed, setElapsed] = useState(0),
    [pos, setPos] = useState([50, 50]),
    [keyboard, setKeyboard] = useState(false);
  const [touchBest, saveTouchBest] = useBest("sprint", true);
  const [keyBest, saveKeyBest] = useBest("sprint-keyboard", true);
  const best = keyboard ? keyBest : touchBest;
  const saveBest = keyboard ? saveKeyBest : saveTouchBest;
  const elapsedRef = useRef(0);
  const clockStart = useRef(0);
  useEffect(() => {
    if (phase !== "playing") return;
    const start = performance.now() - elapsedRef.current;
    clockStart.current = start;
    const timer = setInterval(() => {
      elapsedRef.current = performance.now() - start;
      setElapsed(elapsedRef.current);
    }, 50);
    return () => {
      if (clockStart.current === start)
        elapsedRef.current = performance.now() - start;
      clearInterval(timer);
    };
  }, [phase]);
  const hit = () => {
    if (phase !== "playing") return;
    if (count === 19) {
      const final = performance.now() - clockStart.current;
      setElapsed(final);
      saveBest(Number((final / 1000).toFixed(2)));
      setPhase("won");
    }
    setCount((n) => n + 1);
    setPos([10 + random(80), 12 + random(76)]);
  };
  useKeys((key) => {
    if (key === " ") {
      if (phase === "ready") setKeyboard(true);
      else if (keyboard) hit();
    }
    if (key === "Escape")
      setPhase((p) =>
        p === "playing" ? "paused" : p === "paused" ? "playing" : p,
      );
  });
  return (
    <GameShell
      id="sprint"
      phase={phase}
      setPhase={setPhase}
      score={(elapsed / 1000).toFixed(2)}
      unit="s"
      best={best}
      progress={(count / 20) * 100}
      onReset={() => {
        setCount(0);
        setElapsed(0);
        clockStart.current = 0;
        elapsedRef.current = 0;
        setPos([50, 50]);
        setPhase("ready");
      }}
      controls={
        <>
          <span className="sp-hint">{count} / 20</span>
          <Button
            variant="outline"
            disabled={phase !== "ready"}
            onClick={() => setKeyboard(!keyboard)}
            aria-pressed={keyboard}
          >
            {keyboard ? "Leertaste" : "Touch / Maus"}
          </Button>
        </>
      }
    >
      <div className="sp-target-field">
        <Button
          size="icon"
          className="sp-target"
          disabled={phase !== "playing"}
          aria-label={`Ziel ${count + 1} treffen`}
          style={{
            left: (keyboard ? 50 : pos[0]) + "%",
            top: (keyboard ? 50 : pos[1]) + "%",
          }}
          onPointerDown={(e) => {
            e.preventDefault();
            hit();
          }}
          onClick={(e) => {
            if (e.detail === 0) hit();
          }}
        >
          ✚
        </Button>
      </div>
    </GameShell>
  );
}

export function mineNeighbors(index: number) {
  const r = Math.floor(index / 9),
    c = index % 9;
  return [-1, 0, 1].flatMap((dy) =>
    [-1, 0, 1].flatMap((dx) => {
      const nr = r + dy,
        nc = c + dx;
      return (dx || dy) && nr >= 0 && nr < 9 && nc >= 0 && nc < 9
        ? [nr * 9 + nc]
        : [];
    }),
  );
}
function Mines() {
  const [phase, setPhase] = useState<Phase>("ready"),
    [mines, setMines] = useState<number[]>([]),
    [revealed, setRevealed] = useState<number[]>([]),
    [flags, setFlags] = useState<number[]>([]),
    [flagMode, setFlagMode] = useState(false),
    [moves, setMoves] = useState(0),
    [best, saveBest] = useBest("mines", true);
  const reveal = (i: number, flag = false) => {
    if (phase !== "playing" || revealed.includes(i)) return;
    if (flag) {
      setFlags((f) =>
        f.includes(i)
          ? f.filter((v) => v !== i)
          : f.length < 10
            ? [...f, i]
            : f,
      );
      return;
    }
    if (flags.includes(i)) return;
    let bombs = mines;
    if (!bombs.length) {
      const safe = [i, ...mineNeighbors(i)];
      bombs = shuffle(
        Array.from({ length: 81 }, (_, n) => n).filter(
          (n) => !safe.includes(n),
        ),
      ).slice(0, 10);
      setMines(bombs);
    }
    setMoves(moves + 1);
    if (bombs.includes(i)) {
      setRevealed([...revealed, i]);
      setPhase("over");
      return;
    }
    const seen = new Set(revealed),
      stack = [i];
    while (stack.length) {
      const n = stack.pop()!;
      if (seen.has(n) || bombs.includes(n) || flags.includes(n)) continue;
      seen.add(n);
      if (!mineNeighbors(n).some((v) => bombs.includes(v)))
        stack.push(...mineNeighbors(n));
    }
    setRevealed([...seen]);
    if (seen.size === 71) {
      setPhase("won");
      saveBest(moves + 1);
    }
  };
  return (
    <GameShell
      id="mines"
      phase={phase}
      setPhase={setPhase}
      score={10 - flags.length}
      best={best ? `${best} Züge` : 0}
      onReset={() => {
        setMines([]);
        setRevealed([]);
        setFlags([]);
        setFlagMode(false);
        setMoves(0);
        setPhase("ready");
      }}
      progress={(revealed.filter((i) => !mines.includes(i)).length / 71) * 100}
      controls={
        <Button
          variant={flagMode ? "secondary" : "outline"}
          onClick={() => setFlagMode(!flagMode)}
          aria-pressed={flagMode}
          aria-label="Minen markieren umschalten"
        >
          <Flag />
          {flagMode ? "Markieren" : "Aufdecken"}
        </Button>
      }
    >
      <div
        className="sp-mines"
        role="group"
        aria-label="Minesweeper, 9 mal 9 Felder, 10 Minen"
      >
        {Array.from({ length: 81 }, (_, i) => {
          const open = revealed.includes(i),
            bomb = mines.includes(i) && (phase === "over" || phase === "won"),
            count = mineNeighbors(i).filter((n) => mines.includes(n)).length;
          return (
            <button
              key={i}
              className={open ? "sp-open" : ""}
              disabled={phase !== "playing"}
              aria-label={`Reihe ${Math.floor(i / 9) + 1}, Spalte ${(i % 9) + 1}: ${open ? count + " benachbarte Minen" : flags.includes(i) ? "markiert" : "verdeckt"}`}
              onClick={() => reveal(i, flagMode)}
              onContextMenu={(e) => {
                e.preventDefault();
                reveal(i, true);
              }}
            >
              {bomb ? (
                "✹"
              ) : flags.includes(i) ? (
                <Flag size={14} />
              ) : open ? (
                count || ""
              ) : (
                ""
              )}
            </button>
          );
        })}
      </div>
    </GameShell>
  );
}

export function toggleLights(board: boolean[], index: number) {
  return board.map((v, i) =>
    i === index ||
    (Math.floor(i / 5) === Math.floor(index / 5) &&
      Math.abs(i - index) === 1) ||
    Math.abs(i - index) === 5
      ? !v
      : v,
  );
}
function makeLights() {
  let board = Array(25).fill(false);
  shuffle(Array.from({ length: 25 }, (_, i) => i))
    .slice(0, 10)
    .forEach((i) => (board = toggleLights(board, i)));
  return board.some(Boolean) ? board : toggleLights(board, 12);
}
function Lights() {
  const [board, setBoard] = useState(makeLights),
    [phase, setPhase] = useState<Phase>("ready"),
    [moves, setMoves] = useState(0),
    [best, saveBest] = useBest("lights", true),
    [history, setHistory] = useState<boolean[][]>([]);
  const pick = (i: number) => {
    if (phase !== "playing") return;
    const next = toggleLights(board, i);
    setHistory((h) => [...h.slice(-99), board]);
    setBoard(next);
    setMoves(moves + 1);
    if (!next.some(Boolean)) {
      saveBest(moves + 1);
      setPhase("won");
    }
  };
  return (
    <GameShell
      id="lights"
      phase={phase}
      setPhase={setPhase}
      score={moves}
      best={best}
      onReset={() => {
        setBoard(makeLights());
        setHistory([]);
        setMoves(0);
        setPhase("ready");
      }}
      controls={
        <>
          <span className="sp-hint">Alle Lichter aus · ✚</span>
          <Button
            variant="outline"
            size="icon"
            disabled={!history.length || phase !== "playing"}
            aria-label="Letzten Zug zurücknehmen"
            onClick={() => {
              setBoard(history[history.length - 1]);
              setHistory((h) => h.slice(0, -1));
              setMoves((m) => Math.max(0, m - 1));
            }}
          >
            <Undo2 />
          </Button>
        </>
      }
    >
      <div
        className="sp-lights"
        role="group"
        aria-label="Lights Out, 5 mal 5 Lichter"
      >
        {board.map((on, i) => (
          <Button
            key={i}
            variant="outline"
            disabled={phase !== "playing"}
            aria-pressed={on}
            aria-label={`Licht Reihe ${Math.floor(i / 5) + 1}, Spalte ${(i % 5) + 1}: ${on ? "an" : "aus"}`}
            className={on ? "sp-light-on" : ""}
            onClick={() => pick(i)}
          >
            <span />
          </Button>
        ))}
      </div>
    </GameShell>
  );
}

export default function Singleplayer({ game }: { game: string }) {
  const [round, setRound] = useState(0);
  const valid = singleplayerCatalog.some((g) => g.id === game);
  return (
    <div className="singleplayer" key={game}>
      <div className="sp-local">
        <HardDrive size={12} />
        <span>Offline · auf deinem Gerät</span>
      </div>
      <div key={`${game}:${round}`}>
        {!valid ? (
          <p>Spiel nicht gefunden.</p>
        ) : game === "snake" || game === "breakout" || game === "flappy" ? (
          <Arcade kind={game} onReset={() => setRound((r) => r + 1)} />
        ) : game === "memory" ? (
          <Memory />
        ) : game === "2048" ? (
          <Game2048 />
        ) : game === "sprint" ? (
          <Sprint />
        ) : game === "mines" ? (
          <Mines />
        ) : (
          <Lights />
        )}
      </div>
    </div>
  );
}
