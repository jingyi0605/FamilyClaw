type StatusMessageProps = {
  tone: "info" | "success" | "error";
  message: string;
};

export function StatusMessage({ tone, message }: StatusMessageProps) {
  return <div className={`status-message ${tone}`}>{message}</div>;
}

