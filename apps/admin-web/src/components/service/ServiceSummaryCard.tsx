type ServiceSummaryCardProps = {
  title: string;
  value: string;
  note: string;
};

export function ServiceSummaryCard({ title, value, note }: ServiceSummaryCardProps) {
  return (
    <article className="summary-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}
