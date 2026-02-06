import React, { useState, useEffect } from 'react';
import { Edit2, X } from 'lucide-react';
import { Input } from '../../../components/ui/input';

/**
 * RenameThreadModal Component
 * 
 * Modal for renaming a thread.
 * 
 * @param {boolean} isOpen - Whether the modal is open
 * @param {string} currentTitle - Current thread title
 * @param {Function} onConfirm - Callback when user confirms rename (receives new title)
 * @param {Function} onCancel - Callback when user cancels
 * @param {boolean} isRenaming - Whether rename is in progress
 * @param {string} error - Error message to display (optional)
 */
function RenameThreadModal({ isOpen, currentTitle, onConfirm, onCancel, isRenaming, error }) {
  const [newTitle, setNewTitle] = useState('');

  // Reset form when modal opens/closes or currentTitle changes
  useEffect(() => {
    if (isOpen) {
      setNewTitle(currentTitle || '');
    } else {
      setNewTitle('');
    }
  }, [isOpen, currentTitle]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (newTitle.trim() && !isRenaming) {
      onConfirm(newTitle.trim());
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)' }}
      onClick={onCancel}
    >
      <div
        className="relative w-full max-w-md rounded-lg p-6"
        style={{
          backgroundColor: '#1B1D25',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: 'rgba(97, 85, 245, 0.2)' }}
            >
              <Edit2 className="h-5 w-5" style={{ color: '#6155F5' }} />
            </div>
            <h2 className="text-xl font-semibold" style={{ color: '#FFFFFF' }}>
              Rename Thread
            </h2>
          </div>
          <button
            onClick={onCancel}
            disabled={isRenaming}
            className="p-1 rounded-full transition-colors hover:bg-white/10 disabled:opacity-50"
            style={{ color: '#FFFFFF' }}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2" style={{ color: '#FFFFFF', opacity: 0.9 }}>
              Thread Title
            </label>
            <Input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter thread title"
              maxLength={255}
              disabled={isRenaming}
              className="w-full"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#FFFFFF',
              }}
              autoFocus
            />
            <p className="text-xs mt-1" style={{ color: '#FFFFFF', opacity: 0.5 }}>
              {newTitle.length}/255 characters
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 rounded-md" style={{ backgroundColor: 'rgba(255, 56, 60, 0.1)', border: '1px solid rgba(255, 56, 60, 0.3)' }}>
              <p className="text-sm" style={{ color: '#FF383C' }}>
                {error}
              </p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onCancel}
              disabled={isRenaming}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ color: '#FFFFFF' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isRenaming || !newTitle.trim() || newTitle.trim() === currentTitle}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                backgroundColor: (isRenaming || !newTitle.trim() || newTitle.trim() === currentTitle) 
                  ? 'rgba(97, 85, 245, 0.5)' 
                  : '#6155F5',
                color: '#FFFFFF',
              }}
            >
              {isRenaming ? 'Renaming...' : 'Rename'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default RenameThreadModal;
