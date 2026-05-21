import { useState, useCallback, useEffect } from "react";
import { Lock, PanelLeftClose, PanelLeft, Workflow } from "lucide-react";
import { useProfiles } from "./hooks/useProfiles";
import { useWorkflows } from "./hooks/useWorkflows";
import { api, setOnUnauthorized, type ProfileCreateData, type WorkflowRun } from "./lib/api";
import { ProfileList } from "./components/ProfileList";
import { ProfileForm } from "./components/ProfileForm";
import { ProfileViewer } from "./components/ProfileViewer";
import { LaunchButton } from "./components/LaunchButton";
import { StatusIndicator } from "./components/StatusIndicator";
import { LoginPage } from "./components/LoginPage";
import { WorkflowList } from "./components/WorkflowList";
import { WorkflowEditor } from "./components/WorkflowEditor";
import { WorkflowRunDetail } from "./components/WorkflowRunDetail";

type AuthState = "checking" | "required" | "ok" | "error";
type View = "empty" | "create" | "edit" | "view";
type Tab = "profiles" | "workflows";

export default function App() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [authRequired, setAuthRequired] = useState(false);

  useEffect(() => {
    setOnUnauthorized(() => setAuthState("required"));

    api.authStatus()
      .then(({ auth_required, authenticated }) => {
        setAuthRequired(auth_required);
        if (!auth_required || authenticated) {
          setAuthState("ok");
        } else {
          setAuthState("required");
        }
      })
      .catch((err) => {
        console.warn("[auth] status check failed:", err);
        setAuthState("error");
      });

    return () => setOnUnauthorized(null);
  }, []);

  if (authState === "checking") {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  if (authState === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-0">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Unable to reach the server</p>
          <button
            onClick={() => {
              setAuthState("checking");
              api.authStatus()
                .then(({ auth_required, authenticated }) => {
                  setAuthRequired(auth_required);
                  setAuthState(!auth_required || authenticated ? "ok" : "required");
                })
                .catch(() => setAuthState("error"));
            }}
            className="text-xs text-gray-400 hover:text-gray-200 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (authState === "required") {
    return <LoginPage onSuccess={() => setAuthState("ok")} />;
  }

  return (
    <AppContent
      authRequired={authRequired}
      onLogout={async () => {
        await api.logout();
        setAuthState("required");
      }}
    />
  );
}

interface AppContentProps {
  authRequired: boolean;
  onLogout: () => void;
}

function AppContent({ authRequired, onLogout }: AppContentProps) {
  const { profiles, loading, error, create, update, remove, launch, stop } = useProfiles();
  const { workflows, create: createWorkflow, update: updateWorkflow, remove: removeWorkflow, run: runWorkflow } = useWorkflows();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("empty");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [tab, setTab] = useState<Tab>("profiles");

  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [workflowView, setWorkflowView] = useState<"list" | "edit" | "run">("list");
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);

  const selected = profiles.find((p) => p.id === selectedId) ?? null;
  const selectedWorkflow = workflows.find((w) => w.id === selectedWorkflowId) ?? null;

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    const profile = profiles.find((p) => p.id === id);
    setView(profile?.status === "running" ? "view" : "edit");
  }, [profiles]);

  const handleNew = useCallback(() => {
    setSelectedId(null);
    setView("create");
  }, []);

  const handleCreate = useCallback(async (data: ProfileCreateData) => {
    const profile = await create(data);
    if (profile) {
      setSelectedId(profile.id);
      setView("edit");
    }
  }, [create]);

  const handleUpdate = useCallback(async (data: ProfileCreateData) => {
    if (!selectedId) return;
    await update(selectedId, data);
  }, [selectedId, update]);

  const handleDelete = useCallback(async () => {
    if (!selectedId) return;
    await remove(selectedId);
    setSelectedId(null);
    setView("empty");
  }, [selectedId, remove]);

  const handleLaunch = useCallback(async () => {
    if (!selectedId) return;
    const result = await launch(selectedId);
    if (result) setView("view");
  }, [selectedId, launch]);

  const handleStop = useCallback(async () => {
    if (!selectedId) return;
    await stop(selectedId);
    setView("edit");
  }, [selectedId, stop]);

  const handleVncDisconnect = useCallback(() => {
    setView("edit");
  }, []);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r border-border bg-surface-1 flex-shrink-0 flex flex-col">
          <div className="flex border-b border-border">
            <button
              onClick={() => setTab("profiles")}
              className={`flex-1 px-3 py-2 text-xs font-medium ${tab === "profiles" ? "text-blue-400 border-b-2 border-blue-400" : "text-gray-500 hover:text-gray-300"}`}
            >
              Profiles
            </button>
            <button
              onClick={() => setTab("workflows")}
              className={`flex-1 px-3 py-2 text-xs font-medium flex items-center justify-center gap-1 ${tab === "workflows" ? "text-blue-400 border-b-2 border-blue-400" : "text-gray-500 hover:text-gray-300"}`}
            >
              <Workflow className="h-3 w-3" /> Workflows
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {tab === "profiles" ? (
              <ProfileList
                profiles={profiles}
                selectedId={selectedId}
                onSelect={handleSelect}
                onNew={handleNew}
              />
            ) : (
              <WorkflowList
                workflows={workflows}
                selectedId={selectedWorkflowId}
                onSelect={(id) => { setSelectedWorkflowId(id); setWorkflowView("edit"); }}
                onNew={() => { setSelectedWorkflowId(null); setWorkflowView("edit"); }}
                onRun={async (id) => {
                  const result = await runWorkflow(id);
                  if (result) setSelectedRun(result);
                }}
                onDelete={(id) => removeWorkflow(id)}
              />
            )}
          </div>
        </div>
      )}

      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-500 hover:text-gray-300 p-1"
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </button>
            {selected && (
              <div className="flex items-center gap-2">
                <StatusIndicator status={selected.status} size="md" />
                <span className="text-sm font-medium">{selected.name}</span>
                <span className="text-xs text-gray-500 capitalize">{selected.platform}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selected && (
              <LaunchButton
                status={selected.status}
                onLaunch={handleLaunch}
                onStop={handleStop}
              />
            )}
            {authRequired && (
              <button
                onClick={onLogout}
                className="text-gray-500 hover:text-gray-300 p-1"
                title="Log out"
              >
                <Lock className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {tab === "workflows" && workflowView === "edit" && (
            <WorkflowEditor
              workflow={selectedWorkflow}
              profiles={profiles}
              onSave={async (data) => {
                if (selectedWorkflow) {
                  return await updateWorkflow(selectedWorkflow.id, data);
                } else {
                  const created = await createWorkflow(data);
                  if (created) {
                    setSelectedWorkflowId(created.id);
                  }
                  return created;
                }
              }}
              onRun={async (id) => {
                const result = await runWorkflow(id);
                if (result) {
                  setSelectedRun(result);
                }
                return result;
              }}
              onCancel={() => { setSelectedWorkflowId(null); setWorkflowView("list"); }}
            />
          )}

          {tab === "workflows" && selectedRun && (
            <WorkflowRunDetail
              run={selectedRun}
              onClose={() => setSelectedRun(null)}
            />
          )}

          {tab === "profiles" && view === "empty" && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-gray-500 text-sm">Select a profile or create a new one</p>
              </div>
            </div>
          )}

          {tab === "profiles" && view === "create" && (
            <ProfileForm
              profile={null}
              onSave={handleCreate}
              onCancel={() => setView("empty")}
            />
          )}

          {tab === "profiles" && view === "edit" && selected && (
            <ProfileForm
              profile={selected}
              onSave={handleUpdate}
              onDelete={handleDelete}
              onCancel={() => {
                setSelectedId(null);
                setView("empty");
              }}
            />
          )}

          {tab === "profiles" && view === "view" && selected && selected.status === "running" && (
            <ProfileViewer
              key={selected.id}
              profileId={selected.id}
              cdpUrl={selected.cdp_url}
              clipboardSync={selected.clipboard_sync}
              onDisconnect={handleVncDisconnect}
            />
          )}
        </div>
      </div>
    </div>
  );
}
