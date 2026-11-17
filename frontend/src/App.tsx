import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  AnimatePresence,
  MotionConfig,
  motion,
  useReducedMotion,
} from "motion/react";
import {
  Activity,
  Check,
  ChevronRight,
  CircleAlert,
  Globe2,
  Grid2X2,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Moon,
  Radio,
  Settings2,
  Shield,
  SlidersHorizontal,
  Sun,
  Users,
  Wifi,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Separator } from "@/components/ui/separator";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Login, Logo } from "./Login";
const Dashboard = lazy(() =>
  import("./Dashboard").then((m) => ({ default: m.Dashboard })),
);
import type { TrafficPoint } from "./Dashboard";
const Guests = lazy(() =>
  import("./Guests").then((m) => ({ default: m.Guests })),
);
const WebActivity = lazy(() =>
  import("./Activity").then((m) => ({ default: m.WebActivity })),
);
const Internet = lazy(() =>
  import("./Wifi").then((m) => ({ default: m.Wifi })),
);
const Settings = lazy(() =>
  import("./Settings").then((m) => ({ default: m.Settings })),
);
const Matrix = lazy(() =>
  import("./Features").then((m) => ({ default: m.Matrix })),
);
const SecurityBase = lazy(() =>
  import("./Features").then((m) => ({ default: m.Security })),
);
const VPN = lazy(() => import("./Features").then((m) => ({ default: m.VPN })));
import { action, api, authState } from "./api";
import type { Auth, Config, Status } from "./api";
import type { Confirm } from "./controls";

function Security({ confirm, onLogout }: { confirm: Confirm; onLogout: () => void }) {
  return location.hash === "#activity" ? (
    <WebActivity confirm={confirm} />
  ) : (
    <SecurityBase confirm={confirm} onLogout={onLogout} />
  );
}

const links = [
  { id: "overview", label: "Übersicht", icon: LayoutDashboard },
  { id: "wifi", label: "Internet", icon: Wifi },
  { id: "guests", label: "Gäste & Codes", icon: Users },
  { id: "activity", label: "Webaktivität", icon: Globe2 },
  { id: "vpn", label: "Mullvad VPN", icon: Shield },
  { id: "matrix", label: "LED-Matrix", icon: Grid2X2 },
  { id: "settings", label: "Einstellungen", icon: SlidersHorizontal },
  { id: "security", label: "Sicherheit", icon: KeyRound },
];
type Confirmation = {
  title: string;
  description: string;
  run: () => Promise<void>;
};
function Navigation({
  route,
  navigate,
  logout,
  hostname,
  features,
}: {
  route: string;
  navigate: (r: string) => void;
  logout: () => void;
  hostname: string;
  features: Record<string,boolean>;
}) {
  const { setOpenMobile } = useSidebar();
  return (
    <Sidebar className="qspot-sidebar">
      <SidebarHeader>
        <a
          href="#overview"
          className="sidebar-brand"
          onClick={(e) => {
            e.preventDefault();
            navigate("overview");
            setOpenMobile(false);
          }}
        >
          <Logo />
        </a>
        <Badge variant="outline" className="sidebar-device">
          <Radio />
          {hostname}
        </Badge>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Router</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {links.filter(link=>link.id!=="matrix"&&(link.id!=="vpn"||features.vpn!==false)).map((link) => (
                <SidebarMenuItem key={link.id}>
                  <SidebarMenuButton isActive={route === link.id} asChild>
                    <a
                      href={"#" + link.id}
                      onClick={(e) => {
                        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
                          return;
                        e.preventDefault();
                        navigate(link.id);
                        setOpenMobile(false);
                      }}
                    >
                      <link.icon />
                      <span>{link.label}</span>
                    </a>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <Separator />
        <div className="sidebar-user">
          <div className="admin-monogram">Q</div>
          <div>
            <strong>Administrator</strong>
            <span>Lokaler Zugang</span>
          </div>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Abmelden"
            onClick={logout}
          >
            <LogOut />
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
function App() {
  const [auth, setAuth] = useState<Auth | null>(null),
    [config, setConfig] = useState<Config | null>(null),
    [status, setStatus] = useState<Status | null>(null),
    [error, setError] = useState(""),
    [history, setHistory] = useState<TrafficPoint[]>([]),
    [route, setRoute] = useState(() => location.hash.slice(1) || "overview"),
    [confirming, setConfirming] = useState<Confirmation | null>(null),
    [confirmBusy, setConfirmBusy] = useState(false),
    [dirty, setDirty] = useState(false),
    [dark, setDark] = useState(
      () => localStorage.getItem("qspot-theme") !== "light",
    );
  const reduced = useReducedMotion(),
    keyboard = useRef(false);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    localStorage.setItem("qspot-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const keys = () => {
        keyboard.current = true;
      },
      pointer = () => {
        keyboard.current = false;
      };
    window.addEventListener("keydown", keys);
    window.addEventListener("pointerdown", pointer);
    return () => {
      window.removeEventListener("keydown", keys);
      window.removeEventListener("pointerdown", pointer);
    };
  }, []);
  useEffect(() => {
    void authState()
      .then(setAuth)
      .catch((e) => setError((e as Error).message));
  }, []);
  const refresh = useCallback(async () => {
    const s = await api<Status>("/api/admin/status");
    setStatus(s);
    setError("");
    if (s.rates[s.uplink_interface||'eth0']) {
      const w = s.rates[s.uplink_interface||'eth0'];
      setHistory((h) =>
        [
          ...h,
          {
            time: new Intl.DateTimeFormat(undefined, {
              timeStyle: "medium",
            }).format(new Date()),
            down: (w.rx_Bps * 8) / 1000000,
            up: (w.tx_Bps * 8) / 1000000,
          },
        ].slice(-40),
      );
    }
  }, []);
  const refreshConfig = useCallback(async () => {
    setConfig(await api<Config>("/api/admin/config"));
  }, []);
  useEffect(() => {
    if (!auth?.authenticated) return;
    let live = true;
    void Promise.all([api<Config>("/api/admin/config"), refresh()])
      .then(([c]) => {
        if (!live) return;
        setConfig(c);
      })
      .catch((e) => setError((e as Error).message));
    const id = setInterval(
      () =>
        void refresh().catch((e) => {
          setError((e as Error).message);
          if ((e as Error & { status?: number }).status === 401) {
            setAuth((a) => (a ? { ...a, authenticated: false } : a));
            setStatus(null);
            setConfig(null);
          }
        }),
      3000,
    );
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [auth?.authenticated, refresh]);
  const confirm: Confirm = (title, description, run) =>
    setConfirming({ title, description, run });
  function navigate(next: string) {
    const go = () => {
      setRoute(next);
      location.hash = next;
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    if (dirty && next !== route) {
      confirm(
        "Änderungen verwerfen?",
        "Dein Entwurf wurde noch nicht auf dem Router gespeichert.",
        async () => {
          setDirty(false);
          go();
        },
      );
    } else go();
  }
  useEffect(() => {
    const hash = () => {
      const next = location.hash.slice(1) || "overview";
      if (links.some((x) => x.id === next)) setRoute(next);
    };
    window.addEventListener("hashchange", hash);
    return () => window.removeEventListener("hashchange", hash);
  }, []);
  async function logout() {
    try {
      await api("/api/logout", {});
      setAuth(await authState());
      setStatus(null);
      setConfig(null);
      setHistory([]);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  async function saveConfig(c: Config) {
    await action("apply", { config: c });
    setConfig(await api<Config>("/api/admin/config"));
    setDirty(false);
    await refresh();
  }
  async function confirmNetwork() {
    await action("confirm");
    await refresh();
    toast.success("Verbindung bestätigt. Einstellungen bleiben aktiv.");
  }
  async function executeConfirm() {
    if (!confirming) return;
    setConfirmBusy(true);
    try {
      await confirming.run();
      setConfirming(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setConfirmBusy(false);
    }
  }
  const current = links.find((x) => x.id === route) || links[0];
  const body = !auth ? (
    <div className="boot-view">
      <Logo />
      {error ? (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <>
          <Spinner />
          <p>Verbindung zu deinem SchülerWLAN …</p>
        </>
      )}
    </div>
  ) : !auth.authenticated ? (
    <Login auth={auth} onLogin={setAuth} />
  ) : (
    <SidebarProvider>
      <Navigation
        route={route}
        navigate={navigate}
        logout={() => void logout()}
        hostname={config?.hostname || "SchülerWLAN"}
        features={config?.features||{}}
      />
      <SidebarInset>
        <a href="#main-content" className="skip-link">
          Zum Inhalt
        </a>
        <header className="app-header">
          <div className="flex items-center gap-3">
            <SidebarTrigger className="md:hidden" />
            <span className="header-parent">SchülerWLAN</span>
            <ChevronRight className="size-3 text-muted-foreground" />
            <span>{current.label}</span>
          </div>
          <div className="header-actions">
            {auth.simulation && <Badge variant="outline">Simulation</Badge>}
            <span className="header-live">
              <Activity />
              Live
            </span>
            <Button
              size="icon"
              variant="ghost"
              aria-label={
                dark ? "Hellen Modus aktivieren" : "Dunklen Modus aktivieren"
              }
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun /> : <Moon />}
            </Button>
          </div>
        </header>
        <main id="main-content" className="app-main">
          {error && (
            <Alert className="mb-5">
              <CircleAlert />
              <AlertTitle>Verbindung prüfen</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {status?.pending && (
            <Alert className="network-confirmation mb-6">
              <Settings2 />
              <AlertTitle>Erreichbarkeit bestätigen</AlertTitle>
              <AlertDescription>
                <span>
                  Die Änderung wird ohne Bestätigung automatisch zurückgerollt.
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      void confirmNetwork().catch((e) =>
                        toast.error((e as Error).message),
                      )
                    }
                  >
                    <Check data-icon="inline-start" />
                    Alles funktioniert
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void action("rollback")
                        .then(refreshConfig)
                        .then(refresh)
                        .catch((e) => toast.error((e as Error).message))
                    }
                  >
                    Zurückrollen
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}
          {!config || !status ? (
            <div className="page-stack">
              <Skeleton className="h-12 w-72" />
              <Skeleton className="h-64 w-full" />
              <div className="grid grid-cols-2 gap-5">
                <Skeleton className="h-48" />
                <Skeleton className="h-48" />
              </div>
            </div>
          ) : (
            <Suspense fallback={<Skeleton className="h-80 w-full" />}>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={route}
                  initial={
                    keyboard.current
                      ? false
                      : {
                          opacity: 0,
                          transform: reduced ? "none" : "translateY(5px)",
                        }
                  }
                  animate={{ opacity: 1, transform: "translateY(0px)" }}
                  exit={{ opacity: 0 }}
                  transition={{
                    duration: keyboard.current ? 0 : 0.16,
                    ease: [0.23, 1, 0.32, 1],
                  }}
                >
                  {route === "overview" ? (
                    <Dashboard
                      refreshConfig={refreshConfig}
                      status={status}
                      config={config}
                      history={history}
                      navigate={navigate}
                      confirm={confirm}
                      refresh={refresh}
                    />
                  ) : route === "wifi" ? (
                    <Internet status={status} refresh={refresh} />
                  ) : route === "guests" ? (
                    <Guests
                      status={status}
                      config={config}
                      refresh={refresh}
                      confirm={confirm}
                    />
                  ) : route === "vpn" ? (
                    <VPN
                      status={status}
                      config={config}
                      save={saveConfig}
                      refresh={refresh}
                    />
                  ) : route === "matrix" ? (
                    <Matrix
                      status={status}
                      config={config}
                      refreshConfig={refreshConfig}
                    />
                  ) : route === "settings" ? (
                    <Settings
                      config={config}
                      save={saveConfig}
                      confirm={confirm}
                      onDirty={setDirty}
                    />
                  ) : (
                    <Security
                      confirm={confirm}
                      onLogout={() => {
                        setAuth((a) =>
                          a ? { ...a, authenticated: false } : a,
                        );
                        setConfig(null);
                        setStatus(null);
                      }}
                    />
                  )}
                </motion.div>
              </AnimatePresence>
            </Suspense>
          )}
          <footer className="app-footer">
            <Logo compact />
            <span>SchülerWLAN</span>
            <span>UNO Q</span>
          </footer>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        {body}
        <Toaster theme={dark ? "dark" : "light"} position="bottom-right" />
        <Dialog
          open={!!confirming}
          onOpenChange={(v) => {
            if (!v && !confirmBusy) setConfirming(null);
          }}
        >
          <DialogContent showCloseButton={!confirmBusy}>
            <DialogHeader>
              <DialogTitle>{confirming?.title}</DialogTitle>
              <DialogDescription>{confirming?.description}</DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                disabled={confirmBusy}
                onClick={() => setConfirming(null)}
              >
                Abbrechen
              </Button>
              <Button
                disabled={confirmBusy}
                onClick={() => void executeConfirm()}
              >
                {confirmBusy ? <Spinner data-icon="inline-start" /> : null}
                {confirmBusy ? "Wird ausgeführt …" : "Bestätigen"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </TooltipProvider>
    </MotionConfig>
  );
}
export default App;
