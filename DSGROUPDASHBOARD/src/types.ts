export type NavItem =
  | 'Dashboard'
  | 'Assistants'
  | 'Voices'
  | 'Knowledge Bases'
  | 'Threads'
  | 'Contacts'
  | 'Campaigns'
  | 'Settings';

export interface Voice {
  id: string;
  name: string;
  ref_audio_path: string;
  ref_text: string;
  created_at: string;
}

export interface Assistant {
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
  kb?: string;
}

export interface Thread {
  id: string;
  agent_id: string;
  agent_name: string;
  phone_number: string;
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
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface Contact {
  id: string;
  name: string;
  phone: string;
  email: string;
  lastCall: string;
  tags: string[];
}
