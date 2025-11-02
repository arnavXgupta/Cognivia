import { useState } from 'react';
import { Upload } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

export const NewFolderModal = ({ isOpen, onClose, onCreateFolder }) => {
  const [folderName, setFolderName] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (folderName.trim()) {
      onCreateFolder({ name: folderName });
      setFolderName('');
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Subject">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <Input
            placeholder="Enter subject name..."
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            autoFocus
          />
        </div>

        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-white/30 p-8">
          <Upload className="w-10 h-10 text-white/60" />
          <p className="text-sm text-white/80 text-center">
            Upload initial resources (PDFs, YouTube links, etc.) – optional
          </p>
        </div>

        <div className="text-center">
          <button
            type="button"
            onClick={handleSubmit}
            className="text-sm text-white/60 hover:text-white transition-colors"
          >
            Skip for now → Create empty subject
          </button>
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
          <Button variant="secondary" onClick={onClose} type="button">
            Cancel
          </Button>
          <Button type="submit">
            Create Subject
          </Button>
        </div>
      </form>
    </Modal>
  );
};
