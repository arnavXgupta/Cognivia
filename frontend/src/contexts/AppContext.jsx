import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

const AppContext = createContext();

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
};

export const AppProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Store chat history and generated content per folder
  const [folderData, setFolderData] = useState({}); // { folderId: { chatHistory, notes, studyPlan } }

  // Fetch all folders on mount and when needed
  const fetchFolders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const fetchedFolders = await api.getFolders();
      
      // Transform backend data to frontend format
      const transformedFolders = fetchedFolders.map(folder => ({
        id: folder.id.toString(),
        name: folder.name,
        resources: [], // Will be populated when folder is viewed
        studyPlan: folderData[folder.id]?.studyPlan || { weeks: [] },
        notes: folderData[folder.id]?.notes || [],
        chatHistory: folderData[folder.id]?.chatHistory || [],
      }));
      
      setFolders(transformedFolders);
    } catch (err) {
      console.error('Error fetching folders:', err);
      setError(err.message || 'Failed to fetch folders');
    } finally {
      setLoading(false);
    }
  }, [folderData]);

  // Fetch folder details (including resources)
  const fetchFolderDetails = useCallback(async (folderId) => {
    try {
      const folderDetail = await api.getFolder(parseInt(folderId));
      
      // Transform resources
      const resources = folderDetail.resources.map(resource => ({
        id: resource.id.toString(),
        type: resource.resource_type,
        name: resource.source_id,
        sourceId: resource.source_id,
        resourceId: resource.id,
      }));

      // Update folder in state
      setFolders(prevFolders => 
        prevFolders.map(f => {
          if (f.id === folderId) {
            return {
              ...f,
              resources,
            };
          }
          return f;
        })
      );

      return { ...folderDetail, resources };
    } catch (err) {
      console.error('Error fetching folder details:', err);
      throw err;
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchFolders();
    }
  }, [isAuthenticated, fetchFolders]);

  const login = async (email, password) => {
    // For now, simple auth - in production, validate with backend
    setIsAuthenticated(true);
    setUser({ email, name: email.split('@')[0] });
    return true;
  };

  const logout = () => {
    setIsAuthenticated(false);
    setUser(null);
    setFolders([]);
    setFolderData({});
  };

  const addFolder = async (folderData) => {
    try {
      const newFolder = await api.createFolder(folderData.name);
      const transformed = {
        id: newFolder.id.toString(),
        name: newFolder.name,
        resources: [],
        studyPlan: { weeks: [] },
        notes: [],
        chatHistory: [],
      };
      setFolders(prev => [...prev, transformed]);
      return transformed;
    } catch (err) {
      console.error('Error creating folder:', err);
      throw err;
    }
  };

  const deleteFolder = async (folderId) => {
    try {
      await api.deleteFolder(parseInt(folderId));
      setFolders(prev => prev.filter(f => f.id !== folderId));
      // Clean up folder data
      setFolderData(prev => {
        const updated = { ...prev };
        delete updated[parseInt(folderId)];
        return updated;
      });
    } catch (err) {
      console.error('Error deleting folder:', err);
      throw err;
    }
  };

  const addResource = async (folderId, resource) => {
    try {
      let newResource;
      if (resource.type === 'youtube') {
        newResource = await api.addYouTubeResource(parseInt(folderId), [resource.url]);
      } else if (resource.type === 'pdf') {
        newResource = await api.uploadPDFResource(parseInt(folderId), resource.file);
      } else {
        throw new Error('Unknown resource type');
      }

      const transformed = {
        id: newResource.id.toString(),
        type: newResource.resource_type,
        name: newResource.source_id,
        sourceId: newResource.source_id,
        resourceId: newResource.id,
      };

      setFolders(prevFolders => 
        prevFolders.map(folder => {
          if (folder.id === folderId) {
            return {
              ...folder,
              resources: [...folder.resources, transformed]
            };
          }
          return folder;
        })
      );

      return transformed;
    } catch (err) {
      console.error('Error adding resource:', err);
      throw err;
    }
  };

  const deleteResource = async (folderId, resourceId) => {
    try {
      await api.deleteResource(parseInt(resourceId));
      setFolders(prevFolders => 
        prevFolders.map(folder => {
          if (folder.id === folderId) {
            return {
              ...folder,
              resources: folder.resources.filter(r => r.id !== resourceId)
            };
          }
          return folder;
        })
      );
    } catch (err) {
      console.error('Error deleting resource:', err);
      throw err;
    }
  };

  const addChatMessage = (folderId, message) => {
    const folderIdNum = parseInt(folderId);
    const messageWithId = { ...message, id: Date.now().toString() };
    
    // Update folder data
    setFolderData(prev => ({
      ...prev,
      [folderIdNum]: {
        ...prev[folderIdNum],
        chatHistory: [...(prev[folderIdNum]?.chatHistory || []), messageWithId]
      }
    }));

    // Update folders state
    setFolders(prevFolders => 
      prevFolders.map(folder => {
        if (folder.id === folderId) {
          return {
            ...folder,
            chatHistory: [...folder.chatHistory, messageWithId]
          };
        }
        return folder;
      })
    );
  };

  const generateNotes = async (resourceId) => {
    try {
      const response = await api.generateNotes(parseInt(resourceId));
      // Parse the notes response - it might be a string or structured data
      let notes = [];
      if (response.notes) {
        // If notes is a string, try to parse it or split it into sections
        if (typeof response.notes === 'string') {
          // Simple parsing - split by headings or paragraphs
          const sections = response.notes.split(/\n\n+/).filter(Boolean);
          notes = sections.map((section, idx) => ({
            id: `note-${resourceId}-${idx}`,
            title: section.split('\n')[0] || `Note ${idx + 1}`,
            content: section,
          }));
        } else if (Array.isArray(response.notes)) {
          notes = response.notes;
        }
      }
      return notes;
    } catch (err) {
      console.error('Error generating notes:', err);
      throw err;
    }
  };

  const generateStudyPlan = async (resourceId, knowledgeLevel = 'beginner', learningStyle = 'active') => {
    try {
      const response = await api.generateStudyPlan(parseInt(resourceId), knowledgeLevel, learningStyle);
      // Parse study plan - convert to expected format
      let studyPlan = { weeks: [] };
      if (response.study_plan) {
        // Parse the study plan string if needed
        // For now, return a basic structure
        studyPlan = typeof response.study_plan === 'string' 
          ? parseStudyPlanString(response.study_plan)
          : response.study_plan;
      }
      return studyPlan;
    } catch (err) {
      console.error('Error generating study plan:', err);
      throw err;
    }
  };

  // Helper to parse study plan string (basic implementation)
  const parseStudyPlanString = (planStr) => {
    // This is a simple parser - you might want to enhance this
    const weeks = [];
    const weekMatches = planStr.match(/Week \d+/gi);
    if (weekMatches) {
      weekMatches.forEach((match, idx) => {
        weeks.push({
          week: idx + 1,
          topics: ['Study plan content'],
          hours: 8,
        });
      });
    }
    return { weeks };
  };

  const updateFolderNotes = (folderId, notes) => {
    setFolders(prevFolders => 
      prevFolders.map(f => {
        if (f.id === folderId) {
          return { ...f, notes };
        }
        return f;
      })
    );
  };

  const updateFolderStudyPlan = (folderId, studyPlan) => {
    setFolders(prevFolders => 
      prevFolders.map(f => {
        if (f.id === folderId) {
          return { ...f, studyPlan };
        }
        return f;
      })
    );
  };

  return (
    <AppContext.Provider value={{
      isAuthenticated,
      user,
      folders,
      loading,
      error,
      login,
      logout,
      addFolder,
      deleteFolder,
      addResource,
      deleteResource,
      addChatMessage,
      fetchFolderDetails,
      generateNotes,
      generateStudyPlan,
      updateFolderNotes,
      updateFolderStudyPlan,
      refreshFolders: fetchFolders,
    }}>
      {children}
    </AppContext.Provider>
  );
};
