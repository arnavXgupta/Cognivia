import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Upload, Plus } from 'lucide-react';
import { useAppContext } from '../contexts/AppContext';
import { Button } from '../components/ui/Button';
import { ResourceCard } from '../components/ResourceCard';
import { UploadResourceModal } from '../components/UploadResourceModal';
import { StudyPlanPanel } from '../components/StudyPlanPanel';
import { NotesPanel } from '../components/NotesPanel';
import { ChatSidebar } from '../components/ChatSidebar';

export const FolderView = () => {
  const { folderId } = useParams();
  const navigate = useNavigate();
  const { folders, addResource, deleteResource, addChatMessage, fetchFolderDetails, generateNotes, generateStudyPlan, updateFolderNotes, updateFolderStudyPlan, loading } = useAppContext();
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false);
  const [isGeneratingStudyPlan, setIsGeneratingStudyPlan] = useState(false);

  const folder = folders.find((f) => f.id === folderId);

  // Fetch folder details when component mounts or folderId changes
  useEffect(() => {
    if (folderId && !folder?.resources?.length) {
      setIsFetching(true);
      fetchFolderDetails(folderId)
        .catch(err => console.error('Error fetching folder details:', err))
        .finally(() => setIsFetching(false));
    }
  }, [folderId, folder?.resources?.length, fetchFolderDetails]);

  if (loading || isFetching) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white/60">Loading folder...</p>
        </div>
      </div>
    );
  }

  if (!folder) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Folder not found</h2>
          <Button onClick={() => navigate('/dashboard')}>
            Return to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const handleAddResource = async (folderId, resource) => {
    try {
      await addResource(folderId, resource);
    } catch (error) {
      console.error('Error adding resource:', error);
      alert(error.message || 'Failed to add resource. Please try again.');
    }
  };

  const handleDeleteResource = async (resourceId) => {
    try {
      await deleteResource(folderId, resourceId);
    } catch (error) {
      console.error('Error deleting resource:', error);
      alert(error.message || 'Failed to delete resource. Please try again.');
    }
  };

  const handleSendMessage = (message) => {
    addChatMessage(folderId, message);
  };

  const handleGenerateNotes = async () => {
    if (!folder.resources || folder.resources.length === 0) {
      alert('Please upload at least one resource to generate notes.');
      return;
    }

    setIsGeneratingNotes(true);
    try {
      const resourceId = folder.resources[0].resourceId || parseInt(folder.resources[0].id);
      const notes = await generateNotes(resourceId);
      updateFolderNotes(folderId, notes);
    } catch (error) {
      console.error('Error generating notes:', error);
      alert(error.message || 'Failed to generate notes. Please try again.');
    } finally {
      setIsGeneratingNotes(false);
    }
  };

  const handleGenerateStudyPlan = async () => {
    if (!folder.resources || folder.resources.length === 0) {
      alert('Please upload at least one resource to generate a study plan.');
      return;
    }

    setIsGeneratingStudyPlan(true);
    try {
      const resourceId = folder.resources[0].resourceId || parseInt(folder.resources[0].id);
      const studyPlan = await generateStudyPlan(resourceId);
      updateFolderStudyPlan(folderId, studyPlan);
    } catch (error) {
      console.error('Error generating study plan:', error);
      alert(error.message || 'Failed to generate study plan. Please try again.');
    } finally {
      setIsGeneratingStudyPlan(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-black">
      <header className="border-b border-white/10 bg-black/50 backdrop-blur-sm">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/dashboard')}
                className="text-white/60 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-2xl font-bold text-white">{folder.name}</h1>
            </div>
            <Button icon={Upload} onClick={() => setIsUploadModalOpen(true)}>
              Add Resource
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto p-6 space-y-8">
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-white">Resources</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Plus}
                  onClick={() => setIsUploadModalOpen(true)}
                >
                  Add
                </Button>
              </div>

              {folder.resources.length === 0 ? (
                <div className="text-center py-12 border-2 border-dashed border-white/20 rounded-lg">
                  <Upload className="w-12 h-12 text-white/40 mx-auto mb-3" />
                  <p className="text-white/60 mb-4">No resources yet</p>
                  <Button
                    variant="secondary"
                    onClick={() => setIsUploadModalOpen(true)}
                  >
                    Upload First Resource
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {folder.resources.map((resource) => (
                    <ResourceCard
                      key={resource.id}
                      resource={resource}
                      onDelete={handleDeleteResource}
                    />
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="text-xl font-semibold text-white mb-4">
                AI-Generated Content
              </h2>
              <div className="space-y-4">
                <StudyPlanPanel 
                  studyPlan={folder.studyPlan} 
                  resources={folder.resources}
                  onGenerate={handleGenerateStudyPlan}
                  isGenerating={isGeneratingStudyPlan}
                />
                <NotesPanel 
                  notes={folder.notes} 
                  resources={folder.resources}
                  onGenerate={handleGenerateNotes}
                  isGenerating={isGeneratingNotes}
                />
              </div>
            </section>
          </div>
        </main>

        <aside className="w-96 flex-shrink-0 hidden lg:flex">
          <ChatSidebar
            folderName={folder.name}
            folderId={folder.id}
            resources={folder.resources}
            chatHistory={folder.chatHistory}
            onSendMessage={handleSendMessage}
          />
        </aside>
      </div>

      <div className="lg:hidden fixed bottom-4 right-4">
        <Button
          onClick={() => alert('Mobile chat view - In production, this would open a full-screen chat modal')}
          className="rounded-full w-14 h-14 shadow-lg"
        >
          💬
        </Button>
      </div>

      <UploadResourceModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onAddResource={handleAddResource}
        folderId={folderId}
      />
    </div>
  );
};
