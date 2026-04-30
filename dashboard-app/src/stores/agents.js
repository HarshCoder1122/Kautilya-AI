import { defineStore } from 'pinia'
import { Agents } from '@/lib/api'

export const useAgents = defineStore('agents', {
  state: () => ({
    items: [],
    loaded: false,
    loading: false,
    error: null,
  }),
  getters: {
    byId: (s) => (id) => s.items.find((a) => a.id === id || a.agent_id === id),
  },
  actions: {
    async fetch(force = false) {
      if (this.loaded && !force) return this.items
      this.loading = true; this.error = null
      try {
        const data = await Agents.list()
        this.items = (data?.agents || data || []).map((a) => ({ ...a, id: a.id || a.agent_id }))
        this.loaded = true
        return this.items
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const res = await Agents.create(payload)
      await this.fetch(true)
      return res
    },
    async update(id, payload) {
      await Agents.update(id, payload)
      await this.fetch(true)
    },
    async remove(id) {
      await Agents.remove(id)
      this.items = this.items.filter((a) => a.id !== id)
    },
  },
})
