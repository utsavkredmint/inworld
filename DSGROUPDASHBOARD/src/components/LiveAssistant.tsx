import { useState, useEffect, useRef } from 'react';
import { 
  Mic, 
  MicOff, 
  Phone, 
  PhoneOff, 
  MessageSquare, 
  Calendar, 
  Clock, 
  User, 
  CheckCircle2,
  AlertCircle,
  Play,
  Volume2,
  Bot,
  Activity
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';

interface Message {
  id: string;
  role: 'assistant' | 'user';
  text: string;
  timestamp: Date;
}

export function LiveAssistant() {
  const [isCalling, setIsCalling] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [status, setStatus] = useState<'idle' | 'calling' | 'connected' | 'ended'>('idle');
  const [bookingData, setBookingData] = useState({
    date: 'Not set',
    time: 'Not set',
    km: 'Not set'
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  const script = {
    start: "नमस्कार देव जी, मैं किया Service Center, गाजियाबाद से बात कर रहा हूँ। हमारे रिकॉर्ड के अनुसार आपकी गाड़ी की पिछली सर्विस हमारे यहाँ हुई थी और अब अगली सर्विस का समय हो गया है। कृपया बताइए, आप किस तारीख को सर्विस करवाना सुविधाजनक समझेंगे?",
    nextWeek: "जी अवश्य। कृपया बताइए, अगले सप्ताह आप किस तारीख को आना चाहेंगे?",
    dayOfWeek: "ठीक है। कृपया उस दिन की सही तारीख भी बता दीजिए ताकि हम आपकी बुकिंग दर्ज कर सकें।",
    timeAsk: "धन्यवाद। कृपया बताइए, आप किस समय आना चाहेंगे?",
    timeClarify: "जी अवश्य। कृपया सही समय भी बता दीजिए ताकि हम आपकी बुकिंग ठीक से निर्धारित कर सकें।",
    busyTime: "क्षमा कीजिए, उस समय स्लॉट उपलब्ध नहीं है। क्या आप तीन बजे के बाद का समय चुन सकते हैं?",
    slotUnavailable: "उस समय बुकिंग उपलब्ध नहीं है। कृपया कोई अन्य सुविधाजनक समय बताएं।",
    kmAsk: "कृपया बताइए, पिछली सर्विस के बाद गाड़ी लगभग कितने किलोमीटर चली है?",
    kmDecisionLow: "धन्यवाद। गाड़ी सामान्य सर्विस के लिए उपयुक्त है। क्या मैं आपकी सर्विस कन्फर्म कर दूँ?",
    kmDecisionHigh: "धन्यवाद। अब गाड़ी की विस्तृत सर्विस आवश्यक होगी, जिसमें इंजन ऑयल और अन्य जरूरी जांच शामिल रहेगी। क्या मैं आपकी सर्विस कन्फर्म कर दूँ?",
    confirm: "आपकी सर्विस निर्धारित कर दी गई है। कृपया समय से दस मिनट पहले पहुँचें। धन्यवाद देव जी, हम आपकी सेवा के लिए तत्पर हैं।",
    offer: "जी, इस समय सर्विस पर विशेष छूट और फ्री कार वॉश की सुविधा उपलब्ध है।",
    cost: "जी, इस सर्विस में लेबर चार्ज बिल्कुल फ्री है। हालांकि गाड़ी की आवश्यकता के अनुसार कुछ कंज़्यूमेबल चार्ज लग सकते हैं।"
  };

  const startCall = () => {
    setStatus('calling');
    setIsCalling(true);
    setMessages([]);
    setBookingData({ date: 'Not set', time: 'Not set', km: 'Not set' });
    setTimeout(() => {
      setStatus('connected');
      addMessage('assistant', script.start);
    }, 2000);
  };

  const endCall = () => {
    setStatus('ended');
    setIsCalling(false);
    setTimeout(() => setStatus('idle'), 3000);
  };

  const addMessage = (role: 'assistant' | 'user', text: string) => {
    setMessages(prev => [...prev, {
      id: Math.random().toString(36).substr(2, 9),
      role,
      text,
      timestamp: new Date()
    }]);
  };

  const handleUserResponse = (text: string) => {
    addMessage('user', text);
    
    // Simple logic to simulate the bot's decision tree based on the user's instructions
    setTimeout(() => {
      const lowerText = text.toLowerCase();
      
      if (lowerText.includes('offer') || lowerText.includes('छूट') || lowerText.includes('discount')) {
        addMessage('assistant', script.offer);
        return;
      }

      if (lowerText.includes('cost') || lowerText.includes('price') || lowerText.includes('कितने') || lowerText.includes('charge')) {
        addMessage('assistant', script.cost);
        return;
      }

      if (bookingData.date === 'Not set') {
        if (text.includes('अगले सप्ताह') || text.includes('next week')) {
          addMessage('assistant', script.nextWeek);
        } else if (['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'सोमवार', 'मंगलवार'].some(day => lowerText.includes(day))) {
          addMessage('assistant', script.dayOfWeek);
        } else {
          setBookingData(prev => ({ ...prev, date: text }));
          addMessage('assistant', script.timeAsk);
        }
      } else if (bookingData.time === 'Not set') {
        if (text.includes('morning') || text.includes('afternoon') || text.includes('evening') || text.includes('सुबह') || text.includes('शाम')) {
          addMessage('assistant', script.timeClarify);
        } else if (text.includes('1') || text.includes('2')) {
          addMessage('assistant', script.busyTime);
        } else {
          setBookingData(prev => ({ ...prev, time: text }));
          addMessage('assistant', script.kmAsk);
        }
      } else if (bookingData.km === 'Not set') {
        const kmValue = parseInt(text.replace(/[^0-9]/g, ''));
        setBookingData(prev => ({ ...prev, km: text }));
        if (kmValue > 10000) {
          addMessage('assistant', script.kmDecisionHigh);
        } else {
          addMessage('assistant', script.kmDecisionLow);
        }
      } else {
        addMessage('assistant', script.confirm);
      }
    }, 1000);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="p-8 h-full flex flex-col bg-white">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h3 className="text-zinc-900 font-semibold text-xl">Live Assistant Simulator</h3>
          <p className="text-zinc-500 text-sm">Test your voice bot configuration in real-time</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-50 border border-zinc-200 rounded-full">
            <div className={cn("w-2 h-2 rounded-full animate-pulse", status === 'connected' ? "bg-emerald-500" : "bg-zinc-300")} />
            <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{status}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-0">
        {/* Chat Interface */}
        <div className="lg:col-span-2 flex flex-col bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-zinc-200 bg-zinc-50/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-orange-500/10 flex items-center justify-center">
                <Bot className="w-5 h-5 text-orange-500" />
              </div>
              <div>
                <p className="text-sm font-semibold text-zinc-900">किया Service Center Bot</p>
                <p className="text-[10px] text-emerald-600 font-bold uppercase tracking-widest">Hindi Assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-2 text-zinc-400 hover:text-zinc-900 transition-colors">
                <Volume2 className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-zinc-50/20">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-50">
                <div className="w-16 h-16 rounded-full bg-zinc-100 flex items-center justify-center border border-zinc-200">
                  <Phone className="w-8 h-8 text-zinc-400" />
                </div>
                <div>
                  <p className="text-zinc-900 font-medium">No active call</p>
                  <p className="text-sm text-zinc-500">Start a call to begin simulation</p>
                </div>
              </div>
            )}
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  className={cn(
                    "flex w-full",
                    msg.role === 'assistant' ? "justify-start" : "justify-end"
                  )}
                >
                  <div className={cn(
                    "max-w-[80%] p-4 rounded-2xl text-sm leading-relaxed",
                    msg.role === 'assistant' 
                      ? "bg-white text-zinc-800 rounded-tl-none border border-zinc-200 shadow-sm" 
                      : "bg-orange-500 text-white rounded-tr-none shadow-lg shadow-orange-500/20"
                  )}>
                    {msg.text}
                    <div className={cn(
                      "text-[10px] mt-2 font-medium opacity-50",
                      msg.role === 'assistant' ? "text-zinc-500" : "text-orange-100"
                    )}>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div className="p-6 border-t border-zinc-200 bg-white">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <input 
                  type="text" 
                  placeholder={isListening ? "Listening..." : "Type user response..."}
                  className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 focus:outline-none focus:ring-1 focus:ring-orange-500 transition-all"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.currentTarget.value) {
                      handleUserResponse(e.currentTarget.value);
                      e.currentTarget.value = '';
                    }
                  }}
                />
                <button 
                  onClick={() => setIsListening(!isListening)}
                  className={cn(
                    "absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-all",
                    isListening ? "bg-rose-500 text-white animate-pulse" : "text-zinc-400 hover:text-zinc-900"
                  )}
                >
                  {isListening ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
                </button>
              </div>
              
              {status === 'idle' || status === 'ended' ? (
                <button 
                  onClick={startCall}
                  className="bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-emerald-500/20 active:scale-95"
                >
                  <Phone className="w-5 h-5" />
                  Start Call
                </button>
              ) : (
                <button 
                  onClick={endCall}
                  className="bg-rose-500 hover:bg-rose-600 text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg shadow-rose-500/20 active:scale-95"
                >
                  <PhoneOff className="w-5 h-5" />
                  End Call
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          <div className="bg-white border border-zinc-200 p-6 rounded-2xl shadow-sm">
            <h4 className="text-zinc-900 font-semibold mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-orange-500" />
              Customer Profile
            </h4>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Name</span>
                <span className="text-sm font-medium text-zinc-900">Dev Ji</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Last Service</span>
                <span className="text-sm font-medium text-zinc-900">15 Oct 2025</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Vehicle</span>
                <span className="text-sm font-medium text-zinc-900">Kia Seltos (UP-14)</span>
              </div>
            </div>
          </div>

          <div className="bg-white border border-zinc-200 p-6 rounded-2xl shadow-sm">
            <h4 className="text-zinc-900 font-semibold mb-4 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-orange-500" />
              Booking Details
            </h4>
            <div className="space-y-4">
              <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-200 flex items-center gap-3">
                <Calendar className="w-4 h-4 text-zinc-400" />
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase font-bold">Date</p>
                  <p className="text-sm text-zinc-900 font-medium">{bookingData.date}</p>
                </div>
              </div>
              <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-200 flex items-center gap-3">
                <Clock className="w-4 h-4 text-zinc-400" />
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase font-bold">Time</p>
                  <p className="text-sm text-zinc-900 font-medium">{bookingData.time}</p>
                </div>
              </div>
              <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-200 flex items-center gap-3">
                <Activity className="w-4 h-4 text-zinc-400" />
                <div>
                  <p className="text-[10px] text-zinc-500 uppercase font-bold">KM Reading</p>
                  <p className="text-sm text-zinc-900 font-medium">{bookingData.km}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-orange-50 border border-orange-100 p-6 rounded-2xl">
            <h4 className="text-orange-600 font-semibold mb-2 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              Bot Instructions
            </h4>
            <p className="text-xs text-orange-800/70 leading-relaxed">
              The bot is currently following the "किया Service Center, गाजियाबाद" persona. It will prioritize polite Hindi communication and appointment scheduling for "देव जी".
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
