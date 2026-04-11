import { 
  Megaphone, 
  Plus, 
  Play, 
  Pause, 
  BarChart2, 
  Users, 
  Phone,
  MoreVertical,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  AlertCircle,
  Upload,
  FileSpreadsheet,
  ArrowLeft,
  X,
  Check,
  Trash2,
  Database
} from 'lucide-react';
import { useState, useEffect, ChangeEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, Campaign, CampaignContact } from '@/src/lib/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const initialCampaigns: any[] = [];

export function Campaigns() {
  const [view, setView] = useState<'list' | 'create'>('list');
  const [campaignName, setCampaignName] = useState('');
  const [selectedAssistant, setSelectedAssistant] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [campaignList, setCampaignList] = useState<Campaign[]>([]);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [assistants, setAssistants] = useState<any[]>([]);
  const [contacts, setContacts] = useState<CampaignContact[]>([]);
  const [previewContacts, setPreviewContacts] = useState<CampaignContact[]>([]);

  useEffect(() => {
    api.listAgents()
      .then(agents => {
        if (Array.isArray(agents)) {
          setAssistants(agents);
          if (agents.length > 0) setSelectedAssistant(agents[0].id);
        }
      })
      .catch(err => {
        console.error("Failed to load assistants:", err);
      });
  }, []);

  useEffect(() => {
    api.listCampaigns()
      .then(setCampaignList)
      .catch(err => console.error("Failed to load campaigns:", err));
  }, [view]);

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = e.target.files?.[0];
    if (uploadedFile) {
      setFile(uploadedFile);
      const reader = new FileReader();
      
      if (uploadedFile.name.endsWith('.csv')) {
        reader.onload = (event) => {
          const text = event.target?.result as string;
          Papa.parse(text, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
              const parsed = results.data.map((row: any) => ({
                phone_number: String(row.phone_number || row.phone || row.Number || row.Mobile || ""),
                name: String(row.name || row.Name || row.Customer || "")
              })).filter((c: any) => c.phone_number);
              setContacts(parsed);
              setPreviewContacts(parsed.slice(0, 3));
            }
          });
        };
        reader.readAsText(uploadedFile);
      } else {
        reader.onload = (event) => {
          const data = new Uint8Array(event.target?.result as ArrayBuffer);
          const workbook = XLSX.read(data, { type: 'array' });
          const sheetName = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[sheetName];
          const json = XLSX.utils.sheet_to_json(worksheet);
          const parsed = json.map((row: any) => ({
            phone_number: String(row.phone_number || row.phone || row.Number || row.Mobile || ""),
            name: String(row.name || row.Name || row.Customer || "")
          })).filter((c: any) => c.phone_number);
          setContacts(parsed);
          setPreviewContacts(parsed.slice(0, 3));
        };
        reader.readAsArrayBuffer(uploadedFile);
      }
    }
  };

  const handleDelete = (id: string) => {
    setDeleteId(id);
  };

  const confirmDelete = () => {
    if (deleteId) {
      api.deleteCampaign(deleteId).then(() => {
        setCampaignList(prev => prev.filter(c => c.id !== deleteId));
        setDeleteId(null);
      });
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
            <h3 className="text-zinc-900 font-bold text-2xl">Create New Campaign</h3>
            <p className="text-zinc-500 text-sm">Configure your automated voice campaign</p>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 rounded-3xl p-8 space-y-8">
          {/* Campaign Name */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Campaign Name</label>
            <input 
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="e.g. Service Reminder Q2"
              className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
            />
          </div>

          {/* Select Assistant */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Select Agent (Assistant)</label>
            {assistants.length === 0 ? (
              <div className="p-4 bg-zinc-100 rounded-xl border border-dashed border-zinc-300 text-center">
                <p className="text-zinc-500 text-xs italic">No agents found. Please create an agent first.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {assistants.map((ast) => (
                  <button
                    key={ast.id}
                    onClick={() => setSelectedAssistant(ast.id)}
                    className={cn(
                      "p-4 rounded-xl border text-left transition-all flex items-center justify-between group",
                      selectedAssistant === ast.id 
                        ? "bg-orange-50 border-orange-500 ring-1 ring-orange-500" 
                        : "bg-white border-zinc-200 hover:border-zinc-300"
                    )}
                  >
                    <div>
                      <p className={cn("font-bold text-sm", selectedAssistant === ast.id ? "text-orange-900" : "text-zinc-900")}>{ast.name}</p>
                      <div className="flex items-center gap-2">
                        <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-tighter">{ast.type || "Voice"} Agent</p>
                        {ast.kb && (
                          <span className="flex items-center gap-1 text-[9px] font-bold text-orange-600 uppercase bg-orange-50 px-1.5 py-0.5 rounded">
                            <Database className="w-2 h-2" />
                            {ast.kb}
                          </span>
                        )}
                      </div>
                    </div>
                    {selectedAssistant === ast.id && <Check className="w-4 h-4 text-orange-500" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* File Upload */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Upload Contact Data (CSV/Excel)</label>
            <div className="relative">
              <input 
                type="file" 
                accept=".csv, .xlsx, .xls"
                onChange={handleFileUpload}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
              />
              <div className={cn(
                "border-2 border-dashed rounded-2xl p-12 flex flex-col items-center justify-center gap-4 transition-all",
                file ? "bg-emerald-50 border-emerald-200" : "bg-white border-zinc-200 hover:border-orange-200"
              )}>
                <div className={cn(
                  "w-16 h-16 rounded-full flex items-center justify-center",
                  file ? "bg-emerald-100 text-emerald-600" : "bg-orange-50 text-orange-500"
                )}>
                  {file ? <CheckCircle2 className="w-8 h-8" /> : <Upload className="w-8 h-8" />}
                </div>
                <div className="text-center">
                  <p className="font-bold text-zinc-900">{file ? file.name : "Click or drag file to upload"}</p>
                  <p className="text-xs text-zinc-500 mt-1">
                    {file ? `${(file.size / 1024).toFixed(2)} KB` : "Supports CSV, Excel (.xlsx, .xls)"}
                  </p>
                </div>
                {file && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="text-xs font-bold text-red-500 hover:text-red-600 flex items-center gap-1"
                  >
                    <X className="w-3 h-3" /> Remove file
                  </button>
                )}
              </div>
            </div>
            {previewContacts.length > 0 && (
              <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
                <div className="bg-zinc-100 px-4 py-2 border-b border-zinc-200">
                  <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Contact Preview (First 3)</p>
                </div>
                <div className="divide-y divide-zinc-100">
                  {previewContacts.map((c, i) => (
                    <div key={i} className="px-4 py-2.5 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-500 font-bold text-xs">
                          {c.name ? c.name[0] : '#'}
                        </div>
                        <div>
                          <p className="text-xs font-bold text-zinc-900">{c.name || "No Name"}</p>
                          <p className="text-[10px] text-zinc-500">{c.phone_number}</p>
                        </div>
                      </div>
                      <div className="px-2 py-0.5 bg-zinc-100 text-zinc-500 text-[9px] font-bold rounded uppercase">Pending</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <p className="text-[10px] text-zinc-400 italic">Selected agent will call one by one from this data automatically.</p>
          </div>

          <div className="pt-4">
            <button 
              disabled={!campaignName || !selectedAssistant || contacts.length === 0}
              onClick={() => {
                api.createCampaign({
                  name: campaignName,
                  agent_id: selectedAssistant,
                  contacts: contacts
                }).then(() => {
                  setView('list');
                  setCampaignName('');
                  setSelectedAssistant('');
                  setFile(null);
                  setContacts([]);
                  setPreviewContacts([]);
                }).catch(console.error);
              }}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-200 disabled:text-zinc-400 text-white py-4 rounded-xl font-bold text-lg transition-all shadow-lg shadow-orange-500/20 active:scale-[0.98]"
            >
              Launch Campaign
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
          <h3 className="text-zinc-900 font-semibold text-xl">Campaigns</h3>
          <p className="text-zinc-500 text-sm">Create and monitor automated voice call campaigns</p>
        </div>
        <button 
          onClick={() => setView('create')}
          className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-orange-500/20 active:scale-95"
        >
          <Plus className="w-5 h-5" />
          New Campaign
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-orange-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search campaigns..." 
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/50 focus:border-orange-500/50 transition-all"
          />
        </div>
        <button className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-zinc-400 hover:text-zinc-900 transition-all">
          <Filter className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <AnimatePresence mode="popLayout">
          {campaignList.map((camp, i) => {
            if (camp.type === 'bulk') {
              return (
                <motion.div
                  key={camp.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: i * 0.1 }}
                  layout
                  className="bg-white border border-zinc-200 rounded-3xl overflow-hidden hover:border-orange-500/30 transition-all group shadow-sm"
                >
                  <div className="p-6 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-orange-500 flex items-center justify-center text-white shadow-lg shadow-orange-500/20">
                        <Megaphone className="w-6 h-6" />
                      </div>
                      <div>
                        <h4 className="text-zinc-900 font-bold text-lg">{camp.name}</h4>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="text-xs text-zinc-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {camp.date}
                          </span>
                          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase rounded-full">
                            {camp.status}
                          </span>
                          {camp.kb && (
                            <span className="flex items-center gap-1 text-[10px] font-bold text-orange-600 uppercase bg-orange-50 px-2 py-0.5 rounded-full">
                              <Database className="w-2.5 h-2.5" />
                              {camp.kb}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="p-2 hover:bg-white rounded-lg text-zinc-400 hover:text-zinc-900 transition-colors border border-transparent hover:border-zinc-200">
                        <BarChart2 className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleDelete(camp.id)}
                        className="p-2 hover:bg-red-50 rounded-lg text-zinc-400 hover:text-red-600 transition-colors border border-transparent hover:border-red-100"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button className="p-2 hover:bg-white rounded-lg text-zinc-400 hover:text-zinc-900 transition-colors border border-transparent hover:border-zinc-200">
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="p-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                    <StatItem label="Total Contacts" value={camp.stats?.totalContacts} />
                    <StatItem label="Responded Users" value={camp.stats?.respondedUsers} highlight="emerald" />
                    <StatItem label="Attempted Calls" value={camp.stats?.attemptedCalls} />
                    <StatItem label="Failed Calls" value={camp.stats?.failedCalls} highlight="red" />
                    <StatItem label="Not Answered" value={camp.stats?.notAnswered} highlight="amber" />
                    <StatItem label="Blocked Calls" value={camp.stats?.blockedCalls} />
                    <StatItem label="Voicemail / Hold" value={camp.stats?.voicemailOnHold} />
                  </div>
                </motion.div>
              );
            }

            return (
              <motion.div
                key={camp.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: i * 0.1 }}
                layout
                className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl group hover:border-zinc-300 transition-all flex items-center gap-8"
              >
                <div className="w-12 h-12 rounded-xl bg-white border border-zinc-200 flex items-center justify-center shrink-0 group-hover:border-orange-500/50 transition-all">
                  <Megaphone className="w-6 h-6 text-orange-500" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <h4 className="text-zinc-900 font-bold text-lg truncate">{camp.name}</h4>
                    <div className={cn(
                      "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider",
                      camp.status === 'running' ? "bg-emerald-500/10 text-emerald-600" :
                      camp.status === 'paused' ? "bg-amber-500/10 text-amber-600" :
                      camp.status === 'completed' ? "bg-blue-500/10 text-blue-600" :
                      "bg-zinc-200 text-zinc-500"
                    )}>
                      {camp.status}
                    </div>
                  </div>
                  <p className="text-xs text-zinc-500 flex items-center gap-2">
                    <Users className="w-3 h-3" />
                    {camp.agent_name}
                    {camp.kb && (
                      <span className="flex items-center gap-1 text-orange-600 font-medium ml-2">
                        <Database className="w-3 h-3" />
                        {camp.kb}
                      </span>
                    )}
                  </p>
                </div>

                <div className="w-48 shrink-0">
                  <div className="flex justify-between text-[10px] font-bold text-zinc-500 uppercase mb-2">
                    <span>Progress</span>
                    <span>{Math.round((camp.completed_contacts / camp.total_contacts) * 100) || 0}%</span>
                  </div>
                  <div className="h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${(camp.completed_contacts / camp.total_contacts) * 100 || 0}%` }}
                      className="h-full bg-orange-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-8 shrink-0">
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Total Calls</p>
                    <p className="text-sm font-bold text-zinc-900">{camp.total_contacts?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Success Rate</p>
                    <p className="text-sm font-bold text-emerald-600">{camp.success_rate}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button 
                    onClick={() => {
                        const newStatus = camp.status === 'running' ? 'paused' : 'running';
                        api.updateCampaignStatus(camp.id, newStatus).then(() => {
                           api.listCampaigns().then(setCampaignList);
                        });
                    }}
                    className="p-2 bg-zinc-200 hover:bg-zinc-300 text-zinc-600 rounded-lg transition-all"
                  >
                    {camp.status === 'running' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>
                  <button className="p-2 bg-zinc-200 hover:bg-zinc-300 text-zinc-600 rounded-lg transition-all">
                    <BarChart2 className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => handleDelete(camp.id)}
                    className="p-2 hover:bg-red-50 rounded-lg text-zinc-400 hover:text-red-600 transition-colors border border-transparent hover:border-red-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button className="p-2 bg-zinc-200 hover:bg-zinc-300 text-zinc-600 rounded-lg transition-all">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            );
          })}
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
                <h4 className="text-xl font-bold text-zinc-900">Delete Campaign?</h4>
                <p className="text-zinc-500 text-sm">
                  This action cannot be undone. All data associated with this campaign will be permanently removed.
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
    </div>
  );
}

function StatItem({ label, value, highlight }: { label: string; value?: number; highlight?: 'emerald' | 'amber' | 'red' }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] text-zinc-400 font-bold uppercase tracking-tighter leading-tight">{label}</p>
      <p className={cn(
        "text-lg font-bold",
        highlight === 'emerald' ? "text-emerald-600" :
        highlight === 'amber' ? "text-amber-600" :
        highlight === 'red' ? "text-red-600" :
        "text-zinc-900"
      )}>
        {value ?? 0}
      </p>
    </div>
  );
}
