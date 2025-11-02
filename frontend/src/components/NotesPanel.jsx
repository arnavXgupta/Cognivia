import { ChevronDown, ChevronUp, BookOpen, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';

export const NotesPanel = ({ notes, resources = [], onGenerate, isGenerating = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedNotes, setExpandedNotes] = useState(new Set());

  const toggleNote = (noteId) => {
    const newExpanded = new Set(expandedNotes);
    if (newExpanded.has(noteId)) {
      newExpanded.delete(noteId);
    } else {
      newExpanded.add(noteId);
    }
    setExpandedNotes(newExpanded);
  };

  const hasResources = resources && resources.length > 0;
  const hasNotes = notes && notes.length > 0;

  if (!hasNotes) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            AI-Generated Notes
          </h3>
          {hasResources && onGenerate && (
            <Button
              size="sm"
              variant="secondary"
              onClick={onGenerate}
              disabled={isGenerating}
              icon={Sparkles}
            >
              {isGenerating ? 'Generating...' : 'Generate Notes'}
            </Button>
          )}
        </div>
        <p className="text-white/60 text-sm">
          {hasResources 
            ? 'Click "Generate Notes" to create comprehensive study notes from your resources'
            : 'Upload resources to generate comprehensive study notes'}
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <BookOpen className="w-5 h-5" />
          AI-Generated Notes
        </h3>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-white/60" />
        ) : (
          <ChevronDown className="w-5 h-5 text-white/60" />
        )}
      </div>

      {isExpanded && (
        <div className="mt-4 space-y-3">
          {notes.map((note) => (
            <div
              key={note.id}
              className="border border-white/10 rounded-lg overflow-hidden bg-white/5"
            >
              <button
                onClick={() => toggleNote(note.id)}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
              >
                <h4 className="text-white font-medium text-left">{note.title}</h4>
                {expandedNotes.has(note.id) ? (
                  <ChevronUp className="w-4 h-4 text-white/60 shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-white/60 shrink-0" />
                )}
              </button>
              {expandedNotes.has(note.id) && (
                <div className="px-4 pb-4">
                  <p className="text-white/80 text-sm leading-relaxed">
                    {note.content}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
