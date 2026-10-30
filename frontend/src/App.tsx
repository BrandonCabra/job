import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type Application, type Job, type Task } from "./api";

type View = "jobs" | "applications";

const terminalTaskStates = new Set(["completed", "failed"]);

function App() {
  const [view, setView] = useState<View>("jobs");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [loadedJobs, loadedApplications] = await Promise.all([
        api.jobs(),
        api.applications()
      ]);
      setJobs(loadedJobs);
      setApplications(loadedApplications);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cargar la API.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const active = Object.values(tasks).filter((task) => !terminalTaskStates.has(task.status));
    if (!active.length) return;
    const timer = window.setInterval(() => {
      void Promise.all(active.map((task) => api.task(task.id)))
        .then((updated) => {
          setTasks((current) => ({
            ...current,
            ...Object.fromEntries(updated.map((task) => [task.id, task]))
          }));
          if (updated.some((task) => terminalTaskStates.has(task.status))) void loadData();
        })
        .catch((reason) => setError(reason instanceof Error ? reason.message : "Falló una tarea."));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [tasks, loadData]);

  async function enqueue(jobId: string, type: "evaluate-task" | "documents-task") {
    setError("");
    try {
      const task = await api.enqueue(jobId, type);
      setTasks((current) => ({ ...current, [task.id]: task }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo encolar la tarea.");
    }
  }

  async function updateApplication(application: Application, status: string) {
    try {
      const updated = await api.updateApplication(application.id, status);
      setApplications((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo actualizar la candidatura.");
    }
  }

  const completedTasks = useMemo(
    () => Object.values(tasks).filter((task) => task.status === "completed").length,
    [tasks]
  );

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">JOB AGENT / PANEL LOCAL</p>
          <h1>Tu próxima oportunidad, organizada.</h1>
          <p className="subtitle">Evalúa ofertas, genera documentos y revisa cada candidatura sin perder trazabilidad.</p>
        </div>
        <button className="secondary-button" onClick={() => void loadData()} disabled={busy}>
          {busy ? "Cargando..." : "Actualizar"}
        </button>
      </header>

      <section className="metrics">
        <Metric label="Ofertas disponibles" value={jobs.length} />
        <Metric label="Candidaturas" value={applications.length} />
        <Metric label="Tareas completadas" value={completedTasks} />
        <Metric label="Revisión humana" value="Activa" accent />
      </section>

      {error && <div className="alert">{error}</div>}

      <nav className="tabs" aria-label="Secciones">
        <button className={view === "jobs" ? "tab active" : "tab"} onClick={() => setView("jobs")}>Ofertas</button>
        <button className={view === "applications" ? "tab active" : "tab"} onClick={() => setView("applications")}>Candidaturas</button>
      </nav>

      {view === "jobs" ? (
        <section className="content-grid">
          <div className="section-heading">
            <div><p className="eyebrow">CATÁLOGO</p><h2>Ofertas recientes</h2></div>
            <span className="muted">{jobs.length} resultados</span>
          </div>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} tasks={tasks} onEnqueue={enqueue} />
          ))}
          {!busy && jobs.length === 0 && <Empty text="No hay ofertas en SQLite." />}
        </section>
      ) : (
        <ApplicationsView applications={applications} onUpdate={updateApplication} />
      )}
    </main>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: number | string; accent?: boolean }) {
  return <article className={accent ? "metric accent" : "metric"}><span>{label}</span><strong>{value}</strong></article>;
}

function JobCard({ job, tasks, onEnqueue }: { job: Job; tasks: Record<string, Task>; onEnqueue: (id: string, type: "evaluate-task" | "documents-task") => Promise<void> }) {
  const related = Object.values(tasks).filter((task) => task.job_id === job.id);
  const latest = related.at(-1);
  return (
    <article className="job-card">
      <div className="job-main">
        <div className="job-icon">{job.company.slice(0, 1).toUpperCase()}</div>
        <div><span className="tag">{job.source}</span><h3>{job.title}</h3><p className="company">{job.company} · {job.location || "Ubicación no especificada"}</p></div>
      </div>
      <p className="description">{job.description.slice(0, 220)}{job.description.length > 220 ? "…" : ""}</p>
      <div className="job-actions">
        <a href={job.url} target="_blank" rel="noreferrer">Ver oferta ↗</a>
        <button onClick={() => void onEnqueue(job.id, "evaluate-task")} disabled={latest?.status === "running" || latest?.status === "queued"}>Evaluar</button>
        <button className="primary-button" onClick={() => void onEnqueue(job.id, "documents-task")} disabled={latest?.status === "running" || latest?.status === "queued"}>Generar documentos</button>
      </div>
      {latest && <TaskBadge task={latest} />}
    </article>
  );
}

function TaskBadge({ task }: { task: Task }) {
  const result = task.result;
  return <div className={`task ${task.status}`}><span>{task.status}</span>{task.error && <small>{task.error}</small>}{typeof result.score === "number" && <small>Score: {result.score}</small>}{typeof result.pdf_path === "string" && <a href={api.documentUrl(result.pdf_path)} target="_blank" rel="noreferrer">Abrir PDF</a>}</div>;
}

function ApplicationsView({ applications, onUpdate }: { applications: Application[]; onUpdate: (application: Application, status: string) => Promise<void> }) {
  return <section className="content-grid"><div className="section-heading"><div><p className="eyebrow">SEGUIMIENTO</p><h2>Mis candidaturas</h2></div><span className="muted">{applications.length} registros</span></div>{applications.map((application) => <article className="application-card" key={application.id}><div><span className="tag">{application.status}</span><h3>{application.title}</h3><p className="company">{application.company} · Score {application.score}</p><p className="muted">{application.step}</p></div><div className="application-actions"><a href={application.url} target="_blank" rel="noreferrer">Oferta ↗</a>{application.status !== "Enviada" && <button className="primary-button" onClick={() => void onUpdate(application, "Enviada")}>Marcar enviada</button>}{application.status !== "Rechazada" && <button onClick={() => void onUpdate(application, "Rechazada")}>Rechazar</button>}</div></article>)}{applications.length === 0 && <Empty text="Aún no hay candidaturas registradas." />}</section>;
}

function Empty({ text }: { text: string }) { return <div className="empty">{text}</div>; }

export default App;
