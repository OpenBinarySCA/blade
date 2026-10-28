import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTaskStore = defineStore('task', () => {
  const currentTaskId = ref(null)
  const taskHistory = ref([])

  function setCurrentTask(taskId) {
    currentTaskId.value = taskId
    if (!taskHistory.value.includes(taskId)) {
      taskHistory.value.unshift(taskId)
      // Keep only last 10 tasks
      if (taskHistory.value.length > 10) {
        taskHistory.value = taskHistory.value.slice(0, 10)
      }
    }
  }

  function clearCurrentTask() {
    currentTaskId.value = null
  }

  return {
    currentTaskId,
    taskHistory,
    setCurrentTask,
    clearCurrentTask
  }
}, {
  persist: true
})
