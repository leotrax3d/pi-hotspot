import { useCallback, useEffect, useMemo, useState } from "react";
import "@fontsource-variable/jetbrains-mono";
import {
  Clock3,
  Globe2,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { action } from "./api";
import type { Confirm } from "./controls";
import { Pane } from "./controls";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

type ActivityEvent = { time: number; ip: string; mac: string; domain: string };
type ActivityData = {
  events: ActivityEvent[];
  top: { domain: string; count: number }[];
  hours: number;
  retention_hours: number;
  enabled?:boolean;
  total: number;
};

export function WebActivity({ confirm }: { confirm: Confirm }) {
  const [data, setData] = useState<ActivityData | null>(null),
    [hours, setHours] = useState("24"),
    [query, setQuery] = useState(""),
    [loading, setLoading] = useState(true);
  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        setData(
          await action<ActivityData>("web_activity", { hours: Number(hours) }),
        );
      } catch (e) {
        toast.error((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [hours],
  );
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(true), 15000);
    return () => clearInterval(id);
  }, [load]);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (
      data?.events.filter(
        (e) =>
          !needle ||
          e.domain.includes(needle) ||
          e.ip.includes(needle) ||
          e.mac.toLowerCase().includes(needle),
      ) ?? []
    );
  }, [data, query]);
  const formatDate = (stamp: number) =>
    new Intl.DateTimeFormat("de-DE", {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(stamp * 1000);
  const clear = () =>
    confirm(
      "Webaktivität löschen?",
      "Alle bisher sichtbaren Einträge werden aus der Ansicht entfernt. Neue DNS-Anfragen erscheinen anschließend wieder.",
      async () => {
        await action("clear_web_activity");
        await load();
        toast.success("Webaktivität gelöscht");
      },
    );
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1>Webaktivität</h1>{data?.enabled===false&&<p>DNS-Logging ist deaktiviert. Aktivierung: sudo pi-hotspot configure</p>}
          <p>Aufgerufene Domains im Gastnetz</p>
        </div>
        <Badge variant="outline">
          <Globe2 />
          {data?.total ?? 0} Anfragen
        </Badge>
      </div>
      <Alert>
        <ShieldAlert />
        <AlertDescription>
          SchülerWLAN protokolliert DNS-Domains, keine vollständigen
          HTTPS-Adressen, Seiteninhalte oder Suchbegriffe. Geräte mit
          verschlüsseltem oder eigenem DNS können Einträge umgehen. Informiere
          die Nutzer über diese Protokollierung.
        </AlertDescription>
      </Alert>
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Domain, IP oder MAC suchen"
            aria-label="Webaktivität durchsuchen"
          />
        </div>
        <Select value={hours} onValueChange={setHours}>
          <SelectTrigger className="w-[170px]" aria-label="Zeitraum">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">Letzte Stunde</SelectItem>
            <SelectItem value="24">Letzte 24 Stunden</SelectItem>
            <SelectItem value="168">Letzte 7 Tage</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCw
            data-icon="inline-start"
            className={loading ? "animate-spin" : ""}
          />
          Aktualisieren
        </Button>
        <Button variant="ghost" onClick={clear} disabled={!data?.events.length}>
          <Trash2 data-icon="inline-start" />
          Verlauf löschen
        </Button>
      </div>
      {loading && !data ? (
        <>
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-72 w-full" />
        </>
      ) : (
        <>
          <div className="settings-grid">
            <Pane
              title="Häufigste Domains"
              description="DNS-Anfragen im gewählten Zeitraum."
            >
              {data?.top.length ? (
                <div className="flex flex-col gap-3">
                  {data.top.slice(0, 6).map((item, index) => (
                    <div
                      className="flex items-center gap-3 text-sm"
                      key={item.domain}
                    >
                      <span className="w-5 text-xs text-muted-foreground">
                        {index + 1}
                      </span>
                      <span className="min-w-0 flex-1 truncate">
                        {item.domain}
                      </span>
                      <Badge variant="secondary">{item.count}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted-copy">Noch keine Domains erfasst.</p>
              )}
            </Pane>
            <Pane
              title="Speicherung"
              description="Lokal auf diesem SchülerWLAN."
            >
              <div className="feature-list">
                <div>
                  <Clock3 />
                  <span>Maximal 7 Tage abrufbar</span>
                </div>
                <div>
                  <Globe2 />
                  <span>{data?.total ?? 0} DNS-Anfragen im Zeitraum</span>
                </div>
                <div>
                  <ShieldAlert />
                  <span>Keine vollständigen HTTPS-Inhalte</span>
                </div>
              </div>
              <p className="muted-copy">
                Die Anzeige wird alle 15 Sekunden aktualisiert. „Verlauf
                löschen“ setzt den sichtbaren Verlauf sofort zurück.
              </p>
            </Pane>
          </div>
          <Pane
            title="Aufgerufene Domains"
            description={
              query
                ? `${visible.length} passende Einträge`
                : "Neueste Einträge zuerst"
            }
          >
            {visible.length ? (
              <div
                className="max-h-[560px] overflow-auto rounded-lg border bg-zinc-950 p-2 text-[11px] leading-5 text-zinc-300 shadow-inner"
                style={{ fontFamily: '"JetBrains Mono Variable", "JetBrains Mono", monospace' }}
                role="log"
                aria-label="DNS-Aktivitätslog"
              >
                {visible.map((event, index) => (
                  <div
                    className="grid min-w-[780px] grid-cols-[150px_120px_155px_1fr] gap-3 border-b border-white/[.045] px-2 py-0.5 hover:bg-white/[.055]"
                    key={`${event.time}-${event.ip}-${event.domain}-${index}`}
                  >
                    <span className="text-zinc-500">{formatDate(event.time)}</span>
                    <span className="text-cyan-400">{event.ip}</span>
                    <span className="text-amber-300/80">{event.mac || "--:--:--:--:--:--"}</span>
                    <span className="break-all text-emerald-400">{event.domain}</span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty>
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Globe2 />
                  </EmptyMedia>
                  <EmptyTitle>
                    {query ? "Keine Treffer" : "Noch keine Webaktivität"}
                  </EmptyTitle>
                  <EmptyDescription>
                    {query
                      ? "Passe den Suchbegriff oder Zeitraum an."
                      : "Sobald ein verbundenes Gerät eine Domain über SchülerWLAN auflöst, erscheint sie hier."}
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </Pane>
        </>
      )}
    </div>
  );
}
