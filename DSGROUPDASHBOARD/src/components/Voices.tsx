import React, { useState, useEffect } from 'react';
import { Mic, Upload, Trash2, Play, Plus, Loader2, Music, Settings2, Globe, X } from 'lucide-react';
import { api, Voice } from '../lib/api';

export function Voices() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCloning, setIsCloning] = useState(false);
  const [testingVoiceId, setTestingVoiceId] = useState<string | null>(null);
  const [showCloneModal, setShowCloneModal] = useState(false);
  
  // Test settings state
  const [testText, setTestText] = useState('नमस्ते, मैं आपकी सहायता के लिए तैयार हूँ।');
  const [testLanguage, setTestLanguage] = useState('hindi');

  // Form state
  const [name, setName] = useState('');
  const [refText, setRefText] = useState('');
  const [cloneLanguage, setCloneLanguage] = useState('hindi');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  const handleTestVoice = async (voiceId: string) => {
    if (testingVoiceId) return;
    setTestingVoiceId(voiceId);
    try {
      const blob = await api.testVoice(voiceId, testText, testLanguage);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (error) {
      console.error('Test voice failed:', error);
      alert('Failed to generate test audio.');
    } finally {
      setTestingVoiceId(null);
    }
  };

  const handleClone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !selectedFile) return;

    setIsCloning(true);
    try {
      await api.cloneVoice(name, selectedFile, refText, cloneLanguage);
      setShowCloneModal(false);
      setName('');
      setRefText('');
      setCloneLanguage('hindi');
      setSelectedFile(null);
      loadVoices();
    } catch (error) {
      console.error('Cloning failed:', error);
      alert('Cloning failed. Please check the logs.');
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
        <>
          <div className="mb-8 p-6 bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-zinc-800 rounded-lg">
                <Settings2 className="w-5 h-5 text-zinc-400" />
              </div>
              <div>
                <h3 className="text-white font-semibold">Test Playback Settings</h3>
                <p className="text-sm text-white/40">Customize how your test audio is generated</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 space-y-3">
                <label className="flex items-center gap-2 text-xs font-bold text-white/40 uppercase tracking-wider">
                  Test Sentence
                </label>
                <textarea
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  className="w-full bg-black border border-white/10 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-zinc-500 min-h-[100px] transition-colors resize-none placeholder:text-white/10"
                  placeholder="Type anything here... e.g. 'नमस्ते, आपका क्या हाल है?'"
                />
              </div>
              
              <div className="space-y-6">
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-xs font-bold text-white/40 uppercase tracking-wider">
                    <Globe className="w-3 h-3" />
                    Language
                  </label>
                  <select
                    value={testLanguage}
                    onChange={(e) => setTestLanguage(e.target.value)}
                    className="w-full bg-black border border-white/10 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-zinc-500 appearance-none transition-colors"
                  >
                    <option value="hindi">Hindi</option>
                    <option value="english">English (US)</option>
                    <option value="spanish">Spanish</option>
                    <option value="french">French</option>
                    <option value="german">German</option>
                    <option value="chinese">Chinese</option>
                    <option value="japanese">Japanese</option>
                  </select>
                </div>
                
                <div className="p-4 bg-zinc-800/30 rounded-xl border border-white/5">
                  <p className="text-[11px] leading-relaxed text-zinc-400">
                    <strong className="text-zinc-200 block mb-1">Speaker Persistence:</strong>
                    Once cloned, the voice is saved under your account. You can use it in agents by its name without re-uploading audio.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {(voices || []).map((voice) => (
              <div key={voice.id} className="group p-5 rounded-2xl border border-zinc-200 bg-white hover:border-orange-200 hover:shadow-xl hover:shadow-orange-500/5 transition-all duration-300 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => handleDelete(voice.id)}
                    className="p-2 text-zinc-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-12 h-12 rounded-2xl bg-orange-50 flex items-center justify-center text-orange-500 group-hover:scale-110 transition-transform duration-300">
                    <Music className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-zinc-900">{voice.name}</h3>
                    <p className="text-xs text-zinc-400">Created {new Date(voice.created_at).toLocaleDateString()}</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-zinc-50 rounded-xl group-hover:bg-orange-50/50 transition-colors">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                      <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Reference</span>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-400">
                      {voice.ref_audio_path.split('/').pop()}
                    </span>
                  </div>
                  <button 
                    disabled={testingVoiceId === voice.id}
                    onClick={() => handleTestVoice(voice.id)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-zinc-900 text-white rounded-xl text-sm font-bold hover:bg-zinc-800 transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-zinc-900/10"
                  >
                    {testingVoiceId === voice.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4 fill-current" />
                    )}
                    {testingVoiceId === voice.id ? 'Generating...' : 'Test Voice'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {showCloneModal && (
        <div className="fixed inset-0 bg-zinc-950/60 backdrop-blur-md z-[100] flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-2xl rounded-[2.5rem] shadow-2xl border border-white/20 overflow-hidden ring-1 ring-black/5 animate-in zoom-in-95 fade-in duration-300">
            <div className="p-8 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-orange-500 text-white flex items-center justify-center shadow-lg shadow-orange-500/20">
                  <Mic className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-black text-zinc-900 tracking-tight">Clone New Identity</h2>
                  <p className="text-sm text-zinc-400 font-medium">Create a persistent TTS model from audio</p>
                </div>
              </div>
              <button 
                onClick={() => setShowCloneModal(false)}
                className="p-3 hover:bg-white hover:shadow-xl rounded-2xl transition-all text-zinc-400 hover:text-zinc-900"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleClone} className="p-8 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Left Column: Info & Text */}
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest px-1">Identity Name</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Professional Female Voice"
                      className="w-full px-5 py-4 bg-zinc-50 border-2 border-transparent focus:border-orange-500/20 focus:bg-white rounded-2xl text-sm font-bold transition-all outline-none"
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest px-1 flex items-center justify-between">
                      Reference Text
                      <span className="text-[10px] lowercase font-normal opacity-60">(optional)</span>
                    </label>
                    <textarea
                      value={refText}
                      onChange={(e) => setRefText(e.target.value)}
                      placeholder="Transcript of the audio clip..."
                      className="w-full px-5 py-4 bg-zinc-50 border-2 border-transparent focus:border-orange-500/20 focus:bg-white rounded-2xl text-sm font-medium transition-all outline-none min-h-[120px] resize-none"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest px-1 flex items-center gap-2">
                      <Globe className="w-3.5 h-3.5" />
                      Target Language
                    </label>
                    <select
                      value={cloneLanguage}
                      onChange={(e) => setCloneLanguage(e.target.value)}
                      className="w-full px-5 py-4 bg-zinc-50 border-2 border-transparent focus:border-orange-500/20 focus:bg-white rounded-2xl text-sm font-bold transition-all outline-none appearance-none cursor-pointer"
                    >
                      <option value="hindi">Hindi</option>
                      <option value="english">English (US)</option>
                      <option value="spanish">Spanish</option>
                      <option value="french">French</option>
                      <option value="german">German</option>
                      <option value="chinese">Chinese</option>
                    </select>
                  </div>
                </div>

                {/* Right Column: Audio Upload */}
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest px-1">Reference Audio</label>
                    <div 
                      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDragging(false);
                        const file = e.dataTransfer.files[0];
                        if (file && (file.type.includes('audio') || file.name.endsWith('.mp3') || file.name.endsWith('.wav'))) {
                          setSelectedFile(file);
                        }
                      }}
                      className={`
                        relative group cursor-pointer border-2 border-dashed rounded-[2rem] p-8 transition-all duration-300
                        ${selectedFile ? 'border-orange-500 bg-orange-50/30' : 'border-zinc-200 hover:border-orange-200 bg-zinc-50/50 hover:bg-white'}
                        ${isDragging ? 'scale-105 border-orange-500 bg-orange-50' : ''}
                      `}
                    >
                      <input 
                        type="file" 
                        accept=".wav,.mp3" 
                        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                      <div className="flex flex-col items-center justify-center gap-4 text-center">
                        <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${selectedFile ? 'bg-orange-500 text-white animate-bounce' : 'bg-white text-zinc-400 group-hover:text-orange-500 shadow-sm'}`}>
                          <Upload className="w-8 h-8" />
                        </div>
                        {selectedFile ? (
                          <div>
                            <p className="text-sm font-bold text-zinc-900 mb-1">{selectedFile.name}</p>
                            <p className="text-[10px] text-orange-600 font-bold uppercase">Ready to Clone</p>
                          </div>
                        ) : (
                          <div>
                            <p className="text-sm font-bold text-zinc-900 mb-1">Drop audio file here</p>
                            <p className="text-[10px] text-zinc-400 font-medium">.WAV or .MP3 (Recommended 3-10s)</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="p-6 bg-zinc-900 rounded-[2rem] space-y-4 shadow-xl">
                    <button 
                      type="button"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="w-full flex items-center justify-between text-white group"
                    >
                      <div className="flex items-center gap-2">
                        <Settings2 className="w-4 h-4 text-orange-500" />
                        <span className="text-xs font-bold uppercase tracking-widest">Inference Engine</span>
                      </div>
                      <Plus className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-45' : ''}`} />
                    </button>
                    {showAdvanced && (
                      <div className="space-y-4 pt-4 border-t border-white/5 animate-in slide-in-from-top-4 duration-300">
                        <div className="space-y-2">
                          <div className="flex justify-between text-[10px] font-bold text-white/40 uppercase">
                            <span>Steps</span>
                            <span>32</span>
                          </div>
                          <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                            <div className="h-full w-[60%] bg-orange-500" />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex justify-between text-[10px] font-bold text-white/40 uppercase">
                            <span>CFG Scale</span>
                            <span>2.0</span>
                          </div>
                          <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                            <div className="h-full w-[40%] bg-orange-500" />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCloneModal(false)}
                  className="flex-1 py-4 text-sm font-bold text-zinc-500 hover:text-zinc-900 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCloning || !selectedFile || !name}
                  className="flex-[2] py-4 bg-orange-500 text-white rounded-2xl text-sm font-black hover:bg-orange-600 transition-all active:scale-95 disabled:opacity-50 shadow-xl shadow-orange-500/20 flex items-center justify-center gap-3 uppercase tracking-widest"
                >
                  {isCloning ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Cloning Identity...
                    </>
                  ) : (
                    <>
                      <Mic className="w-5 h-5" />
                      Generate TTS Model
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
