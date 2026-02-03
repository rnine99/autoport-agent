import React, { useState } from 'react';
import { ChevronDown, Globe, Plus, Send, Zap, Loader2 } from 'lucide-react';
import { Card, CardContent } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { useNavigate } from 'react-router-dom';
import { getWorkspaces, createWorkspace, DEFAULT_USER_ID } from '../../ChatAgent/utils/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../../components/ui/dialog';
import { useToast } from '../../../components/ui/use-toast';

const DEFAULT_WORKSPACE_NAME = 'Stealth Agent';
const DEFAULT_WORKSPACE_DESCRIPTION = 'system default workspace, cannot be deleted';

/**
 * Chat input strip matching ChatAgent input bar.
 * When user sends a message, navigates to ChatAgent page with "Stealth Agent" workspace.
 * Creates the workspace if it doesn't exist.
 */
function ChatInputCard() {
  const [message, setMessage] = useState('');
  const [planMode, setPlanMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreatingDialog, setShowCreatingDialog] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  /**
   * Finds or creates the "Stealth Agent" workspace
   * @returns {Promise<string>} The workspace ID
   */
  const findOrCreateDefaultWorkspace = async () => {
    // Fetch user's workspaces
    const { workspaces } = await getWorkspaces(DEFAULT_USER_ID);
    
    // Look for "Stealth Agent" workspace
    const stealthAgentWorkspace = workspaces?.find(
      (ws) => ws.name === DEFAULT_WORKSPACE_NAME
    );
    
    if (stealthAgentWorkspace) {
      return stealthAgentWorkspace.workspace_id;
    }
    
    // If not found, create it
    setShowCreatingDialog(true);
    try {
      const newWorkspace = await createWorkspace(
        DEFAULT_WORKSPACE_NAME,
        DEFAULT_WORKSPACE_DESCRIPTION
      );
      setShowCreatingDialog(false);
      return newWorkspace.workspace_id;
    } catch (error) {
      setShowCreatingDialog(false);
      throw error;
    }
  };

  const handleSend = async () => {
    if (!message.trim() || isLoading) {
      return;
    }

    setIsLoading(true);
    try {
      // Find or create "Stealth Agent" workspace
      const workspaceId = await findOrCreateDefaultWorkspace();

      // Navigate to ChatAgent page with workspace and message in state
      navigate(`/chat/${workspaceId}`, {
        state: {
          initialMessage: message.trim(),
          planMode: planMode,
        },
      });
      
      // Clear input
      setMessage('');
    } catch (error) {
      console.error('Error with workspace:', error);
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to access workspace. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <Card
        className="fin-card flex-shrink-0"
        style={{ borderColor: 'var(--color-accent-primary)', borderWidth: '1.5px' }}
      >
        <CardContent className="p-3">
          <div className="flex items-center gap-1">
            <button 
              className="w-9 h-9 flex items-center justify-center rounded-md transition-colors hover:bg-white/5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <Plus className="h-4 w-4" />
            </button>
            <Input
              placeholder="What would you like to know?"
              className="flex-1 h-9 rounded-md text-sm focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
              style={{
                backgroundColor: 'transparent',
                border: 'none',
                color: 'var(--color-text-muted)',
                fontSize: '14px',
                outline: 'none',
              }}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
            <div className="flex items-center gap-1">
              <button 
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors hover:bg-white/5"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <Globe className="h-4 w-4" />
                <span className="text-sm font-medium">Agent</span>
              </button>
              <button
                className={`flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors ${
                  planMode ? 'bg-white/100' : 'hover:bg-white/5'
                }`}
                style={{ color: 'var(--color-text-muted)' }}
                onClick={() => setPlanMode(!planMode)}
              >
                <Zap className="h-4 w-4" />
                <span className="text-sm font-medium">Plan Mode</span>
              </button>
              <button 
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors hover:bg-white/5"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <span className="text-sm font-medium">Tool</span>
                <ChevronDown className="h-4 w-4" />
              </button>
              <button
                className="w-8 h-9 rounded-md flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ 
                  backgroundColor: (isLoading || !message.trim()) ? 'rgba(97, 85, 245, 0.5)' : 'var(--color-accent-primary)',
                  color: 'var(--color-text-on-accent)',
                }}
                onClick={handleSend}
                disabled={isLoading || !message.trim()}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Creating Workspace Dialog */}
      <Dialog open={showCreatingDialog} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md text-white border" style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}>
          <DialogHeader>
            <DialogTitle className="dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
              Creating Workspace
            </DialogTitle>
            <DialogDescription style={{ color: 'var(--color-text-secondary)' }}>
              Creating your default "Stealth Agent" workspace. Please wait...
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--color-accent-primary)' }} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default ChatInputCard;
