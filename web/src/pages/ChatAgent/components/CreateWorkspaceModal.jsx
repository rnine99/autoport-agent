import React, { useState } from 'react';
import { X } from 'lucide-react';
import { Input } from '../../../components/ui/input';

/**
 * CreateWorkspaceModal Component
 * 
 * Modal dialog for creating a new workspace.
 * Allows user to input:
 * - Workspace name (required)
 * - Workspace description (optional)
 * 
 * @param {boolean} isOpen - Whether the modal is open
 * @param {Function} onClose - Callback to close the modal
 * @param {Function} onCreate - Callback when workspace is created (receives {name, description})
 */
function CreateWorkspaceModal({ isOpen, onClose, onCreate }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!name.trim()) {
      setError('Workspace name is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onCreate({ name: name.trim(), description: description.trim() });
      // Reset form on success
      setName('');
      setDescription('');
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to create workspace');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}
      onClick={handleClose}
    >
      <div
        className="relative w-full max-w-md rounded-lg p-6"
        style={{
          backgroundColor: '#1B1D25',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-1 rounded-full transition-colors hover:bg-white/10"
          style={{ color: '#FFFFFF' }}
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <h2 className="text-xl font-semibold mb-4" style={{ color: '#FFFFFF' }}>
          Create New Workspace
        </h2>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name input */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: '#FFFFFF' }}>
              Workspace Name <span style={{ color: '#FF383C' }}>*</span>
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter workspace name"
              className="w-full"
              style={{
                backgroundColor: '#0A0A0A',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#FFFFFF',
              }}
              disabled={isSubmitting}
              autoFocus
            />
          </div>

          {/* Description input */}
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: '#FFFFFF' }}>
              Description <span style={{ color: '#999999', fontSize: '12px' }}>(Optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter workspace description"
              rows={3}
              className="w-full rounded-md px-3 py-2 text-sm resize-none"
              style={{
                backgroundColor: '#0A0A0A',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#FFFFFF',
              }}
              disabled={isSubmitting}
            />
          </div>

          {/* Error message */}
          {error && (
            <p className="text-sm" style={{ color: '#FF383C' }}>
              {error}
            </p>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 justify-end pt-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors hover:bg-white/10"
              style={{ color: '#FFFFFF' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                backgroundColor: isSubmitting || !name.trim() ? 'rgba(97, 85, 245, 0.5)' : '#6155F5',
                color: '#FFFFFF',
              }}
            >
              {isSubmitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateWorkspaceModal;
