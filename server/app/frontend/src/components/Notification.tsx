import React from "react";
import { Snackbar, Alert } from "@mui/material";

const Notification = (x) => {
  const message = x.message;
  const severity = x.severity;
  const open = x.open;
  const handleClose = x.handleClose;
  const handleSnackbarClose = (
    event: React.SyntheticEvent<Element, Event>,
    reason: string,
  ) => {
    event.preventDefault();
    if (reason === "clickaway") {
      return;
    }
    handleClose();
  };
  if (!open) {
    return null;
  }

  return (
    <Snackbar
      open={open}
      autoHideDuration={5000} // Notification will close automatically after 5 seconds
      anchorOrigin={{ vertical: "top", horizontal: "center" }}
    >
      <Alert
        onClose={(event) => {
          handleSnackbarClose(event, "clickaway");
        }}
        severity={severity}
        sx={{ width: "100%" }}
      >
        {message}
      </Alert>
    </Snackbar>
  );
};

export default Notification;
