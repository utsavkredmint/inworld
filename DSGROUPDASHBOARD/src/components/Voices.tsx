import React, { useState, useEffect } from 'react';
import { Mic, Upload, Trash2, Play, Plus, Loader2, Music } from 'lucide-react';
import { api, Voice } from '../lib/api';

export function Voices() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCloning, setIsCloning] = useState(false);
  const [showCloneModal, setShowCloneModal] = useState(false);
  
  // Form state
  const [name, setName] = useState('');
  const [refText, setRefText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    loadVoices();
  }, []);

  const loadVoices = async () => {
    try {
      const data = await api.listVoices();
      setVoices(data);
    } catch (error) {
      console.error('Failed to load voices:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !name) return;

    setIsCloning(true);
    const formData = new FormData();
    formData.append('name', name);
    formData.append('ref_text', refText);
    formData.append('file', selectedFile);

    try {
      await api.cloneVoice(formData);
      await loadVoices();
      setShowCloneModal(false);
      setName('');
      setRefText('');
      setSelectedFile(null);
    } catch (error) {
      console.error('Cloning failed:', error);
      alert('Failed to clone voice. Please ensure it is a valid WAV/MP3 file.');
    } finally {
      setIsCloning(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this voice?')) return;
    try {
      await api.deleteVoice(id);
      setVoices(voices.filter(v => v.id !== id));
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 bg-white h-full overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 tracking-tight">Voice Cloning</h2>
          <p className="text-zinc-500 text-sm mt-1">Manage your custom AI voices using OmniVoice zero-shot cloning.</p>
        </div>
        <button 
          onClick={() => setShowCloneModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-semibold transition-all shadow-lg shadow-orange-500/20 active:scale-95"
        >
          <Plus className="w-4 h-4" />
          Clone New Voice
        </button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-400 space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-orange-500" />
          <p className="text-sm font-medium">Loading your voices...</p>
        </div>
      ) : voices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 border-2 border-dashed border-zinc-200 rounded-2xl bg-zinc-50/50 space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-white border border-zinc-200 flex items-center justify-center shadow-sm">
            <Mic className="text-zinc-300 w-8 h-8" />
          </div>
          <div className="text-center">
            <h3 className="text-zinc-900 font-semibold">No custom voices found</h3>
            <p className="text-zinc-500 text-sm max-w-xs mx-auto mt-1">
              Upload a 5-10 second audio clip to create your first high-quality cloned voice.
            </p>
          </div>
          <button 
            onClick={() => setShowCloneModal(true)}
            className="text-orange-600 text-sm font-bold hover:text-orange-700 transition-colors"
          >
            Create your first voice →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {(voices || []).map((voice) => (
            <div key={voice.id} className="group p-5 rounded-2xl border border-zinc-200 bg-white hover:border-orange-200 hover:shadow-xl hover:shadow-orange-500/5 transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <button 
                  onClick={() => handleDelete(voice.id)}
                  className="p-2 text-zinc-400 hover:text-red-500 transition-colors bg-white rounded-lg shadow-sm border border-zinc-100"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center shrink-0">
                  <Music className="text-orange-600 w-6 h-6" />
                </div>
                <div className="min-w-0 pr-8">
                  <h3 className="font-bold text-zinc-900 truncate">{voice.name}</h3>
                  <p className="text-xs text-zinc-500 mt-1">Created {new Date(voice.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              <div className="mt-6 pt-5 border-t border-zinc-50 flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">Reference</span>
                  <span className="text-xs text-zinc-600 font-medium truncate max-w-[120px]">
                    {voice.ref_audio_path.split('/').pop()}
                  </span>
                </div>
                <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 text-white rounded-lg text-xs font-bold hover:bg-zinc-800 transition-colors active:scale-95 disabled:opacity-50">
                  <Play className="w-3 h-3 fill-current" />
                  Test Voice
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Integration could go here, but for brevity I'll use a simple conditional render */}
      {showCloneModal && (
        <div className="fixed inset-0 bg-zinc-950/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl border border-zinc-200 overflow-hidden ring-1 ring-black/5 animate-in zoom-in-95 fade-in duration-200">
            <div className="p-8">
              <h3 className="text-xl font-bold text-zinc-900 tracking-tight">Clone New Voice</h3>
              <p className="text-zinc-500 text-sm mt-1">Provide a sample and text for the zero-shot model.</p>

              <form onSubmit={handleClone} className="mt-8 space-y-6">
                <div>
                  <label className="block text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">Voice Name</label>
                  <input 
                    type="text" 
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. My Personal Assistant"
                    className="w-full px-4 py-3 rounded-xl border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">Reference Audio</label>
                  <div className="relative group/upload">
                    <input 
                      type="file" 
                      accept=".wav,.mp3"
                      required
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                    />
                    <div className="w-full py-8 border-2 border-dashed border-zinc-200 rounded-2xl flex flex-col items-center justify-center bg-zinc-50 group-hover/upload:bg-zinc-100/50 group-hover/upload:border-orange-300 transition-all">
                      <Upload className="w-6 h-6 text-zinc-400 group-hover/upload:text-orange-500 mb-2 transition-colors" />
                      <span className="text-sm text-zinc-600 font-medium">
                        {selectedFile ? selectedFile.name : 'Click to upload audio (WAV/MP3)'}
                      </span>
                      <span className="text-[10px] text-zinc-400 mt-1 uppercase font-bold tracking-tighter">Recommended: 5-10 seconds</span>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">Transcription (Optional)</label>
                  <textarea 
                    value={refText}
                    onChange={(e) => setRefText(e.target.value)}
                    placeholder="What is spoken in the audio? (Recommended for better quality)"
                    className="w-full px-4 py-3 rounded-xl border border-zinc-200 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all text-sm h-24 resize-none"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button 
                    type="button"
                    onClick={() => setShowCloneModal(false)}
                    className="flex-1 py-3 text-sm font-bold text-zinc-500 hover:text-zinc-900 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={isCloning || !selectedFile || !name}
                    className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-white py-3 rounded-xl text-sm font-bold shadow-lg shadow-zinc-900/10 active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isCloning ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Cloning...
                      </>
                    ) : 'Create Voice'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
