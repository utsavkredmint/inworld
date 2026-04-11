const API_BASE = "http://45.195.83.136:8001/api/dashboard";
const VOICES_BASE = "http://45.195.83.136:8001/api/voices";

export interface AgentPayload {
  name: string;
  greeting: string;
  system_prompt: string;
  persona?: string;
  voice?: string;
  language?: string;
}

export interface Agent {
  id: string;
  name: string;
  greeting: string;
  system_prompt: string;
  persona: string;
  voice: string;
  language: string;
  status: string;
  created_at: string;
  updated_at: string;
  total_calls: number;
}

export interface Campaign {
  id: string;
  name: string;
  agent_id: string;
  agent_name: string;
  status: 'running' | 'paused' | 'completed';
  total_contacts: number;
  completed_contacts: number;
  failed_contacts: number;
  success_rate: string;
  created_at: string;
}

export interface CampaignContact {
  phone_number: string;
  name?: string;
}

export interface Voice {
  id: string;
  name: string;
  ref_audio_path: string;
  ref_text: string;
  created_at: string;
}


export interface Call {
  id: string;
  agent_id: string;
  agent_name: string;
  call_uuid: string;
  phone_number: string;
  direction: string;
  status: string;
  duration_sec: number;
  recording_url: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  message_count: number;
  metadata: string;
}

export interface Message {
  id: number;
  call_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

export interface CallDetail extends Call {
  messages: Message[];
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  // Agents
  listAgents: () => request<{ agents: Agent[] }>("/agents").then((r) => r.agents),

  createAgent: (data: AgentPayload) =>
    request<Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),

  getAgent: (id: string) => request<Agent>(`/agents/${id}`),

  updateAgent: (id: string, data: AgentPayload) =>
    request<Agent>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteAgent: (id: string) =>
    request<{ status: string }>(`/agents/${id}`, { method: "DELETE" }),

  // Calls
  triggerCall: (agentId: string, phoneNumber: string) =>
    request<Call>("/calls", {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, phone_number: phoneNumber }),
    }),

  listCalls: (agentId?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (agentId) params.set("agent_id", agentId);
    return request<{ calls: Call[]; total: number }>(`/calls?${params}`);
  },

  getCall: (id: string) => request<CallDetail>(`/calls/${id}`),

  getRecordingUrl: (id: string) => `${API_BASE}/calls/${id}/recording`,

  // Campaigns
  listCampaigns: () => request<{ campaigns: Campaign[] }>("/campaigns").then((r) => r.campaigns),

  createCampaign: (data: { name: string; agent_id: string; contacts: CampaignContact[] }) =>
    request<Campaign>("/campaigns", { method: "POST", body: JSON.stringify(data) }),

  updateCampaignStatus: (id: string, status: string) =>
    request<{ status: string }>(`/campaigns/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) }),

  deleteCampaign: (id: string) =>
    request<{ status: string }>(`/campaigns/${id}`, { method: "DELETE" }),

  // Voices
  listVoices: () =>
    fetch(VOICES_BASE).then(res => res.json()) as Promise<Voice[]>,

  cloneVoice: (name: string, file: File, refText?: string, language?: string) => {
    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);
    if (refText) formData.append("ref_text", refText);
    if (language) formData.append("language", language);
    return fetch(`${VOICES_BASE}/clone`, {
      method: "POST",
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error("Failed to clone voice");
      return res.json() as Promise<Voice>;
    });
  },

  deleteVoice: (id: string) =>
    fetch(`${VOICES_BASE}/${id}`, { method: "DELETE" }).then(res => res.json()),

  async testVoice(id: string, text?: string, language?: string) {
    const params = new URLSearchParams();
    if (text) params.append('text', text);
    if (language) params.append('language', language);
    
    const response = await fetch(`${VOICES_BASE}/${id}/test?${params.toString()}`);
    if (!response.ok) throw new Error('Generation failed');
    return response.blob();
  }
};
