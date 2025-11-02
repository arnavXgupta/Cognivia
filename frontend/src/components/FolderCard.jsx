import { Folder, FileText, Trash2 } from 'lucide-react';
import { Card } from './ui/Card';
import { useState } from 'react';

export const FolderCard = ({ folder, onClick, onDelete }) => {
  const [showDelete, setShowDelete] = useState(false);

  const handleDelete = (e) => {
    e.stopPropagation();
    if (window.confirm(`Delete "${folder.name}"? This action cannot be undone.`)) {
      onDelete(folder.id);
    }
  };

  return (
    <Card
      hover
      onClick={onClick}
      className="p-6 relative group"
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
    >
      {showDelete && (
        <button
          onClick={handleDelete}
          className="absolute top-4 right-4 text-white/40 hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}

      <div className="flex items-start gap-4">
        <div className="bg-white/10 rounded-lg p-3">
          <Folder className="w-8 h-8 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-white mb-2 truncate">
            {folder.name}
          </h3>
          <div className="flex items-center gap-2 text-white/60 text-sm">
            <FileText className="w-4 h-4" />
            <span>{folder.resources.length} resources</span>
          </div>
        </div>
      </div>
    </Card>
  );
};
