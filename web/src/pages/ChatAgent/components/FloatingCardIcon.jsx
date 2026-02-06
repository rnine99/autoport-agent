import React from 'react';
import { Bookmark } from 'lucide-react';

/**
 * FloatingCardIcon Component
 * 
 * Displays a minimized floating card as an icon with title in the top bar.
 * Clicking the icon will restore the card.
 * Shows a green visual indicator when there's an unread update.
 * 
 * @param {Object} props
 * @param {string} props.id - Unique identifier for the card
 * @param {string} props.title - Title/name of the card to display
 * @param {Function} props.onClick - Callback when icon is clicked to restore card
 * @param {boolean} props.hasUnreadUpdate - Whether the card has an unread update (shows green indicator)
 */
function FloatingCardIcon({ id, title, onClick, hasUnreadUpdate = false }) {
  // Use green color if there's an unread update, otherwise use purple
  const iconColor = hasUnreadUpdate ? '#0FEDBE' : '#6155F5';
  
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-md transition-colors hover:bg-white/10"
      style={{ color: iconColor }}
      title={`Restore: ${title || 'Card'}${hasUnreadUpdate ? ' (has updates)' : ''}`}
    >
      <Bookmark className="h-4 w-4 flex-shrink-0" style={{ color: iconColor }} />
      <span className="text-sm font-medium whitespace-nowrap" style={{ color: '#FFFFFF' }}>
        {title || 'Card'}
      </span>
      {/* Unread update indicator dot */}
      {hasUnreadUpdate && (
        <div
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: '#0FEDBE' }}
        />
      )}
    </button>
  );
}

export default FloatingCardIcon;
