'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { MessageCircle, X, Send, Loader, Sprout, ScanSearch, FlaskConical, LineChart, Satellite, Landmark, Globe2, Settings } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useLanguage } from '@/context/LanguageContext';

interface ChatbotBubbleProps {
  onNavigate: (tab: string) => void;
}

interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
}

const MessageContent = ({ content }: { content: string }) => {
  const lines = content.split('\n');
  return (
    <div className="flex flex-col gap-1.5">
      {lines.map((line, idx) => {
        if (!line.trim()) return <div key={idx} className="h-0.5" />; // spacer for empty lines
        
        const isBullet = line.match(/^[\s]*[-•*]/);
        const isNumbered = line.match(/^[\s]*\d+\./);
        
        return (
          <div 
            key={idx} 
            className={`text-[14px] leading-relaxed font-medium ${
              isBullet || isNumbered ? 'pl-4 relative' : ''
            }`}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
};

export default function ChatbotBubble({ onNavigate }: ChatbotBubbleProps) {
  const { language, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          id: 'welcome-1',
          type: 'bot',
          content: 'নমস্কাৰ! Hello!\n\nআপুনি কি কৰিব বিচাৰে?\nWhat would you like to do?\n\nতলৰ বুটামবোৰ টিপক বা চমু শব্দ টাইপ কৰক।\nTap a button below, or type a short word.',
          timestamp: new Date(),
        },
        {
          id: 'welcome-2',
          type: 'bot',
          content: 'Examples / উদাহৰণ:\n• "পাত" or "leaf" → Leaf Scanner\n• "বজাৰ" or "market" → Market Prices\n• "অনুদান" or "subsidy" → Government Schemes\n• "খেতি" or "cultivation" → Farm Monitor',
          timestamp: new Date(),
        }
      ]);
    }
  }, [isOpen, messages.length]);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  const quickActions = [
    { id: 'cultivation', icon: Sprout, en: 'Cultivation', as: 'খেতি', desc: 'Farm Monitor' },
    { id: 'leaf-quality', icon: ScanSearch, en: 'Leaf Scan', as: 'পাত স্কেন', desc: 'Leaf Quality Scanner' },
    { id: 'action', icon: FlaskConical, en: 'Simulator', as: 'কাৰ্য পৰীক্ষক', desc: 'Action Simulator' },
    { id: 'market', icon: LineChart, en: 'Market', as: 'বজাৰ দাম', desc: 'Market Intelligence' },
    { id: 'satellite', icon: Satellite, en: 'Crop Health', as: 'শস্য স্বাস্থ্য', desc: 'Satellite Monitor' },
    { id: 'subsidies', icon: Landmark, en: 'Subsidies', as: 'অনুদান', desc: 'Government Schemes' },
    { id: 'digital-twin', icon: Globe2, en: 'Digital Twin', as: 'ডিজিটেল টুইন', desc: 'Digital Twin' },
    { id: 'settings', icon: Settings, en: 'Settings', as: 'ছেটিং', desc: 'Account Settings' },
  ];

  const handleQuickAction = (tabId: string) => {
    const action = quickActions.find(a => a.id === tabId);
    if (!action) return;
    onNavigate(tabId);
    
    const botResponse: Message = { 
      id: Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9), 
      type: 'bot', 
      content: `Opening ${action.desc}!\n${action.as} খোলা হৈছে!`, 
      timestamp: new Date() 
    };
    setMessages(prev => [...prev, botResponse]);
  };

  const parseNavigationIntent = (input: string): string | null => {
    const text = input.toLowerCase();
    const mappings: Record<string, string[]> = {
      'cultivation': ['cultivation', 'iot', 'sensor', 'soil', 'moisture', 'temperature', 'humidity', 'weather', 'rainfall', 'health score', 'pest', 'drought', 'monitor', 'kheti', 'খেতি', 'মাটি', 'আৰ্দ্ৰতা', 'উষ্ণতা', 'বৰষুণ', 'কীট', 'পথাৰ'],
      'leaf-quality': ['leaf', 'scan', 'quality', 'grade', 'disease', 'upload', 'photo', 'image', 'scanner', 'healthy', 'diseased', 'pat', 'পাত', 'স্কেন', 'গ্ৰেড', 'ৰোগ', 'ছবি'],
      'action': ['action', 'simulate', 'simulator', 'yield', 'harvest', 'selling', 'auction', 'route', 'truck', 'outcome', 'what if', 'koribo', 'কাৰ্য', 'সিমুলেট', 'উৎপাদন', 'নিলাম', 'বিক্ৰী'],
      'market': ['market', 'price', 'demand', 'forecast', 'trend', 'volatility', 'revenue', 'profit', 'rate', 'bajar', 'dam', 'বজাৰ', 'দাম', 'মূল্য', 'পূৰ্বাভাস', 'লাভ'],
      'satellite': ['satellite', 'ndvi', 'crop health', 'evi', 'ndwi', 'map', 'heatmap', 'anomaly', 'উপগ্ৰহ', 'শস্য', 'মানচিত্ৰ'],
      'subsidies': ['subsidy', 'insurance', 'scheme', 'government', 'grant', 'dossier', 'eligibility', 'replanting', 'bima', 'anudaan', 'অনুদান', 'বীমা', 'আঁচনি', 'চৰকাৰী'],
      'digital-twin': ['digital twin', 'twin', 'projection', '5 year', 'climate', 'resilience', 'future', 'ডিজিটেল', 'ভৱিষ্যত', 'জলবায়ু'],
      'settings': ['settings', 'account', 'profile', 'password', 'name', 'update', 'setting', 'ছেটিং', 'একাউণ্ট', 'প্ৰফাইল', 'পাছৱৰ্ড']
    };

    for (const [tabId, keywords] of Object.entries(mappings)) {
      if (keywords.some(kw => text.includes(kw))) {
        return tabId;
      }
    }
    return null;
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
    const userMessage: Message = { id: Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9), type: 'user', content: inputValue, timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');

    const targetTab = parseNavigationIntent(currentInput);
    if (targetTab) {
      handleQuickAction(targetTab);
      return;
    }

    setIsLoading(true);
    try {
      const history = messages.map(msg => ({ role: msg.type === 'user' ? 'user' : 'assistant', content: msg.content }));
      const data = await apiClient.post('/api/chat', { message: currentInput, history });
      const botResponse: Message = { id: Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9), type: 'bot', content: data.response, timestamp: new Date() };
      setMessages((prev) => [...prev, botResponse]);
      if (data.suggested_actions && data.suggested_actions.length > 0) {
        const actionsMessage: Message = { id: Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9), type: 'bot', content: 'Suggested Actions:\n' + data.suggested_actions.map((action: string, idx: number) => `${idx + 1}. ${action}`).join('\n'), timestamp: new Date() };
        setMessages((prev) => [...prev, actionsMessage]);
      }
      setIsLoading(false);
    } catch (error) {
      const botResponse: Message = { id: Date.now().toString() + '-' + Math.random().toString(36).substring(2, 9), type: 'bot', content: generateBotResponse(currentInput), timestamp: new Date() };
      setMessages((prev) => [...prev, botResponse]);
      setIsLoading(false);
    }
  };

  const generateBotResponse = (userInput: string): string => {
    const input = userInput.toLowerCase();
    if (input.includes('leaf quality') || input.includes('improve leaf')) return 'To improve leaf quality, ensure consistent soil moisture (55-65%), maintain optimal temperature (22-25°C), and apply balanced fertilizers.';
    if (input.includes('irrigation') || input.includes('water')) return 'For tea plants, irrigation depends on season and soil type. During growing season: 2-3 times weekly.';
    if (input.includes('market') || input.includes('price')) return 'Current market trends show 8% price increase expected in the next 7-10 days.';
    if (input.includes('pest') || input.includes('disease')) return 'Common tea plant pests: Green leaf hopper, Scale insect, and Tea mosquito.';
    return language === 'as' ? 'দয়া কৰি আপোনাৰ প্ৰশ্নটো পুনৰ কওক। আপুনি তলৰ বুটামবোৰো ব্যৱহাৰ কৰিব পাৰে।' : 'That\'s a great question! Check the relevant dashboard tab for detailed insights or tap a quick action below.';
  };

  return (
    <>
      <button onClick={() => setIsOpen(!isOpen)} className="fixed bottom-6 right-6 z-40 p-4 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-110 active:scale-95">
        {!isOpen && (
          <span className="absolute top-1 right-1 flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
          </span>
        )}
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
      {isOpen && (
        <Card className="fixed bottom-24 right-6 z-40 w-[400px] max-w-[calc(100vw-24px)] shadow-2xl rounded-2xl overflow-hidden flex flex-col max-h-[600px] h-[80vh] bg-background gap-0 py-0 border-border animate-in slide-in-from-bottom-5 fade-in zoom-in-95 duration-200">
          <div className="bg-primary text-primary-foreground p-4 flex justify-between items-center shrink-0 border-b border-border">
            <div>
              <h3 className="font-bold text-lg flex items-center gap-2">
                CHAI-NET Assistant
                <span className="bg-primary-foreground/20 px-1.5 py-0.5 rounded text-[10px] font-mono tracking-wider">
                  {language.toUpperCase()}
                </span>
              </h3>
              <p className="text-xs opacity-90 font-medium">
                {language === 'as' ? 'সহায়ৰ বাবে সদায় প্ৰস্তুত' : 'Always here to help'}
              </p>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-primary-foreground/80 hover:text-primary-foreground hover:bg-primary-foreground/10 p-1.5 rounded-full transition-colors">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-background">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-4 py-3 rounded-2xl shadow-sm ${message.type === 'user' ? 'bg-primary text-primary-foreground rounded-br-none' : 'bg-muted text-foreground rounded-bl-none border border-border'}`}>
                  <MessageContent content={message.content} />
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted border border-border px-4 py-3 rounded-2xl rounded-bl-none flex items-center gap-2 text-foreground shadow-sm">
                  <Loader className="h-4 w-4 animate-spin text-primary" />
                  <span className="text-sm font-medium">
                    {language === 'as' ? 'লিখি আছে...' : 'Typing...'}
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          <div className="bg-muted/30 border-t border-border p-4 shrink-0">
            <div className="flex flex-wrap gap-2 justify-center mb-4">
              {quickActions.map(action => (
                <button 
                  key={action.id}
                  onClick={() => handleQuickAction(action.id)}
                  className="bg-background border border-border hover:border-primary/50 hover:bg-muted text-xs px-3 py-1.5 rounded-full shadow-sm transition-all duration-200 flex items-center gap-1.5"
                >
                  <action.icon className="h-3.5 w-3.5 text-primary" />
                  <span className="font-semibold text-foreground/90">
                    {language === 'as' ? action.as : action.en}
                  </span>
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input type="text" value={inputValue} onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSendMessage(); } }}
                placeholder={language === 'as' ? 'যিকোনো প্ৰশ্ন সোধক...' : 'Ask me anything...'}
                className="flex-1 px-4 py-2 bg-background border border-border text-foreground rounded-full focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm shadow-inner" />
              <Button onClick={handleSendMessage} disabled={!inputValue.trim() || isLoading} className="rounded-full h-10 w-10 p-0 shadow-md">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
