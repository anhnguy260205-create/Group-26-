export function PresenceIndicator({ presence, enabled, onToggleEnabled }) {
  const { status, attachVideo } = presence

  return (
    <div className="presence-indicator">
      <div className="presence-row">
        <video ref={attachVideo} muted playsInline className="presence-video" />
        <div className="presence-info">
          <span className="presence-status">
            <span className={`dot dot-${enabled ? status : 'idle'}`} />
            <span className="presence-label">
              {!enabled && 'Paused'}
              {enabled && status === 'starting' && 'Starting camera…'}
              {enabled && status === 'present' && 'Face detected'}
              {enabled && status === 'absent' && 'No face in view'}
              {enabled && status === 'unavailable' && 'Camera unavailable'}
            </span>
          </span>
          <button type="button" className="link-button" onClick={onToggleEnabled}>
            {enabled ? 'Pause' : 'Resume'}
          </button>
        </div>
      </div>
    </div>
  )
}
