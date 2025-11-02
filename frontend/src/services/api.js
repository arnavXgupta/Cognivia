// Frontend API service for communicating with the backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8008';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new ApiError(
        data.detail || data.message || `HTTP error! status: ${response.status}`,
        response.status,
        data
      );
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error.message || 'Network error',
      error.status || 0,
      null
    );
  }
}

export const api = {
  // Folder operations
  async getFolders() {
    return fetchAPI('/folders');
  },

  async getFolder(folderId) {
    return fetchAPI(`/folders/${folderId}`);
  },

  async createFolder(name) {
    return fetchAPI('/folders', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  },

  async deleteFolder(folderId) {
    return fetchAPI(`/folders/${folderId}`, {
      method: 'DELETE',
    });
  },

  // Resource operations
  async addYouTubeResource(folderId, urls) {
    return fetchAPI(`/folders/${folderId}/add-youtube`, {
      method: 'POST',
      body: JSON.stringify({ urls }),
    });
  },

  async uploadPDFResource(folderId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${API_BASE_URL}/folders/${folderId}/upload-pdf`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new ApiError(
        data.detail || `HTTP error! status: ${response.status}`,
        response.status,
        data
      );
    }

    return response.json();
  },

  async deleteResource(resourceId) {
    return fetchAPI(`/resources/${resourceId}`, {
      method: 'DELETE',
    });
  },

  // AI operations
  async chatWithResource(resourceId, query) {
    return fetchAPI(`/resources/${resourceId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  },

  async generateNotes(resourceId) {
    return fetchAPI(`/resources/${resourceId}/generate-notes`, {
      method: 'POST',
    });
  },

  async generateStudyPlan(resourceId, knowledgeLevel = 'beginner', learningStyle = 'active') {
    return fetchAPI(`/resources/${resourceId}/generate-study-plan`, {
      method: 'POST',
      body: JSON.stringify({ knowledge_level: knowledgeLevel, learning_style: learningStyle }),
    });
  },
};

export { ApiError };


