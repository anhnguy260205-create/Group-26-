export function StressMonitor({ monitor, enabled, onToggleEnabled }) {
  const { status, latest, manualValue, setManualValue, submitManual, videoRef, canvasRef } = monitor

  return (
    <div className="stress-monitor">
      {/* Camera feed never rendered to the page — sampled off-screen only. */}
      <video ref={videoRef} muted playsInline style={{ display: 'none' }} />
      <canvas ref={canvasRef} width={60} height={60} style={{ display: 'none' }} />

      <div className="stress-monitor-badge">
        <span className={`dot dot-${enabled ? status : 'idle'}`} />
        <span className="stress-monitor-label">
          {!enabled && 'Wellness sensing paused'}
          {enabled && status === 'starting' && 'Wellness sensing starting…'}
          {enabled && status === 'active' && (
            <>
              Wellness sensing active
              {latest?.heart_rate_bpm ? ` · ${Math.round(latest.heart_rate_bpm)} bpm` : ''}
            </>
          )}
          {enabled && status === 'manual-fallback' && 'Wellness sensing: manual check-in'}
          {enabled && status === 'idle' && 'Wellness sensing off'}
        </span>
        <button type="button" className="link-button" onClick={onToggleEnabled}>
          {enabled ? 'Pause' : 'Resume'}
        </button>
      </div>

      {enabled && status === 'manual-fallback' && (
        <div className="manual-checkin">
          <label htmlFor="manual-stress">
            Camera signal isn't available — how stressed do you feel right now?
          </label>
          <input
            id="manual-stress"
            type="range"
            min="1"
            max="10"
            value={manualValue}
            onChange={(e) => setManualValue(Number(e.target.value))}
          />
          <div className="manual-checkin-row">
            <span>{manualValue}/10</span>
            <button type="button" onClick={() => submitManual(manualValue)}>
              Check in
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
