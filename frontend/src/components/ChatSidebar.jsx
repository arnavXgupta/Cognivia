import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, AlertCircle } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { api } from '../services/api';

export const ChatSidebar = ({ folderName, folderId, resources = [], chatHistory = [], onSendMessage }) => {
  const [message, setMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;

    // Check if there are resources to chat with
    if (resources.length === 0) {
      setError('Please upload at least one resource to chat with.');
      setTimeout(() => setError(null), 3000);
      return;
    }

    const userMessage = {
      role: 'user',
      content: message
    };

    onSendMessage(userMessage);
    setMessage('');
    setIsTyping(true);
    setError(null);

    try {
      // Use the first resource for chat (in future, could allow selecting specific resource)
      // const resourceId = resources[0].resourceId || parseInt(resources[0].id);
      const preferred = resources.find(r => r.status === 'ready' && r.type === 'pdf')
        || resources.find(r => r.status === 'ready')
        || null;

      if (!preferred) {
        setError('Your resource is still processing or failed. Please wait or re-upload.');
        setTimeout(() => setError(null), 3000);
        return;
      }
      // const preferred = resources.find(r => r.type === 'pdf') || resources[0];
      const resourceId = preferred.resourceId || parseInt(preferred.id);
      
      const response = await api.chatWithResource(resourceId, message);
      
      // Extract answer from response
      const answer = response.answer || response.content || 'Sorry, I could not generate a response.';
      
      const aiResponse = {
        role: 'assistant',
        content: answer
      };
      
      onSendMessage(aiResponse);
    } catch (err) {
      console.error('Error chatting with AI:', err);
      const errorMessage = err.message || 'Failed to get AI response. Please try again.';
      setError(errorMessage);
      
      const aiResponse = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${errorMessage}`
      };
      onSendMessage(aiResponse);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-zinc-900 border-l border-white/10">
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center gap-2 mb-2">
          <div className="bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg p-2">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-white font-semibold">AI Assistant</h3>
            <p className="text-white/60 text-xs">Context: {folderName}</p>
          </div>
        </div>
        <p className="text-white/60 text-xs">
          Ask questions about your uploaded materials
        </p>
      </div>

      {error && (
        <div className="mx-4 mt-2 p-3 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <p className="text-red-400 text-xs">{error}</p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {resources.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-xs">
              <Bot className="w-12 h-12 text-white/40 mx-auto mb-3" />
              <p className="text-white/60 text-sm mb-2">
                No resources uploaded yet
              </p>
              <p className="text-white/40 text-xs">
                Upload PDFs or YouTube videos to start chatting with AI
              </p>
            </div>
          </div>
        ) : chatHistory.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-xs">
              <Bot className="w-12 h-12 text-white/40 mx-auto mb-3" />
              <p className="text-white/60 text-sm">
                Start a conversation! Ask me anything about your {folderName} materials.
              </p>
            </div>
          </div>
        ) : (
          <>
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="bg-blue-500/20 rounded-lg p-2 shrink-0">
                    <Bot className="w-4 h-4 text-blue-400" />
                  </div>
                )}
                <div
                  className={`rounded-lg p-3 max-w-[80%] ${
                    msg.role === 'user'
                      ? 'bg-white text-black'
                      : 'bg-white/10 text-white'
                  }`}
                >
                  <p className="text-sm leading-relaxed">{msg.content}</p>
                </div>
                {msg.role === 'user' && (
                  <div className="bg-white/10 rounded-lg p-2 shrink-0">
                    <User className="w-4 h-4 text-white" />
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="flex gap-3">
                <div className="bg-blue-500/20 rounded-lg p-2 shrink-0">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
                <div className="bg-white/10 rounded-lg p-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-white/10">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            placeholder="Ask a question..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="flex-1 rounded-lg border border-white/20 bg-black/50 px-4 py-2 text-white placeholder:text-white/60 focus:border-white/50 focus:outline-none text-sm"
          />
          <Button type="submit" size="sm" disabled={!message.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
};
