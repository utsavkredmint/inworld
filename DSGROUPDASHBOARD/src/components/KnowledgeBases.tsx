import { 
  Database, 
  Plus, 
  FileText, 
  Globe, 
  Link as LinkIcon, 
  MoreVertical, 
  Search, 
  Filter,
  CheckCircle2,
  Clock,
  Trash2,
  ArrowLeft,
  Upload,
  Type,
  Check,
  X
} from 'lucide-react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';

const initialKnowledgeBases: any[] = [];

export function KnowledgeBases() {
  const [view, setView] = useState<'list' | 'add'>('list');
  const [knowledgeBaseList, setKnowledgeBaseList] = useState(initialKnowledgeBases);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Form State
  const [sourceName, setSourceName] = useState('');
  const [sourceType, setSourceType] = useState<'URL' | 'PDF' | 'Doc' | 'Text'>('URL');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [sourceFile, setSourceFile] = useState<File | null>(null);

  const handleDelete = (id: string) => {
    setDeleteId(id);
  };

  const confirmDelete = () => {
    if (deleteId) {
      setKnowledgeBaseList(prev => prev.filter(kb => kb.id !== deleteId));
      setDeleteId(null);
    }
  };

  const handleAddSource = () => {
    const newSource = {
      id: Math.random().toString(36).substr(2, 9),
      name: sourceName,
      type: sourceType,
      items: sourceType === 'URL' ? 1 : (sourceType === 'Text' ? 1 : 1), // Mock item count
      status: 'synced',
      lastUpdated: 'Just now'
    };
    setKnowledgeBaseList([newSource, ...knowledgeBaseList]);
    setView('list');
    // Reset form
    setSourceName('');
    setSourceType('URL');
    setSourceUrl('');
    setSourceText('');
    setSourceFile(null);
  };

  if (view === 'add') {
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
            <h3 className="text-zinc-900 font-bold text-2xl">Add Knowledge Source</h3>
            <p className="text-zinc-500 text-sm">Provide documents, URLs, or text to train your AI agents</p>
          </div>
        </div>

        <div className="bg-zinc-50 border border-zinc-200 rounded-3xl p-8 space-y-8">
          {/* Source Name */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Source Name</label>
            <input 
              type="text"
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              placeholder="e.g. Service Manuals 2024"
              className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
            />
          </div>

          {/* Source Type Selection */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Source Type</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { id: 'URL', icon: Globe, label: 'URL' },
                { id: 'PDF', icon: FileText, label: 'PDF' },
                { id: 'Doc', icon: FileText, label: 'DOC' },
                { id: 'Text', icon: Type, label: 'Text' },
              ].map((type) => (
                <button
                  key={type.id}
                  onClick={() => setSourceType(type.id as any)}
                  className={cn(
                    "p-4 rounded-xl border transition-all flex flex-col items-center gap-2",
                    sourceType === type.id 
                      ? "bg-orange-50 border-orange-500 ring-1 ring-orange-500 text-orange-600" 
                      : "bg-white border-zinc-200 text-zinc-500 hover:border-zinc-300"
                  )}
                >
                  <type.icon className="w-6 h-6" />
                  <span className="text-xs font-bold">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Dynamic Input based on Type */}
          <div className="space-y-3">
            {sourceType === 'URL' && (
              <div className="space-y-3">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Website URL</label>
                <div className="relative">
                  <LinkIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                  <input 
                    type="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://example.com"
                    className="w-full bg-white border border-zinc-200 rounded-xl pl-12 pr-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
                  />
                </div>
              </div>
            )}

            {(sourceType === 'PDF' || sourceType === 'Doc') && (
              <div className="space-y-3">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Upload File</label>
                <div className="border-2 border-dashed border-zinc-200 rounded-2xl p-12 text-center space-y-4 hover:border-orange-500/50 transition-colors bg-white group">
                  <div className="w-16 h-16 bg-orange-50 rounded-2xl flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
                    <Upload className="w-8 h-8 text-orange-500" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-zinc-900 font-bold">Click to upload or drag and drop</p>
                    <p className="text-zinc-400 text-xs">{sourceType} files up to 10MB</p>
                  </div>
                  <input 
                    type="file" 
                    accept={sourceType === 'PDF' ? '.pdf' : '.doc,.docx'}
                    className="hidden" 
                    id="kb-file-upload"
                    onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
                  />
                  <label 
                    htmlFor="kb-file-upload"
                    className="inline-block px-6 py-2 bg-zinc-900 text-white rounded-lg text-sm font-bold cursor-pointer hover:bg-zinc-800 transition-colors"
                  >
                    Select File
                  </label>
                  {sourceFile && (
                    <p className="text-orange-600 text-sm font-bold flex items-center justify-center gap-2">
                      <CheckCircle2 className="w-4 h-4" />
                      {sourceFile.name}
                    </p>
                  )}
                </div>
              </div>
            )}

            {sourceType === 'Text' && (
              <div className="space-y-3">
                <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Raw Text Content</label>
                <textarea 
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                  placeholder="Paste your text content here..."
                  rows={8}
                  className="w-full bg-white border border-zinc-200 rounded-xl px-4 py-3 text-zinc-900 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all resize-none"
                />
              </div>
            )}
          </div>

          <div className="pt-4">
            <button 
              disabled={!sourceName || (sourceType === 'URL' && !sourceUrl) || (sourceType === 'Text' && !sourceText) || ((sourceType === 'PDF' || sourceType === 'Doc') && !sourceFile)}
              onClick={handleAddSource}
              className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-200 disabled:text-zinc-400 text-white py-4 rounded-xl font-bold text-lg transition-all shadow-lg shadow-orange-500/20 active:scale-[0.98] flex items-center justify-center gap-2"
            >
              <Check className="w-5 h-5" />
              Add to Knowledge Base
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
          <h3 className="text-zinc-900 font-semibold text-xl">Knowledge Bases</h3>
          <p className="text-zinc-500 text-sm">Upload documents and URLs to train your assistants</p>
        </div>
        <button 
          onClick={() => setView('add')}
          className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-orange-500/20 active:scale-95"
        >
          <Plus className="w-5 h-5" />
          Add Source
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 group-focus-within:text-orange-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search sources..." 
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl pl-10 pr-4 py-2.5 text-sm text-zinc-600 focus:outline-none focus:ring-1 focus:ring-orange-500/50 focus:border-orange-500/50 transition-all"
          />
        </div>
        <button className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-xl text-zinc-400 hover:text-zinc-900 transition-all">
          <Filter className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <AnimatePresence mode="popLayout">
          {knowledgeBaseList.map((kb, i) => (
            <motion.div
              key={kb.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ delay: i * 0.05 }}
              layout
              className="bg-zinc-50 border border-zinc-200 p-6 rounded-2xl group hover:border-zinc-300 transition-all"
            >
              <div className="flex items-start justify-between mb-6">
                <div className="w-12 h-12 rounded-xl bg-white border border-zinc-200 flex items-center justify-center group-hover:border-orange-500/50 transition-all">
                  {kb.type === 'PDF' ? <FileText className="w-6 h-6 text-orange-500" /> : 
                   kb.type === 'URL' ? <Globe className="w-6 h-6 text-orange-500" /> : 
                   kb.type === 'Doc' ? <FileText className="w-6 h-6 text-orange-500" /> :
                   <Type className="w-6 h-6 text-orange-500" />}
                </div>
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    kb.status === 'synced' ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)]" :
                    kb.status === 'syncing' ? "bg-blue-500 animate-pulse" :
                    "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.3)]"
                  )} />
                  <button className="p-1 text-zinc-400 hover:text-zinc-900 transition-colors">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <h4 className="text-zinc-900 font-bold text-lg mb-1">{kb.name}</h4>
              <p className="text-zinc-500 text-xs mb-6 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Updated {kb.lastUpdated}
              </p>

              <div className="flex items-center justify-between p-3 bg-white rounded-xl border border-zinc-200 mb-6">
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase font-bold">Type</p>
                  <p className="text-xs text-zinc-900 font-medium">{kb.type}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-zinc-500 uppercase font-bold">Items</p>
                  <p className="text-xs text-zinc-900 font-medium">{kb.items}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-white py-2 rounded-lg text-xs font-bold transition-all">
                  Sync Now
                </button>
                <button 
                  onClick={() => handleDelete(kb.id)}
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
                <h4 className="text-xl font-bold text-zinc-900">Delete Source?</h4>
                <p className="text-zinc-500 text-sm">
                  Are you sure you want to delete this knowledge source? This will remove the data from your AI training set.
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
