'use client';

import { useState, useRef, useEffect } from 'react';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatInput } from '@/components/ChatInput';
import { PhoneCard } from '@/components/PhoneCard';
import { Header } from '@/components/Header';
import { SuggestedQueries } from '@/components/SuggestedQueries';
import { Message, Phone } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedPhones, setSelectedPhones] = useState<Phone[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStatusMessage('Thinking...');

    try {
      // Use streaming endpoint with fetch (better CORS support than EventSource)
      const params = new URLSearchParams({
        message: content,
        ...(sessionId && { session_id: sessionId }),
      });

      const response = await fetch(`${API_URL}/api/chat/stream?${params}`, {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events from buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'status') {
                // Update the status message with LLM-generated text
                setStatusMessage(data.message);
              } else if (data.type === 'complete') {
                // Final response received
                if (!sessionId && data.session_id) {
                  setSessionId(data.session_id);
                }

                const assistantMessage: Message = {
                  id: (Date.now() + 1).toString(),
                  role: 'assistant',
                  content: data.response,
                  phones: data.phones,
                  timestamp: new Date(),
                };

                setMessages((prev) => [...prev, assistantMessage]);
                setIsLoading(false);
                setStatusMessage('');
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error with streaming, falling back to regular chat:', error);

      // Fallback to regular chat endpoint
      try {
        setStatusMessage('Processing...');
        const response = await fetch(`${API_URL}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: content,
            session_id: sessionId,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to get response');
        }

        const data = await response.json();

        if (!sessionId) {
          setSessionId(data.session_id);
        }

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.response,
          phones: data.phones,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
        setStatusMessage('');
      }
    }
  };

  const handleSuggestionClick = (query: string) => {
    sendMessage(query);
  };

  const handlePhoneSelect = (phone: Phone) => {
    setSelectedPhones((prev) => {
      const exists = prev.find((p) => p.id === phone.id);
      if (exists) {
        return prev.filter((p) => p.id !== phone.id);
      }
      if (prev.length >= 3) {
        return [...prev.slice(1), phone];
      }
      return [...prev, phone];
    });
  };

  const handleCompare = () => {
    if (selectedPhones.length >= 2) {
      const names = selectedPhones.map((p) => p.name).join(', ');
      sendMessage(`Compare ${names}`);
      setSelectedPhones([]);
    }
  };

  const clearChat = async () => {
    if (sessionId) {
      try {
        await fetch(`${API_URL}/api/chat/clear?session_id=${sessionId}`, {
          method: 'POST',
        });
      } catch (error) {
        console.error('Error clearing chat:', error);
      }
    }
    setMessages([]);
    setSelectedPhones([]);
  };

  return (
    <main className="flex flex-col h-screen bg-slate-50 dark:bg-slate-900">
      <Header onClearChat={clearChat} />

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-2">
                Welcome to Mobile Shopping Assistant
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-8">
                I can help you find the perfect mobile phone. Ask me anything!
              </p>
              <SuggestedQueries onQueryClick={handleSuggestionClick} />
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message) => (
                <div key={message.id}>
                  <ChatMessage message={message} />
                  {message.phones && message.phones.length > 0 && (
                    <div className="mt-4 ml-12">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {message.phones.map((phone) => (
                          <PhoneCard
                            key={phone.id}
                            phone={phone}
                            isSelected={selectedPhones.some((p) => p.id === phone.id)}
                            onSelect={() => handlePhoneSelect(phone)}
                            onViewDetails={() => sendMessage(`Tell me more about ${phone.name}`)}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-white text-sm font-medium">
                    <svg className="w-5 h-5 spinner" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-primary-500 rounded-full typing-dot"></div>
                        <div className="w-2 h-2 bg-primary-500 rounded-full typing-dot"></div>
                        <div className="w-2 h-2 bg-primary-500 rounded-full typing-dot"></div>
                      </div>
                      <span className="text-sm text-slate-500 dark:text-slate-400 pulse-text">
                        {statusMessage || 'Thinking...'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Comparison bar */}
      {selectedPhones.length > 0 && (
        <div className="bg-primary-600 text-white px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-medium">
                {selectedPhones.length} phone{selectedPhones.length > 1 ? 's' : ''} selected
              </span>
              <div className="flex gap-2">
                {selectedPhones.map((phone) => (
                  <span
                    key={phone.id}
                    className="bg-white/20 px-2 py-1 rounded text-sm"
                  >
                    {phone.name}
                  </span>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setSelectedPhones([])}
                className="px-3 py-1 text-sm bg-white/20 hover:bg-white/30 rounded transition-colors"
              >
                Clear
              </button>
              <button
                onClick={handleCompare}
                disabled={selectedPhones.length < 2}
                className="px-3 py-1 text-sm bg-white text-primary-600 font-medium rounded hover:bg-white/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Compare Now
              </button>
            </div>
          </div>
        </div>
      )}

      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </main>
  );
}
