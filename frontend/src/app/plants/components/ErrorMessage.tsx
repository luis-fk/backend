interface ErrorMessageProps {
  message: string | null;
  style?: React.CSSProperties; // Allow dynamic style
}

export default function ErrorMessage({ message, style }: ErrorMessageProps) {
  return (
    <>
      {message && (
        <div
          style={{
            color: "#f44336",
            ...style,
          }}
        >
          {message}
        </div>
      )}
    </>
  );
}
