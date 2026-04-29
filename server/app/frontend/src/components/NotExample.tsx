import React, { useState } from "react";
import { Button } from "@mui/material";
import Notification from "./Notification";

const ParentComponent = () => {
  const [notification, setNotification] = useState({
    open: false,
    message: "",
    severity: "info", // 'success', 'error', 'warning', 'info'
  });

  const handleOpenNotification = (message: string, severity: string) => {
    setNotification({ open: true, message, severity });
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  return (
    <div>
      {/* Trigger Notifications */}
      <Button
        variant="contained"
        color="primary"
        onClick={() =>
          handleOpenNotification("This is a success message!", "success")
        }
      >
        Show Success
      </Button>
      <Button
        variant="contained"
        color="error"
        onClick={() =>
          handleOpenNotification("This is an error message!", "error")
        }
      >
        Show Error
      </Button>
      <Button
        variant="contained"
        color="warning"
        onClick={() =>
          handleOpenNotification("This is a warning message!", "warning")
        }
      >
        Show Warning
      </Button>
      <Button
        variant="contained"
        color="info"
        onClick={() =>
          handleOpenNotification("This is an info message!", "info")
        }
      >
        Show Info
      </Button>

      {/* Notification Component */}
      <Notification
        open={notification.open}
        message={notification.message}
        severity={notification.severity}
        handleClose={handleCloseNotification}
      />
    </div>
  );
};

export default ParentComponent;
