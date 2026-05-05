<script setup>
import { ref, onMounted, computed } from 'vue'
import { Upload, Plus, Play, Pause, Trash2, Loader2, PhoneOutgoing, CheckCircle } from 'lucide-vue-next'
import { Campaigns } from '@/lib/api'
import { useAgents } from '@/stores/agents'
import { relativeTime } from '@/lib/format'

const agents = useAgents()
const campaigns = ref([])
const loading = ref(true)

const showUploadModal = ref(false)
const selectedAgentId = ref('')
const campaignName = ref('')
const selectedFile = ref(null)
const uploading = ref(false)
const uploadErr = ref('')

async function load() {
  loading.value = true
  try {
    if (!agents.loaded) await agents.fetch()
    const res = await Campaigns.list()
    campaigns.value = res?.campaigns || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onFileSelected(e) {
  selectedFile.value = e.target.files[0]
}

async function uploadCampaign() {
  if (!selectedAgentId.value || !selectedFile.value) {
    uploadErr.value = 'Please select an agent and a CSV file.'
    return
  }
  uploading.value = true
  uploadErr.value = ''
  
  const formData = new FormData()
  formData.append('agent_id', selectedAgentId.value)
  formData.append('name', campaignName.value || 'New Campaign')
  formData.append('file', selectedFile.value)
  
  try {
    await Campaigns.upload(formData)
    showUploadModal.value = false
    selectedFile.value = null
    campaignName.value = ''
    selectedAgentId.value = ''
    await load()
  } catch (e) {
    uploadErr.value = e.message
  } finally {
    uploading.value = false
  }
}

async function toggleStatus(camp) {
  try {
    if (camp.status === 'running') await Campaigns.pause(camp.id)
    else await Campaigns.start(camp.id)
    await load()
  } catch (e) { alert(e.message) }
}

async function remove(camp) {
  if (!confirm(`Delete campaign ${camp.name}?`)) return
  try {
    await Campaigns.remove(camp.id)
    await load()
  } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Campaigns</h1>
        <p class="text-sm text-ink-muted mt-1">Upload CSVs to start automated bulk outbound calling.</p>
      </div>
      <button class="btn btn-primary" @click="showUploadModal = true">
        <Plus :size="16"/> New Campaign
      </button>
    </header>

    <div v-if="loading" class="space-y-3">
      <div class="skeleton h-16 w-full"></div>
      <div class="skeleton h-16 w-full"></div>
    </div>
    
    <div v-else-if="campaigns.length === 0" class="card empty">
      <div class="empty-icon"><PhoneOutgoing :size="24"/></div>
      <h3 class="text-base font-semibold">No campaigns yet</h3>
      <p class="text-sm mb-4">Upload a CSV file containing phone numbers to start automated dialling.</p>
      <button class="btn btn-primary" @click="showUploadModal = true">Upload CSV</button>
    </div>

    <div v-else class="space-y-4">
      <div v-for="c in campaigns" :key="c.id" class="card p-5">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div class="flex-1 min-w-0">
            <h3 class="font-medium text-base flex items-center gap-2">
              {{ c.name }}
              <span class="pill" :class="c.status === 'running' ? 'pill-success' : (c.status === 'completed' ? 'pill-mono' : 'pill-warning')">
                <span v-if="c.status === 'running'" class="pulse-dot mr-1"></span>
                {{ c.status }}
              </span>
            </h3>
            <p class="text-xs text-ink-muted mt-1">
              Agent: {{ agents.byId(c.agent_id)?.name || c.agent_id }} • Created {{ relativeTime(c.created_timestamp) }}
            </p>
          </div>
          
          <div class="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end">
            <div class="text-right">
              <p class="text-sm font-semibold">{{ c.progress }} / {{ c.total }}</p>
              <p class="text-[10px] text-ink-muted uppercase tracking-wider">Dialed</p>
            </div>
            
            <div class="flex gap-2">
              <button class="btn btn-subtle" v-if="c.status !== 'completed'" @click="toggleStatus(c)">
                <Pause v-if="c.status === 'running'" :size="14"/>
                <Play v-else :size="14"/>
                {{ c.status === 'running' ? 'Pause' : 'Start' }}
              </button>
              <button class="btn btn-ghost text-red-500" @click="remove(c)">
                <Trash2 :size="14"/>
              </button>
            </div>
          </div>
        </div>
        
        <!-- Progress bar -->
        <div class="mt-4 bg-line h-1.5 rounded-full overflow-hidden">
          <div class="h-full bg-accent transition-all duration-500" :style="{ width: `${(c.progress/c.total)*100}%` }"></div>
        </div>
      </div>
    </div>

    <!-- Upload Modal -->
    <div v-if="showUploadModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadein">
      <div class="bg-surface border border-line rounded-xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col">
        <div class="p-5 border-b border-line flex items-center justify-between">
          <h2 class="text-lg font-semibold">New Campaign</h2>
          <button class="btn btn-ghost p-1" @click="showUploadModal = false" :disabled="uploading">✕</button>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="label">Campaign Name</label>
            <input v-model="campaignName" class="input" placeholder="E.g. Lead Gen Batch 1">
          </div>
          
          <div>
            <label class="label">Select Agent</label>
            <select v-model="selectedAgentId" class="select">
              <option value="" disabled>Choose an agent...</option>
              <option v-for="a in agents.items" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
          </div>
          
          <div>
            <label class="label">Upload CSV/Excel</label>
            <div class="border-2 border-dashed border-line rounded-lg p-6 text-center hover:bg-bg-subtle transition-colors relative cursor-pointer" :class="{'border-accent bg-accent/5': selectedFile}">
              <input type="file" accept=".csv" @change="onFileSelected" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" :disabled="uploading">
              <Upload v-if="!selectedFile" class="mx-auto text-ink-muted mb-2" :size="24"/>
              <CheckCircle v-else class="mx-auto text-success mb-2" :size="24"/>
              <p class="text-sm font-medium">{{ selectedFile ? selectedFile.name : 'Click to browse' }}</p>
              <p class="text-xs text-ink-muted mt-1">{{ selectedFile ? Math.round(selectedFile.size/1024)+' KB' : 'Only CSV files with a phone number column.' }}</p>
            </div>
          </div>
          
          <p v-if="uploadErr" class="text-red-400 text-xs">{{ uploadErr }}</p>
        </div>
        
        <div class="p-5 border-t border-line bg-bg-subtle flex justify-end gap-2">
          <button class="btn btn-ghost" @click="showUploadModal = false" :disabled="uploading">Cancel</button>
          <button class="btn btn-primary" @click="uploadCampaign" :disabled="uploading || !selectedFile || !selectedAgentId">
            <Loader2 v-if="uploading" class="animate-spin" :size="14"/>
            {{ uploading ? 'Uploading...' : 'Create Campaign' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
