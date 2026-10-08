"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import TaskCard from "@/components/task-card";
import { deleteTask, fetchTasks, patchTask } from "@/lib/api";
import { Task, TaskStatus } from "@/types/task";

const columns: Array<{ key: TaskStatus; title: string }> = [
  { key: "todo", title: "To Do" },
  { key: "in_progress", title: "In Progress" },
  { key: "done", title: "Done" },
];

export default function BoardPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTasks() {
      try {
        const data = await fetchTasks();
        setTasks(data);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to load tasks.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    loadTasks();
  }, []);

  const groupedTasks = useMemo(() => {
    return {
      todo: tasks.filter((task) => task.status === "todo"),
      in_progress: tasks.filter((task) => task.status === "in_progress"),
      done: tasks.filter((task) => task.status === "done"),
    };
  }, [tasks]);

  async function handleStatusChange(taskId: number, status: TaskStatus) {
    setError(null);
    try {
      const updated = await patchTask(taskId, { status });
      setTasks((current) => current.map((task) => (task.id === taskId ? updated : task)));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to update task status.";
      setError(message);
    }
  }

  async function handleDelete(taskId: number) {
    setError(null);
    try {
      await deleteTask(taskId);
      setTasks((current) => current.filter((task) => task.id !== taskId));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to delete task.";
      setError(message);
    }
  }

  return (
    <section>
      <div className="mb-6 flex items-center justify-between gap-4">
        <Link
          href="/tasks/new"
          className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          &larr; Extract More Tasks
        </Link>

        {loading ? <p className="text-sm text-slate-600">Loading tasks...</p> : null}
      </div>

      {error ? <p className="mb-4 text-sm font-medium text-red-600">{error}</p> : null}

      <div className="grid gap-5 md:grid-cols-3">
        {columns.map((column) => (
          <div key={column.key} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-3 border-b border-slate-200 pb-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
                {column.title}
              </h2>
            </div>

            <div className="space-y-3">
              {groupedTasks[column.key].map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onStatusChange={handleStatusChange}
                  onDelete={handleDelete}
                />
              ))}

              {groupedTasks[column.key].length === 0 ? (
                <p className="rounded-md border border-dashed border-slate-300 bg-white px-3 py-6 text-center text-xs text-slate-500">
                  No tasks
                </p>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
