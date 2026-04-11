import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { Assistants } from './components/Assistants';
import { Voices } from './components/Voices';
import { LiveAssistant } from './components/LiveAssistant';
import { Threads } from './components/Threads';
import { Contacts } from './components/Contacts';
import { KnowledgeBases } from './components/KnowledgeBases';
import { Campaigns } from './components/Campaigns';
import { Settings } from './components/Settings';
import { NavItem } from './types';
import { motion, AnimatePresence } from 'motion/react';

export default function App() {
  const [activeItem, setActiveItem] = useState<NavItem>('Dashboard');
  const [showLiveBot, setShowLiveBot] = useState(false);

  const renderContent = () => {
    if (showLiveBot) return <LiveAssistant />;

    switch (activeItem) {
      case 'Dashboard':
        return <Dashboard />;
      case 'Assistants':
        return <Assistants />;
      case 'Voices':
        return <Voices />;
      case 'Threads':
        return <Threads />;
      case 'Contacts':
        return <Contacts />;
      case 'Knowledge Bases':
        return <KnowledgeBases />;
      case 'Campaigns':
        return <Campaigns />;
      case 'Settings':
        return <Settings />;
      default:
        return (
          <div className="flex flex-col items-center justify-center h-full text-zinc-400 space-y-4 bg-white">
            <div className="w-16 h-16 rounded-2xl bg-zinc-50 border border-zinc-200 flex items-center justify-center">
              <span className="text-2xl font-bold text-zinc-300">?</span>
            </div>
            <div className="text-center">
              <h3 className="text-zinc-900 font-semibold text-lg">{activeItem} Section</h3>
              <p className="text-sm">This section is currently under development.</p>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen bg-white text-zinc-900 font-sans selection:bg-orange-500/30 selection:text-orange-900 overflow-hidden">
      <Sidebar 
        activeItem={activeItem} 
        onItemClick={(item) => {
          setActiveItem(item);
          setShowLiveBot(false);
        }} 
      />
      
      <main className="flex-1 flex flex-col min-w-0 relative">
        <Header activeItem={showLiveBot ? 'Live Assistant' : activeItem} />
        
        <div className="flex-1 overflow-hidden relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={showLiveBot ? 'live' : activeItem}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="h-full"
            >
              {renderContent()}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Floating Live Bot Toggle */}
        <button 
          onClick={() => setShowLiveBot(!showLiveBot)}
          className="absolute bottom-8 right-8 w-14 h-14 bg-orange-500 hover:bg-orange-600 text-white rounded-full shadow-2xl shadow-orange-500/20 flex items-center justify-center transition-all active:scale-95 z-50 group"
        >
          {showLiveBot ? (
            <span className="text-xs font-bold uppercase tracking-tighter">Close</span>
          ) : (
            <div className="relative">
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-orange-500 animate-pulse" />
              <motion.div
                animate={{ rotate: [0, 10, -10, 0] }}
                transition={{ repeat: Infinity, duration: 2 }}
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </motion.div>
            </div>
          )}
          <div className="absolute right-full mr-4 px-3 py-1.5 bg-white border border-zinc-200 shadow-xl rounded-lg text-xs font-bold text-zinc-900 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
            {showLiveBot ? 'Back to Dashboard' : 'Test Live Assistant'}
          </div>
        </button>
      </main>
    </div>
  );
}
