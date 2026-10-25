export function Section({ id, title, intro, children }) {
  return (
    <section id={id} className="block" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{title}</h2>
      {intro && <p className="intro">{intro}</p>}
      {children}
    </section>
  );
}

export function Readouts({ items }) {
  return (
    <dl className="readouts">
      {items.map((it) => (
        <div className="readout" key={it.label}>
          <dt>{it.label}</dt>
          <dd className="value">{it.value}</dd>
          {it.hint && <dd className="hint">{it.hint}</dd>}
        </div>
      ))}
    </dl>
  );
}

/** Render request errors and loading state. */
export function Status({ state, children, height = 320 }) {
  if (state.error)
    return <p className="status error" role="alert">{state.error.message}</p>;
  if (state.loading && !state.data)
    return <div className="status" style={{ minHeight: height }}>Loading…</div>;
  return children;
}
