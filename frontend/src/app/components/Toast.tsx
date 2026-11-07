import { Alert, AlertColor, Snackbar } from "@mui/material";

interface ToastProps {
  message: string | null;
  onClose: () => void;
  severity?: AlertColor;
}

export default function Toast({
  message,
  onClose,
  severity = "error",
}: ToastProps) {
  return (
    <Snackbar
      open={!!message}
      autoHideDuration={5000}
      onClose={onClose}
      anchorOrigin={{ vertical: "top", horizontal: "right" }}
    >
      <Alert severity={severity} onClose={onClose} sx={{ width: "100%" }}>
        {message}
      </Alert>
    </Snackbar>
  );
}