export function Reflection({ reflection, onReturn }) {
  return (
    <div className="reflection-overlay">
      <h2>Before you go back</h2>
      <p className="reflection-message">
        {reflection ? reflection.message : 'Taking a breath and closing the loop…'}
      </p>
      <button type="button" onClick={onReturn} disabled={!reflection}>
        Return to care
      </button>
    </div>
  )
}
