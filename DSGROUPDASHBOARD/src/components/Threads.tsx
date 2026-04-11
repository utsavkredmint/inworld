import { 
  Search, 
  Filter, 
  Clock, 
  User, 
  Bot,
  MoreVertical,
  Phone,
  Download,
  Lock,
  ExternalLink,
  ChevronRight,
  MessageSquare,
  FileText,
  History,
  Webhook
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, Call, Message } from '@/src/lib/api';

export function Threads() {
  console.log('[Threads] Component mounted - v2');
  const [conversationList, setConversationList] = useState<Call[]>([]);
  const [transcript, setTranscript] = useState<Message[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'messages' | 'notes'>('messages');
  const [isDownloading, setIsDownloading] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadCalls = () => {
    api.listCalls().then(r => {
      console.log('[Threads] Loaded calls:', r.calls.length);
      setConversationList(r.calls);
      setLoading(false);
    }).catch(e => {
      console.error('[Threads] Failed to load calls:', e);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadCalls();
    // Auto-refresh every 5 seconds
    const interval = setInterval(loadCalls, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-refresh transcript for selected conversation
  useEffect(() => {
    if (!selectedConversation) return;
    const refreshTranscript = async () => {
      try {
        const detail = await api.getCall(selectedConversation.id);
        setTranscript(detail.messages);
        // Update selected conversation with full details (including recording_url)
        setSelectedConversation((prev: any) => prev?.id === detail.id ? { ...prev, ...detail } : prev);
        // Update list
        setConversationList(prev => prev.map(c =>
          c.id === detail.id ? { ...c, status: detail.status, duration_sec: detail.duration_sec, message_count: detail.messages.length, recording_url: detail.recording_url } : c
        ));
      } catch {}
    };
    refreshTranscript();
    const interval = setInterval(refreshTranscript, 3000);
    return () => clearInterval(interval);
  }, [selectedConversation?.id]);

  const selectConversation = async (call: Call) => {
    setSelectedConversation(call);
    try {
      const detail = await api.getCall(call.id);
      setTranscript(detail.messages);
    } catch (e) {
      console.error('Failed to load transcript:', e);
    }
  };

  const handleDownload = () => {
    if (!selectedConversation?.recording_url) {
      alert('Recording not available for this call');
      return;
    }
    setIsDownloading(true);
    window.open(api.getRecordingUrl(selectedConversation.id), '_blank');
    setTimeout(() => setIsDownloading(false), 1000);
  };

  return (
    <div className="flex h-full bg-white overflow-hidden">
      {/* Left Sidebar: Conversation List */}
      <div className="w-80 border-r border-zinc-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-zinc-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-zinc-900 font-bold">Threads</h3>
            <span className="text-xs text-zinc-500 font-medium">({conversationList.length}) Calls</span>
          </div>
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
            <input 
              type="text" 
              placeholder="Search by Call ID or Phone..." 
              className="w-full bg-zinc-50 border border-zinc-200 rounded-lg pl-10 pr-4 py-2 text-xs text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500"
            />
          </div>
          <div className="flex gap-2">
            <button className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-zinc-100 text-zinc-900 rounded-md border border-zinc-200">All</button>
            <button className="flex-1 py-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-zinc-600 transition-colors">Assigned</button>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto divide-y divide-zinc-100">
          {(() => { console.log('[Threads] Render - conversationList.length:', conversationList.length); return null; })()}
          {conversationList.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-zinc-50 flex items-center justify-center">
                <Phone className="w-5 h-5 text-zinc-300" />
              </div>
              <p className="text-xs text-zinc-400 font-medium">No conversations found</p>
            </div>
          ) : (
            conversationList.map((item) => (
              <button
                key={item.id}
                onClick={() => selectConversation(item)}
                className={cn(
                  "w-full p-4 text-left hover:bg-zinc-50 transition-all group relative",
                  selectedConversation?.id === item.id && "bg-zinc-50 border-l-2 border-orange-500"
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className={cn("text-sm font-bold", selectedConversation?.id === item.id ? "text-zinc-900" : "text-zinc-500")}>{item.phone_number}</span>
                  <span className="text-[10px] text-zinc-400 font-medium">{item.duration_sec ? `${Math.floor(item.duration_sec/60)}m ${item.duration_sec%60}s` : '--'}</span>
                </div>
                <p className="text-xs text-zinc-500 truncate mb-2">{item.agent_name} | {item.message_count} messages</p>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-zinc-400 font-medium">{item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</span>
                  <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", item.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : item.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700')}>{item.status}</span>
                </div>
              </button>
            ))
          )}
          {conversationList.length > 0 && (
            <button className="w-full p-4 text-center text-xs font-bold text-orange-500 hover:text-orange-600 transition-colors">
              Load more conversations
            </button>
          )}
        </div>
      </div>

      {/* Middle: Transcript View */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        <div className="h-14 border-b border-zinc-200 flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-6">
            <button 
              onClick={() => setActiveTab('messages')}
              className={cn(
                "h-14 flex items-center gap-2 text-sm font-bold uppercase tracking-wider transition-all relative",
                activeTab === 'messages' ? "text-orange-600" : "text-zinc-400 hover:text-zinc-600"
              )}
            >
              <MessageSquare className="w-4 h-4" />
              Messages
              {activeTab === 'messages' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-orange-500" />}
            </button>
            <button 
              onClick={() => setActiveTab('notes')}
              className={cn(
                "h-14 flex items-center gap-2 text-sm font-bold uppercase tracking-wider transition-all relative",
                activeTab === 'notes' ? "text-orange-600" : "text-zinc-400 hover:text-zinc-600"
              )}
            >
              <FileText className="w-4 h-4" />
              Notes
              {activeTab === 'notes' && <motion.div layoutId="tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-orange-500" />}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={handleDownload}
              disabled={isDownloading}
              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-50 border border-zinc-200 rounded-lg text-xs font-bold text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-all disabled:opacity-50"
            >
              {isDownloading ? (
                <div className="w-3 h-3 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              {isDownloading ? "Securing..." : "Download Call"}
            </button>
            <div className="h-4 w-px bg-zinc-200 mx-1" />
            <span className="text-xs font-bold text-zinc-900">{selectedConversation?.contact || 'No selection'}</span>
            <button className="p-2 text-zinc-400 hover:text-zinc-900 transition-colors">
              <MoreVertical className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-zinc-50/30">
          {transcript.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-zinc-100 flex items-center justify-center">
                <MessageSquare className="w-8 h-8 text-zinc-300" />
              </div>
              <div>
                <p className="text-sm text-zinc-500 font-medium">No messages to display</p>
                <p className="text-xs text-zinc-400">Select a conversation to view the transcript</p>
              </div>
            </div>
          ) : (
            transcript.map((msg, i) => (
              <div key={i} className={cn("flex flex-col", msg.role === 'assistant' ? "items-start" : "items-end")}>
                <div className={cn(
                  "max-w-[70%] p-4 rounded-2xl text-sm leading-relaxed",
                  msg.role === 'assistant'
                    ? "bg-white text-zinc-800 border border-zinc-200 rounded-tl-none shadow-sm"
                    : "bg-orange-500 text-white rounded-tr-none shadow-lg shadow-orange-500/10"
                )}>
                  {msg.content}
                </div>
                <span className="text-[10px] text-zinc-400 font-medium mt-2 px-1">
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Sidebar: Details */}
      <div className="w-80 border-l border-zinc-200 flex flex-col shrink-0 bg-white">
        <div className="h-14 border-b border-zinc-200 flex items-center px-6 shrink-0">
          <h3 className="text-zinc-900 font-bold text-sm uppercase tracking-wider">Details</h3>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {!selectedConversation ? (
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-zinc-50 flex items-center justify-center">
                <Clock className="w-6 h-6 text-zinc-300" />
              </div>
              <p className="text-xs text-zinc-400 font-medium">Select a thread to view details</p>
            </div>
          ) : (
            <>
              {/* Recording Section */}
              <div className="p-4 bg-zinc-50 border border-zinc-200 rounded-xl flex flex-col items-center text-center space-y-3">
                {selectedConversation?.recording_url ? (
                  <>
                    <audio
                      controls
                      src={api.getRecordingUrl(selectedConversation.id)}
                      className="w-full"
                      preload="none"
                    />
                    <button
                      onClick={handleDownload}
                      className="w-full py-2 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-bold rounded-lg flex items-center justify-center gap-2 transition-all"
                    >
                      <Download className="w-4 h-4" />
                      Download Recording
                    </button>
                  </>
                ) : (
                  <div className="py-2 space-y-2">
                    <div className="w-10 h-10 rounded-full bg-white border border-zinc-200 flex items-center justify-center mx-auto">
                      <Phone className="w-5 h-5 text-zinc-300" />
                    </div>
                    <p className="text-xs text-zinc-400 font-medium">No recording available</p>
                  </div>
                )}
              </div>

              {/* Conversation Details */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Conversation Details</h4>
                <div className="space-y-3">
                  <DetailItem label="Call ID" value={selectedConversation.id} copyable />
                  <DetailItem label="Call UUID" value={selectedConversation.call_uuid || 'N/A'} copyable />
                  <DetailItem label="Phone Number" value={selectedConversation.phone_number || 'N/A'} />
                  <DetailItem label="Agent" value={selectedConversation.agent_name || 'N/A'} />
                  <DetailItem label="Status" value={selectedConversation.status || 'N/A'} />
                  <DetailItem label="Duration" value={selectedConversation.duration_sec ? `${Math.floor(selectedConversation.duration_sec / 60)}m ${selectedConversation.duration_sec % 60}s` : 'N/A'} />
                  <DetailItem label="Started" value={selectedConversation.started_at ? new Date(selectedConversation.started_at).toLocaleString() : 'N/A'} />
                  <DetailItem label="Ended" value={selectedConversation.ended_at ? new Date(selectedConversation.ended_at).toLocaleString() : 'N/A'} />
                  <DetailItem label="Messages" value={String(selectedConversation.message_count || transcript.length || 0)} />
                </div>
              </div>

              {/* Extraction Details (from metadata) */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Extraction Details</h4>
                {(() => {
                  try {
                    const meta = typeof selectedConversation.metadata === 'string'
                      ? JSON.parse(selectedConversation.metadata)
                      : selectedConversation.metadata;
                    if (meta && Object.keys(meta).length > 0) {
                      return (
                        <div className="space-y-2">
                          {Object.entries(meta).map(([key, val]: [string, any]) => (
                            <div key={key}>
                              <p className="text-[10px] font-bold text-zinc-500 uppercase mb-1">{key}</p>
                              {typeof val === 'object' && val !== null ? (
                                <div className="space-y-1">
                                  {Object.entries(val).map(([k, v]: [string, any]) => (
                                    <div key={k} className="flex justify-between p-2 bg-zinc-50 border border-zinc-200 rounded-lg">
                                      <span className="text-xs text-zinc-600">{k}</span>
                                      <span className="text-xs font-bold text-zinc-900">{v === null ? 'N/A' : String(v)}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <p className="text-xs text-zinc-600">{String(val)}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      );
                    }
                    return <p className="text-[10px] text-zinc-400 italic">No extraction data</p>;
                  } catch {
                    return <p className="text-[10px] text-zinc-400 italic">No extraction data</p>;
                  }
                })()}
              </div>

              {/* Call Info */}
              <div className="space-y-4">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">Call Info</h4>
                <div className="space-y-2">
                  <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-blue-600 uppercase bg-blue-500/10 px-1.5 py-0.5 rounded">Direction</span>
                    </div>
                    <p className="text-xs text-zinc-600">{selectedConversation.direction || 'outbound'}</p>
                  </div>
                  <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-emerald-600 uppercase bg-emerald-500/10 px-1.5 py-0.5 rounded">Created</span>
                    </div>
                    <p className="text-xs text-zinc-600">{selectedConversation.created_at ? new Date(selectedConversation.created_at).toLocaleString() : 'N/A'}</p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, value, copyable }: { label: string; value: string; copyable?: boolean }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] text-zinc-400 font-bold uppercase">{label}</p>
      <div className="flex items-center justify-between gap-2 group">
        <p className={cn(
          "text-xs text-zinc-700 font-medium break-all",
          copyable && "font-mono text-[10px]"
        )}>{value}</p>
        {copyable && (
          <button className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-zinc-900 transition-all">
            <ChevronRight className="w-3 h-3 rotate-90" />
          </button>
        )}
      </div>
    </div>
  );
}
