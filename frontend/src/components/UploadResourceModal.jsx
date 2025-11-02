import { useState } from 'react';
import { Upload, FileText, Youtube, AlertCircle } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

export const UploadResourceModal = ({ isOpen, onClose, onAddResource, folderId }) => {
  const [activeTab, setActiveTab] = useState('pdf');
  const [pdfFile, setPdfFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [resourceName, setResourceName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsUploading(true);

    try {
      if (activeTab === 'pdf' && pdfFile) {
        await onAddResource(folderId, {
          type: 'pdf',
          name: resourceName || pdfFile.name,
          file: pdfFile
        });
        setPdfFile(null);
        setResourceName('');
        onClose();
      } else if (activeTab === 'youtube' && youtubeUrl) {
        await onAddResource(folderId, {
          type: 'youtube',
          name: resourceName || 'YouTube Video',
          url: youtubeUrl
        });
        setYoutubeUrl('');
        setResourceName('');
        onClose();
      }
    } catch (err) {
      console.error('Error adding resource:', err);
      setError(err.message || 'Failed to upload resource. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file && file.type === 'application/pdf') {
      setPdfFile(file);
    } else {
      alert('Please select a PDF file');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Resource">
      <div className="space-y-6">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('pdf')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'pdf'
                ? 'bg-white text-black'
                : 'bg-white/10 text-white hover:bg-white/20'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            PDF Upload
          </button>
          <button
            onClick={() => setActiveTab('youtube')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'youtube'
                ? 'bg-white text-black'
                : 'bg-white/10 text-white hover:bg-white/20'
            }`}
          >
            <Youtube className="w-4 h-4 inline mr-2" />
            YouTube Link
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {activeTab === 'pdf' ? (
            <div>
              <label
                htmlFor="file-upload"
                className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-white/30 p-8 cursor-pointer hover:border-white/50 transition-colors"
              >
                <Upload className="w-10 h-10 text-white/60" />
                <div className="text-center">
                  <p className="text-sm text-white/80 mb-1">
                    {pdfFile ? pdfFile.name : 'Click to upload PDF'}
                  </p>
                  <p className="text-xs text-white/60">or drag and drop</p>
                </div>
              </label>
              <input
                id="file-upload"
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                YouTube URL
              </label>
              <Input
                type="url"
                placeholder="https://youtube.com/watch?v=..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">
              Resource Name (Optional)
            </label>
            <Input
              placeholder="Enter a custom name..."
              value={resourceName}
              onChange={(e) => setResourceName(e.target.value)}
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
            <Button variant="secondary" onClick={onClose} type="button" disabled={isUploading}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isUploading ||
                (activeTab === 'pdf' && !pdfFile) ||
                (activeTab === 'youtube' && !youtubeUrl)
              }
            >
              {isUploading ? 'Uploading...' : 'Add Resource'}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
