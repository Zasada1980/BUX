import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BadgeStyled as Badge } from '@/components/ui/BadgeStyled';
import { useToast } from '@/hooks/use-toast';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export default function ChatPage() {
  const { toast } = useToast();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [input]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMessage.content,
          history: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });

      if (!response.ok) {
        throw new Error(`Ошибка: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response || data.message || 'Нет ответа',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка отправки',
        description: error instanceof Error ? error.message : 'Не удалось отправить сообщение'
      });

      // Add error message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Ошибка: не удалось получить ответ от AI',
        timestamp: new Date()
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    toast({
      title: 'Чат очищен',
      description: 'История сообщений удалена'
    });
  };

  const exportChat = () => {
    const text = messages.map(m => {
      const time = m.timestamp.toLocaleTimeString('ru-RU');
      const role = m.role === 'user' ? 'Вы' : 'AI';
      return `[${time}] ${role}: ${m.content}`;
    }).join('\n\n');

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    toast({
      title: 'Экспорт выполнен',
      description: 'Чат сохранён в файл'
    });
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
    toast({
      title: 'Скопировано',
      description: 'Сообщение скопировано в буфер обмена'
    });
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* Header */}
      <Card className="border-b rounded-none">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✨</span>
              <div>
                <CardTitle className="text-xl">AI Чат (Ollama)</CardTitle>
                <CardDescription>Задай любой вопрос или попроси помощь</CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={exportChat}
                disabled={messages.length === 0}
              >
                <span className="mr-2">💾</span>
                Экспорт
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clearChat}
                disabled={messages.length === 0}
              >
                <span className="mr-2">🗑️</span>
                Очистить
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-400">
            <div className="text-center">
              <span className="text-6xl opacity-20">✨</span>
              <p className="text-lg">Начни разговор с AI ассистентом</p>
              <p className="text-sm mt-2">Задай вопрос о проекте, коде или попроси совет</p>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[70%] rounded-lg p-4 ${
                  msg.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-white border shadow-sm'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <Badge
                    variant={msg.role === 'user' ? 'default' : 'secondary'}
                    className="text-xs"
                  >
                    {msg.role === 'user' ? 'Вы' : 'AI'}
                  </Badge>
                  <button
                    onClick={() => copyMessage(msg.content)}
                    className="opacity-50 hover:opacity-100 transition-opacity"
                  >
                    <span className="text-xs">📋</span>
                  </button>
                </div>
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                <p
                  className={`text-xs mt-2 ${
                    msg.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                  }`}
                >
                  {msg.timestamp.toLocaleTimeString('ru-RU')}
                </p>
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border rounded-lg p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="animate-pulse flex space-x-1">
                  <div className="h-2 w-2 bg-gray-400 rounded-full"></div>
                  <div className="h-2 w-2 bg-gray-400 rounded-full"></div>
                  <div className="h-2 w-2 bg-gray-400 rounded-full"></div>
                </div>
                <span className="text-sm text-gray-500">AI думает...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <Card className="border-t rounded-none">
        <CardContent className="p-4">
          <div className="flex gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Введите сообщение... (Enter - отправить, Shift+Enter - новая строка)"
              className="flex-1 resize-none border rounded-md p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[60px] max-h-[200px]"
              rows={1}
              disabled={loading}
            />
            <Button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="self-end"
            >
              <span>📤</span>
            </Button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Powered by Ollama • Модель: {loading ? '...' : 'llama2'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
