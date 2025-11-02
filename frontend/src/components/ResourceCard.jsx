import { FileText, Video, Trash2 } from 'lucide-react';
import { Card } from './ui/Card';
import { useState } from 'react';

export const ResourceCard = ({ resource, onDelete }) => {
  const [showDelete, setShowDelete] = useState(false);

  const handleDelete = (e) => {
    e.stopPropagation();
    if (window.confirm(`Delete "${resource.name}"?`)) {
      onDelete(resource.id);
    }
  };

  const Icon = resource.type === 'youtube' ? Video : FileText;

  return (
    <Card
      hover
      className="p-4 relative group"
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
    >
      {showDelete && (
        <button
          onClick={handleDelete}
          className="absolute top-3 right-3 text-white/40 hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}

      <div className="flex items-start gap-3">
        <div className="bg-white/10 rounded-lg p-2 shrink-0">
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium leading-normal truncate">
            {resource.name}
          </p>
          <p className="text-white/60 text-xs mt-1">
            {resource.type === 'youtube' ? 'YouTube Video' : 'PDF Document'}
          </p>
        </div>
      </div>
    </Card>
  );
};
