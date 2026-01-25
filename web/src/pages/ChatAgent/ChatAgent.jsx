import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import WorkspaceGallery from './components/WorkspaceGallery';
import ChatView from './components/ChatView';
import './ChatAgent.css';

/**
 * ChatAgent Component
 * 
 * Main component for the chat module that handles routing:
 * - /chat -> Shows workspace gallery
 * - /chat/:workspaceId -> Shows chat interface for specific workspace
 * 
 * Uses React Router to determine which view to display.
 */
function ChatAgent() {
  const { workspaceId } = useParams();
  const navigate = useNavigate();

  /**
   * Handles workspace selection from gallery
   * Navigates to the chat view for the selected workspace
   * @param {string} selectedWorkspaceId - The selected workspace ID
   */
  const handleWorkspaceSelect = (selectedWorkspaceId) => {
    navigate(`/chat/${selectedWorkspaceId}`);
  };

  /**
   * Handles navigation back to gallery
   */
  const handleBackToGallery = () => {
    navigate('/chat');
  };

  // If workspaceId is provided in URL, show chat view
  if (workspaceId) {
    return <ChatView workspaceId={workspaceId} onBack={handleBackToGallery} />;
  }

  // Otherwise, show workspace gallery
  return <WorkspaceGallery onWorkspaceSelect={handleWorkspaceSelect} />;
}

export default ChatAgent;
