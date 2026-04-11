import { 
  Bot, 
  MoreVertical, 
  Plus, 
  Activity, 
  Globe, 
  Calendar, 
  Phone,
  Search,
  Filter,
  Play,
  Settings as SettingsIcon,
  Trash2,
  X,
  ArrowLeft,
  Check,
  Database
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { Assistant } from '@/src/types';
import { api } from '@/src/lib/api';

const knowledgeBases: any[] = [];

export function Assistants() {
  const [view, setView] = useState<'list' | 'create'>('list');
  const [assistantList, setAssistantList] = useState<Assistant[]>([]);
  const [voices, setVoices] = useState<any[]>([]);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Call trigger
  const [callAgentId, setCallAgentId] = useState<string | null>(null);
  const [callPhone, setCallPhone] = useState('+91');
  const [callStatus, setCallStatus] = useState('');

  // Form State
  const [agentName, setAgentName] = useState('');
  const [initialMessage, setInitialMessage] = useState('');
  const [agentPersona, setAgentPersona] = useState('');
  const [llmPrompt, setLlmPrompt] = useState('');
  const [selectedVoice, setSelectedVoice] = useState<string>('Riya');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('hi');
  const [selectedKB, setSelectedKB] = useState<string>('');
  const [kbSearch, setKbSearch] = useState('');

  const filteredKBs = knowledgeBases.filter(kb =>
    kb.name.toLowerCase().includes(kbSearch.toLowerCase())
  );

  // Load agents from API
  const loadAgents = async () => {
    try {
      const agents = await api.listAgents();
      setAssistantList(agents as any);
    } catch (e) {
      console.error('Failed to load agents:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadVoices = async () => {
    try {
      const data = await api.listVoices();
      setVoices(data);
    } catch (e) {
      console.log('Failed to load voices:', e);
    }
  };

  useEffect(() => { 
    loadAgents(); 
    loadVoices();
  }, []);

  const handleDelete = (id: string) => {
    setDeleteId(id);
  };

  const confirmDelete = async () => {
    if (deleteId) {
      try {
        await api.deleteAgent(deleteId);
        setAssistantList(prev => prev.filter(a => a.id !== deleteId));
      } catch (e) {
        console.error('Delete failed:', e);
      }
      setDeleteId(null);
    }
  };

  const handleEdit = (bot: Assistant) => {
    setEditingId(bot.id);
    setAgentName(bot.name);
    setInitialMessage(bot.greeting);
    setAgentPersona(bot.persona || '');
    setLlmPrompt(bot.system_prompt);
    setSelectedVoice(bot.voice || 'Riya');
    setSelectedLanguage(bot.language || 'hi');
    setView('create');
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        name: agentName,
        greeting: initialMessage,
        system_prompt: llmPrompt,
        persona: agentPersona,
        voice: selectedVoice,
        language: selectedLanguage,
      };

      if (editingId) {
        const updated = await api.updateAgent(editingId, payload);
        setAssistantList(prev => prev.map(a => a.id === editingId ? updated : a));
      } else {
        const agent = await api.createAgent(payload);
        setAssistantList([agent as any, ...assistantList]);
      }

      setView('list');
      resetForm();
    } catch (e) {
      console.error('Operation failed:', e);
    }
  };

  const resetForm = () => {
    setEditingId(null);
    setAgentName('');
    setInitialMessage('');
    setAgentPersona('');
    setLlmPrompt('');
    setSelectedVoice('Riya');
    setSelectedLanguage('hi');
    setSelectedKB('');
  };

  const handleTriggerCall = async () => {
    if (!callAgentId || callPhone.length < 10) return;
    setCallStatus('Calling...');
    try {
      await api.triggerCall(callAgentId, callPhone);
      setCallStatus('Call triggered!');
      setTimeout(() => { setCallAgentId(null); setCallStatus(''); setCallPhone('+91'); }, 2000);
      loadAgents(); // Refresh call counts
    } catch (e: any) {
      setCallStatus('Failed: ' + e.message);
    }
  };

  if (view === 'create') {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-8 overflow-y-auto h-full bg-white">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setView('list')}
            className="p-2 hover:bg-zinc-100 rounded-full transition-colors text-zinc-500 hover:text-zinc-900"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <div>
            <h3 className="text-zinc-900 font-bold text-2xl">{editingId ? 'Edit Assistant' : 'Create New Assistant'}</h3>
            <p className="text-zinc-500 text-sm">{editingId ? 'Update your assistant configuration' : "Configure your AI voice agent's personality and behavior"}</p>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 rounded-3xl p-8 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Agent Name */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Agent Name</label>
              <input 
                type="text"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="e.g. किया Service Center Bot"
                className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
              />
            </div>

            {/* Initial Message */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Initial Message</label>
              <input 
                type="text"
                value={initialMessage}
                onChange={(e) => setInitialMessage(e.target.value)}
                placeholder="e.g. नमस्कार, मैं किया Service Center से बात कर रहा हूँ..."
                className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
              />
            </div>
          </div>

          {/* Agent Persona */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Agent Persona</label>
            <textarea 
              value={agentPersona}
              onChange={(e) => setAgentPersona(e.target.value)}
              placeholder="Describe the agent's personality, tone, and role..."
              rows={3}
              className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all resize-none"
            />
          </div>

          {/* Voice Selection */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Select Voice</label>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setSelectedVoice('Riya')}
                className={cn(
                  "px-4 py-3 rounded-xl border text-sm font-medium transition-all flex items-center justify-between",
                  selectedVoice === 'Riya' ? "bg-orange-500 text-white border-orange-600" : "bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300"
                )}
              >
                <span>Riya (Default)</span>
                {selectedVoice === 'Riya' && <Check className="w-4 h-4" />}
              </button>
              {voices.map(v => (
                <div key={v.id} className="relative group">
                  <button
                    type="button"
                    onClick={() => setSelectedVoice(v.id)}
                    className={cn(
                      "w-full px-4 py-3 rounded-xl border text-sm font-medium transition-all flex items-center justify-between pr-10",
                      selectedVoice === v.id ? "bg-orange-500 text-white border-orange-600 shadow-md shadow-orange-500/20" : "bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300"
                    )}
                  >
                    <span className="truncate">{v.name}</span>
                    {selectedVoice === v.id && <Check className="w-4 h-4 shrink-0" />}
                  </button>
                  <button 
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      // Simple test audio trigger
                      api.testVoice(v.id, "Hello! testing this voice identity.", v.language || 'hindi');
                    }}
                    className={cn(
                      "absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-all",
                      selectedVoice === v.id ? "text-orange-200 hover:text-white hover:bg-white/10" : "text-zinc-400 hover:text-orange-500 hover:bg-orange-50"
                    )}
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                  </button>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-zinc-400">Choose between the standard AI voice or your custom cloned voices.</p>
          </div>

          {/* Language Selection */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Fixed Language</label>
            <div className="flex gap-3">
              {[
                { id: 'hi', name: 'Hindi' },
                { id: 'en', name: 'English' },
                { id: 'hinglish', name: 'Hinglish' }
              ].map(lang => (
                <button
                  key={lang.id}
                  type="button"
                  onClick={() => setSelectedLanguage(lang.id)}
                  className={cn(
                    "px-6 py-2.5 rounded-xl border text-sm font-medium transition-all flex items-center gap-2",
                    selectedLanguage === lang.id ? "bg-orange-500 text-white border-orange-600 shadow-md shadow-orange-500/20" : "bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300"
                  )}
                >
                  {lang.name}
                  {selectedLanguage === lang.id && <Check className="w-3.5 h-3.5" />}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-zinc-400">Lock the agent to a specific language to prevent accent mixing.</p>
          </div>

          {/* LLM Prompt */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">LLM Prompt</label>
              <span className="text-[10px] bg-orange-100 text-orange-600 px-2 py-0.5 rounded font-bold uppercase">Direct LLM Input</span>
            </div>
            <textarea 
              value={llmPrompt}
              onChange={(e) => setLlmPrompt(e.target.value)}
              placeholder="Enter the system prompt that will be directly fed into the LLM..."
              rows={6}
              className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all resize-none"
            />
            <p className="text-[10px] text-zinc-400 italic">This prompt defines the core logic and constraints of the AI's responses.</p>
          </div>

          {/* Connect Knowledge Base */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Connect Knowledge Base (Optional)</label>
              <div className="relative w-48">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-400" />
                <input 
                  type="text"
                  placeholder="Search KB..."
                  value={kbSearch}
                  onChange={(e) => setKbSearch(e.target.value)}
                  className="w-full bg-white border border-zinc-200 rounded-lg pl-7 pr-3 py-1.5 text-[10px] focus:outline-none focus:ring-1 focus:ring-orange-500"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
              <button
                onClick={() => setSelectedKB('')}
                className={cn(
                  "p-4 rounded-xl border text-left transition-all flex items-center justify-between group",
                  selectedKB === '' 
                    ? "bg-zinc-100 border-zinc-400 ring-1 ring-zinc-400" 
                    : "bg-white border-zinc-200 hover:border-zinc-300"
                )}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center",
                    selectedKB === '' ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-500"
                  )}>
                    <X className="w-4 h-4" />
                  </div>
                  <div>
                    <p className={cn("font-bold text-sm", selectedKB === '' ? "text-zinc-900" : "text-zinc-500")}>No Knowledge Base</p>
                    <p className="text-[10px] text-zinc-400">Agent will use only the system prompt</p>
                  </div>
                </div>
                {selectedKB === '' && <Check className="w-4 h-4 text-zinc-900" />}
              </button>

              {filteredKBs.map((kb) => (
                <button
                  key={kb.id}
                  onClick={() => setSelectedKB(kb.id)}
                  className={cn(
                    "p-4 rounded-xl border text-left transition-all flex items-center justify-between group",
                    selectedKB === kb.id 
                      ? "bg-orange-50 border-orange-500 ring-1 ring-orange-500" 
                      : "bg-white border-zinc-200 hover:border-zinc-300"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center",
                      selectedKB === kb.id ? "bg-orange-500 text-white" : "bg-zinc-100 text-zinc-500"
                    )}>
                      <Database className="w-4 h-4" />
                    </div>
                    <div>
                      <p className={cn("font-bold text-sm", selectedKB === kb.id ? "text-orange-900" : "text-zinc-900")}>{kb.name}</p>
                      <p className="text-[10px] text-zinc-400">Manual selection enabled</p>
                    </div>
                  </div>
                  {selectedKB === kb.id && <Check className="w-4 h-4 text-orange-500" />}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-zinc-400 italic">Select a source manually to provide the agent with specific context and data.</p>
          </div>

          <div className="pt-4">
            <button 
              disabled={!agentName || !llmPrompt}
              onClick={handleSubmit}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-200 disabled:text-zinc-400 text-white py-4 rounded-xl font-bold text-lg transition-all shadow-lg shadow-orange-500/20 active:scale-[0.98] flex items-center justify-center gap-2"
            >
              <Check className="w-5 h-5" />
              {editingId ? 'Save Changes' : 'Create Assistant'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 overflow-y-auto h-full bg-white">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-zinc-900 font-semibold text-xl">Voice Assistants</h3>
          <p className="text-zinc-500 text-sm">Manage and monitor your AI voice agents</p>
        </div>
        <button 
          onClick={() => { resetForm(); setView('create'); }}
          className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-orange-500/20 active:scale-95"
        >
          <Plus className="w-5 h-5" />
          Create Assistant
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-orange-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search assistants..." 
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/50 focus:border-orange-500/50 transition-all"
          />
        </div>
        <button className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-zinc-400 hover:text-zinc-900 transition-all">
          <Filter className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <AnimatePresence mode="popLayout">
          {assistantList.map((bot, i) => (
            <motion.div
              key={bot.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ delay: i * 0.05 }}
              layout
              className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl group hover:border-zinc-300 transition-all"
            >
              <div className="flex items-start justify-between mb-6">
                <div className="w-12 h-12 rounded-xl bg-white border border-zinc-200 flex items-center justify-center group-hover:border-orange-500/50 transition-all">
                  <Bot className="w-6 h-6 text-orange-500" />
                </div>
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider",
                    bot.status === 'active' ? "bg-emerald-500/10 text-emerald-600" :
                    bot.status === 'training' ? "bg-blue-500/10 text-blue-600" :
                    "bg-zinc-200 text-zinc-500"
                  )}>
                    {bot.status}
                  </div>
                  <button className="p-1 text-zinc-400 hover:text-zinc-900 transition-colors">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <h4 className="text-zinc-900 font-bold text-lg mb-1">{bot.name}</h4>
              <div className="flex items-center gap-3 text-zinc-500 text-xs mb-6">
                <div className="flex items-center gap-1">
                  <Globe className="w-3 h-3" />
                  {bot.language}
                </div>
                <div className="w-1 h-1 rounded-full bg-zinc-200" />
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {bot.created_at ? new Date(bot.created_at).toLocaleDateString() : 'New'}
                </div>
                {bot.kb && (
                  <>
                    <div className="w-1 h-1 rounded-full bg-zinc-200" />
                    <div className="flex items-center gap-1 text-orange-600 font-medium">
                      <Database className="w-3 h-3" />
                      {bot.kb}
                    </div>
                  </>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-3 bg-white rounded-xl border border-zinc-200">
                  <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Total Calls</p>
                  <p className="text-sm font-bold text-zinc-900">{(bot.total_calls || 0).toLocaleString()}</p>
                </div>
                <div className="p-3 bg-white rounded-xl border border-zinc-200">
                  <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Success Rate</p>
                  <p className="text-sm font-bold text-zinc-900">84%</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button onClick={() => { setCallAgentId(bot.id); setCallPhone('+91'); setCallStatus(''); }} className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-white py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-all">
                  <Phone className="w-3 h-3" />
                  Call
                </button>
                <button 
                  onClick={() => handleEdit(bot)}
                  className="p-2 bg-zinc-200 hover:bg-zinc-300 text-zinc-600 rounded-lg transition-all"
                >
                  <SettingsIcon className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => handleDelete(bot.id)}
                  className="p-2 bg-zinc-200 hover:bg-rose-50 text-zinc-600 hover:text-rose-600 rounded-lg transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteId(null)}
              className="absolute inset-0 bg-zinc-900/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-zinc-200 p-8 space-y-6"
            >
              <div className="w-16 h-16 rounded-2xl bg-red-50 text-red-500 flex items-center justify-center mx-auto">
                <Trash2 className="w-8 h-8" />
              </div>
              
              <div className="text-center space-y-2">
                <h4 className="text-xl font-bold text-zinc-900">Delete Assistant?</h4>
                <p className="text-zinc-500 text-sm">
                  Are you sure you want to delete this assistant? This will remove all associated configurations and logs.
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteId(null)}
                  className="flex-1 px-6 py-3 rounded-xl font-bold text-zinc-600 hover:bg-zinc-100 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmDelete}
                  className="flex-1 px-6 py-3 rounded-xl font-bold bg-red-500 hover:bg-red-600 text-white transition-all shadow-lg shadow-red-500/20 active:scale-95"
                >
                  Delete
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Call Trigger Modal */}
      <AnimatePresence>
        {callAgentId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setCallAgentId(null)}
              className="absolute inset-0 bg-zinc-900/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-zinc-200 p-8 space-y-6"
            >
              <div className="w-16 h-16 rounded-2xl bg-orange-50 text-orange-500 flex items-center justify-center mx-auto">
                <Phone className="w-8 h-8" />
              </div>
              <div className="text-center space-y-2">
                <h4 className="text-xl font-bold text-zinc-900">Trigger Call</h4>
                <p className="text-zinc-500 text-sm">Enter the phone number to call with this agent</p>
              </div>
              <input
                type="tel"
                value={callPhone}
                onChange={(e) => setCallPhone(e.target.value)}
                placeholder="+91XXXXXXXXXX"
                className="w-full px-4 py-3 rounded-xl border border-zinc-300 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
              {callStatus && (
                <p className={cn("text-sm text-center font-medium", callStatus.includes('Failed') ? 'text-red-500' : 'text-green-600')}>{callStatus}</p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => setCallAgentId(null)}
                  className="flex-1 px-6 py-3 rounded-xl font-bold text-zinc-600 hover:bg-zinc-100 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={handleTriggerCall}
                  disabled={callPhone.length < 10}
                  className="flex-1 px-6 py-3 rounded-xl font-bold bg-orange-500 hover:bg-orange-600 text-white transition-all shadow-lg shadow-orange-500/20 active:scale-95 disabled:opacity-50"
                >
                  Call Now
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
