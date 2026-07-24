import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Dashboard } from '../components/Dashboard'

export function HomePage() {
  const [tasks, setTasks] = useState([])

  const refreshTasks = useCallback(() => {
    api.listTasks().then(setTasks).catch(() => {})
  }, [])

  useEffect(() => {
    refreshTasks()
  }, [refreshTasks])

  async function handleCreateTask(task) {
    const created = await api.createTask(task)
    setTasks((prev) => [...prev, created])
  }

  async function handleToggleTask(id) {
    const updated = await api.toggleTask(id)
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleDeleteTask(id) {
    await api.deleteTask(id)
    setTasks((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <Dashboard
      tasks={tasks}
      onCreateTask={handleCreateTask}
      onToggleTask={handleToggleTask}
      onDeleteTask={handleDeleteTask}
    />
  )
}
