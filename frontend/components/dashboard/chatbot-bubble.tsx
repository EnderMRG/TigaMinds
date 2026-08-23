'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { MessageCircle, X, Send, Loader } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface Message {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
}

// Component to render message content with proper line breaks and formatting
const MessageContent = ({ content }: { content: string }) => {
  const lines = content.split('\n');

  return (
    <div className="space-y-1">
      {lines.map((line, idx) => {
        // Handle bullet points and numbered lists
        if (line.match(/^[\s]*[-•*]/)) {
          return (
            <div key={idx} className="ml-3 text-sm leading-relaxed">
              {line}
            </div>
          );
        }
        if (line.match(/^[\s]*\d+\./)) {
          return (
            <div key={idx} className="ml-3 text-sm leading-relaxed">
              {line}
            </div>
          );
        }
        // Regular text
        return (
          <div key={idx} className="text-sm leading-relaxed">
            {line}
          </div>
        );
      })}
    </div>
  );
};

export default function ChatbotBubble() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'bot',
      content: 'Hello! I\'m CHAI-NET Assistant. How can I help you today? Ask me about cultivation tips, leaf quality, market trends, or any other farming advice.',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const suggestedQuestions = [
    'How to improve leaf quality?',
    'Best irrigation schedule?',
    'Current market prices?',
    'Pest prevention tips?',
  ];

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // Prepare chat history for API
      const history = messages.map(msg => ({
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content
      }));

      // Call backend API with authentication
      const data = await apiClient.post('/api/chat', {
        message: inputValue,
        history: history
      });

      const botResponse: Message = {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botResponse]);

      // Add suggested actions as separate messages if present
      if (data.suggested_actions && data.suggested_actions.length > 0) {
        const actionsMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: 'bot',
          content: '💡 Suggested Actions:\n' + data.suggested_actions.map((action: string, idx: number) => `${idx + 1}. ${action}`).join('\n'),
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, actionsMessage]);
      }

      setIsLoading(false);
    } catch (error) {
      console.error('❌ Chat API error, using client-side fallback:', error);

      // Client-side fallback
      const botResponse: Message = {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        content: generateBotResponse(inputValue),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botResponse]);
      setIsLoading(false);
    }
  };

  const generateBotResponse = (userInput: string): string => {
    const input = userInput.toLowerCase();

    if (input.includes('leaf quality') || input.includes('improve leaf')) {
      return 'To improve leaf quality, ensure consistent soil moisture (55-65%), maintain optimal temperature (22-25°C), and apply balanced fertilizers. Also monitor for pests regularly and ensure adequate light exposure. Our AI scanner can help grade your leaves in real-time!';
    }
    if (input.includes('irrigation') || input.includes('water')) {
      return 'For tea plants, irrigation depends on season and soil type. During growing season: 2-3 times weekly. Use drip irrigation for efficiency. Monitor soil moisture with our IoT sensors. Current moisture in your fields: Field A (58%), Field B (62%).';
    }
    if (input.includes('market') || input.includes('price')) {
      return 'Current market trends show 8% price increase expected in the next 7-10 days. Demand for premium grades (A/B) is rising. Check the Market Intelligence tab for detailed forecasts and optimal selling windows.';
    }
    if (input.includes('pest') || input.includes('disease')) {
      return 'Common tea plant pests: Green leaf hopper, Scale insect, and Tea mosquito. Prevention: Regular scouting, integrated pest management, organic neem spray. Quarantine affected plants. Early detection is key!';
    }
    if (input.includes('fertilizer') || input.includes('nutrient')) {
      return 'Tea plants need NPK ratio around 4:2:2. Apply 500-750 kg/hectare annually. Use organic matter to improve soil structure. Split applications: after each harvest. Foliar feeding with micronutrients boosts quality. Soil test results recommended.';
    }
    if (input.includes('harvest') || input.includes('picking')) {
      return 'Harvest tea leaves at the 2-3 leaf stage for best quality. Morning picking (after dew dries) is preferred. Use two leaves + bud (2LB) for premium grades. Our AI recommendations suggest optimal harvest timing based on current conditions.';
    }

    return 'That\'s a great question! Based on your current farm data, I recommend checking the relevant dashboard tab for detailed insights. You can also schedule a consultation with our agricultural expert. Is there anything specific I can help clarify?';
  };

  const handleSuggestedQuestion = (question: string) => {
    setInputValue(question);
  };

  return (
    <>
      {/* Chatbot Bubble Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-40 p-4 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:shadow-primary/30 transition-all duration-300 hover:scale-110 active:scale-95"
        aria-label="Open chat"
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <Card className="fixed bottom-24 right-6 z-40 w-96 max-w-[calc(100vw-24px)] shadow-2xl border-0 rounded-2xl overflow-hidden flex flex-col max-h-[600px] animate-in fade-in slide-in-from-bottom-4 duration-300">
          {/* Header */}
          <div className="bg-gradient-to-r from-primary to-primary/80 text-primary-foreground p-4 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-lg">CHAI-NET Assistant</h3>
              <p className="text-xs opacity-90">Always here to help</p>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-background">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs px-4 py-3 rounded-2xl ${message.type === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-none'
                    : 'bg-muted text-foreground rounded-bl-none'
                    }`}
                >
                  <MessageContent content={message.content} />
                  <p className={`text-xs mt-2 ${message.type === 'user' ? 'opacity-75' : 'text-muted-foreground'}`}>
                    {message.timestamp.toLocaleTimeString('en-US', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted text-foreground px-4 py-3 rounded-2xl rounded-bl-none flex items-center gap-2">
                  <Loader className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Typing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Questions */}
          {messages.length === 1 && (
            <div className="px-4 py-3 bg-muted/20 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Quick questions:</p>
              <div className="flex flex-wrap gap-2">
                {suggestedQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestedQuestion(question)}
                    className="text-xs px-3 py-1.5 bg-primary/15 text-primary hover:bg-primary/25 rounded-full transition-colors"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="p-4 bg-background space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask me anything..."
                className="flex-1 px-4 py-2 rounded-full bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
              />
              <Button
                onClick={handleSendMessage}
                disabled={!inputValue.trim() || isLoading}
                className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-full h-10 w-10 p-0 flex items-center justify-center"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
