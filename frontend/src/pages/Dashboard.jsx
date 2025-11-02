import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, LogOut } from 'lucide-react';
import { useAppContext } from '../contexts/AppContext';
import { FolderCard } from '../components/FolderCard';
import { NewFolderModal } from '../components/NewFolderModal';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

export const Dashboard = () => {
  const { folders, addFolder, deleteFolder, user, logout } = useAppContext();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const handleCreateFolder = async (folderData) => {
    try {
      await addFolder(folderData);
    } catch (error) {
      console.error('Error creating folder:', error);
      alert(error.message || 'Failed to create folder. Please try again.');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const filteredFolders = folders.filter(folder =>
    folder.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-black">
      <header className="border-b border-white/10 bg-black/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white">My Subjects</h1>
              {user && (
                <p className="text-white/60 text-sm mt-1">Welcome back, {user.name}</p>
              )}
            </div>
            <Button variant="ghost" onClick={handleLogout} icon={LogOut}>
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row gap-4 mb-8">
          <div className="flex-1">
            <Input
              placeholder="Search subjects..."
              icon={Search}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button icon={Plus} onClick={() => setIsModalOpen(true)}>
            New Subject
          </Button>
        </div>

        {filteredFolders.length === 0 ? (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-white/5 rounded-full mb-4">
              <Plus className="w-10 h-10 text-white/40" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">
              {searchQuery ? 'No subjects found' : 'No subjects yet'}
            </h3>
            <p className="text-white/60 mb-6">
              {searchQuery
                ? 'Try a different search term'
                : 'Create your first subject folder to get started'}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsModalOpen(true)} icon={Plus}>
                Create Subject
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredFolders.map((folder) => (
              <FolderCard
                key={folder.id}
                folder={folder}
                onClick={() => navigate(`/folder/${folder.id}`)}
                onDelete={async (folderId) => {
                  if (window.confirm('Are you sure you want to delete this folder? This action cannot be undone.')) {
                    try {
                      await deleteFolder(folderId);
                    } catch (error) {
                      console.error('Error deleting folder:', error);
                      alert(error.message || 'Failed to delete folder. Please try again.');
                    }
                  }
                }}
              />
            ))}
          </div>
        )}
      </main>

      <NewFolderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreateFolder={handleCreateFolder}
      />
    </div>
  );
};
