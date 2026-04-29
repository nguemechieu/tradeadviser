import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  TextField,
  Button,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Select,
  MenuItem,
  Paper,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  Grid,
  Alert,
  CircularProgress,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import SaveIcon from "@mui/icons-material/Save";
import * as settingsApi from "../api/settingsApi";

const Settings = () => {
  // User Profile State
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [firstname, setFirstname] = useState("");
  const [lastname, setLastname] = useState("");
  const [displayName, setDisplayName] = useState("");

  // Security State
  const [password, setPassword] = useState("");
  const [twoFactor, setTwoFactor] = useState(false);

  // Notification State
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [smsNotifications, setSmsNotifications] = useState(false);
  const [pushNotifications, setPushNotifications] = useState(true);

  // Preferences State
  const [theme, setTheme] = useState("light");

  // Subscriptions State
  const [subscriptions, setSubscriptions] = useState<
    Array<{ id: string | number; name: string }>
  >([]);
  const [newSubscription, setNewSubscription] = useState("");

  // UI State
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // Load data on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setErrorMessage("");

      // Load user profile
      const userProfile = await settingsApi.fetchUserProfile();
      setUsername(userProfile.username);
      setEmail(userProfile.email);
      setFirstname(userProfile.firstname || "");
      setLastname(userProfile.lastname || "");
      setDisplayName(userProfile.display_name || "");

      // Load workspace settings
      const workspaceSettings = await settingsApi.fetchWorkspaceSettings();
      if (workspaceSettings.notifications) {
        setEmailNotifications(
          workspaceSettings.notifications.emailNotifications ?? true
        );
        setSmsNotifications(
          workspaceSettings.notifications.smsNotifications ?? false
        );
        setPushNotifications(
          workspaceSettings.notifications.pushNotifications ?? true
        );
      }
      if (workspaceSettings.preferences) {
        setTheme(workspaceSettings.preferences.theme || "light");
      }
      if (workspaceSettings.subscriptions) {
        setSubscriptions(workspaceSettings.subscriptions);
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
      setErrorMessage("Failed to load settings. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const clearMessages = () => {
    setSuccessMessage("");
    setErrorMessage("");
  };

  // Handlers
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      clearMessages();
      await settingsApi.updateUserProfile({
        username,
        email,
        firstname,
        lastname,
        display_name: displayName,
      });
      setSuccessMessage("Profile updated successfully!");
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error: any) {
      console.error("Failed to save profile:", error);
      setErrorMessage(
        error.response?.data?.detail ||
          "Failed to update profile. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSecurity = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      clearMessages();

      if (password) {
        await settingsApi.updatePassword(password);
        setPassword("");
        setSuccessMessage(
          "Password updated successfully! Please log in again."
        );
      }

      // TODO: Handle two-factor setup/disable when backend endpoints are ready
      if (twoFactor) {
        // await settingsApi.setupTwoFactor();
        setSuccessMessage("Security settings updated successfully!");
      } else {
        // await settingsApi.disableTwoFactor();
        setSuccessMessage("Two-factor authentication disabled!");
      }

      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error: any) {
      console.error("Failed to save security settings:", error);
      setErrorMessage(
        error.response?.data?.detail ||
          "Failed to update security settings. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    try {
      setSaving(true);
      clearMessages();
      await settingsApi.updateWorkspaceSettings({
        preferences: { theme: theme as "light" | "dark" | "custom" | "system" },
      });
      setSuccessMessage("Preferences updated successfully!");
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error: any) {
      console.error("Failed to save preferences:", error);
      setErrorMessage(
        error.response?.data?.detail ||
          "Failed to update preferences. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      clearMessages();
      await settingsApi.updateWorkspaceSettings({
        notifications: {
          emailNotifications,
          smsNotifications,
          pushNotifications,
        },
      });
      setSuccessMessage("Notification preferences updated successfully!");
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error: any) {
      console.error("Failed to save notifications:", error);
      setErrorMessage(
        error.response?.data?.detail ||
          "Failed to update notification preferences. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAddSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newSubscription.trim()) {
      const updatedSubscriptions = [
        ...subscriptions,
        { id: Date.now(), name: newSubscription },
      ];
      setSubscriptions(updatedSubscriptions);
      try {
        setSaving(true);
        clearMessages();
        await settingsApi.updateWorkspaceSettings({
          subscriptions: updatedSubscriptions,
        });
        setNewSubscription("");
        setSuccessMessage("Subscription added successfully!");
        setTimeout(() => setSuccessMessage(""), 3000);
      } catch (error: any) {
        // Revert on error
        setSubscriptions(subscriptions);
        setErrorMessage(
          error.response?.data?.detail ||
            "Failed to add subscription. Please try again."
        );
      } finally {
        setSaving(false);
      }
    }
  };

  const handleRemoveSubscription = async (id: string | number) => {
    const updatedSubscriptions = subscriptions.filter((sub) => sub.id !== id);
    setSubscriptions(updatedSubscriptions);
    try {
      setSaving(true);
      clearMessages();
      await settingsApi.updateWorkspaceSettings({
        subscriptions: updatedSubscriptions,
      });
      setSuccessMessage("Subscription removed successfully!");
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (error: any) {
      // Revert on error
      setSubscriptions(subscriptions);
      setErrorMessage(
        error.response?.data?.detail ||
          "Failed to remove subscription. Please try again."
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "400px",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ padding: 4 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      {successMessage && (
        <Alert severity="success" sx={{ marginBottom: 2 }}>
          {successMessage}
        </Alert>
      )}

      {errorMessage && (
        <Alert severity="error" sx={{ marginBottom: 2 }}>
          {errorMessage}
        </Alert>
      )}

      {/* Profile Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Profile
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TextField
              label="Username"
              fullWidth
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={true}
              helperText="Username cannot be changed"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="First Name"
              fullWidth
              value={firstname}
              onChange={(e) => setFirstname(e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Last Name"
              fullWidth
              value={lastname}
              onChange={(e) => setLastname(e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Display Name"
              fullWidth
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Email"
              fullWidth
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Grid>
        </Grid>
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveProfile}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Profile"}
        </Button>
      </Paper>

      {/* Security Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Security
        </Typography>
        <TextField
          label="Change Password"
          fullWidth
          type="password"
          placeholder="Enter new password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          sx={{ marginBottom: 2 }}
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={twoFactor}
              onChange={(e) => setTwoFactor(e.target.checked)}
            />
          }
          label="Enable Two-Factor Authentication"
        />
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveSecurity}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Security Settings"}
        </Button>
      </Paper>

      {/* Notifications Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Notifications
        </Typography>
        <FormGroup>
          <FormControlLabel
            control={
              <Checkbox
                checked={emailNotifications}
                onChange={(e) => setEmailNotifications(e.target.checked)}
              />
            }
            label="Email Notifications"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={smsNotifications}
                onChange={(e) => setSmsNotifications(e.target.checked)}
              />
            }
            label="SMS Notifications"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={pushNotifications}
                onChange={(e) => setPushNotifications(e.target.checked)}
              />
            }
            label="Push Notifications"
          />
        </FormGroup>
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveNotifications}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Notification Preferences"}
        </Button>
      </Paper>

      {/* Preferences Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Preferences
        </Typography>
        <Select
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          fullWidth
          sx={{ marginBottom: 2 }}
          variant={"filled"}
        >
          <MenuItem value="light">Light</MenuItem>
          <MenuItem value="dark">Dark</MenuItem>
          <MenuItem value="custom">Custom</MenuItem>
          <MenuItem value="system">System</MenuItem>
        </Select>
        <Button
          variant="contained"
          color="primary"
          startIcon={<SaveIcon />}
          onClick={handleSavePreferences}
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Preferences"}
        </Button>
      </Paper>

      {/* Subscriptions Section */}
      <Paper sx={{ padding: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Subscriptions
        </Typography>
        <List>
          {subscriptions.map((subscription) => (
            <ListItem
              key={subscription.id}
              secondaryAction={
                <Tooltip title="Remove Subscription">
                  <IconButton
                    edge="end"
                    color="error"
                    onClick={() => handleRemoveSubscription(subscription.id)}
                    disabled={saving}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Tooltip>
              }
            >
              <ListItemText primary={subscription.name} />
            </ListItem>
          ))}
        </List>
        <Box sx={{ display: "flex", alignItems: "center", marginTop: 2 }}>
          <TextField
            label="Add New Subscription"
            value={newSubscription}
            onChange={(e) => setNewSubscription(e.target.value)}
            fullWidth
          />
          <Tooltip title="Add Subscription">
            <IconButton
              color="primary"
              onClick={handleAddSubscription}
              sx={{ marginLeft: 1 }}
              disabled={saving}
            >
              <AddCircleOutlineIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
    </Box>
  );
};

  return (
    <Box sx={{ padding: 4 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      {/* Profile Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Profile
        </Typography>
        <Grid container spacing={3}>
          <TextField
              label="Username"
              fullWidth
              value={username}
              onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
              label="Email"
              fullWidth
              value={email}
              onChange={(e) => setEmail(e.target.value)}
          />
        </Grid>
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveProfile}
        >
          Save Profile
        </Button>
      </Paper>

      {/* Security Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Security
        </Typography>
        <TextField
          label="Change Password"
          fullWidth
          type="password"
          placeholder="Enter new password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          sx={{ marginBottom: 2 }}
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={twoFactor}
              onChange={(e) => setTwoFactor(e.target.checked)}
            />
          }
          label="Enable Two-Factor Authentication"
        />
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveSecurity}
        >
          Save Security Settings
        </Button>
      </Paper>

      {/* Notifications Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Notifications
        </Typography>
        <FormGroup>
          <FormControlLabel
            control={
              <Checkbox
                checked={emailNotifications}
                onChange={(e) => setEmailNotifications(e.target.checked)}
              />
            }
            label="Email Notifications"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={smsNotifications}
                onChange={(e) => setSmsNotifications(e.target.checked)}
              />
            }
            label="SMS Notifications"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={pushNotifications}
                onChange={(e) => setPushNotifications(e.target.checked)}
              />
            }
            label="Push Notifications"
          />
        </FormGroup>
        <Button
          variant="contained"
          color="primary"
          sx={{ marginTop: 2 }}
          startIcon={<SaveIcon />}
          onClick={handleSaveNotifications}
        >
          Save Notification Preferences
        </Button>
      </Paper>

      {/* Preferences Section */}
      <Paper sx={{ padding: 4, marginBottom: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Preferences
        </Typography>
        <Select
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          fullWidth
          sx={{ marginBottom: 2 }}
          variant={"filled"}
        >
          <MenuItem value="light">Light</MenuItem>
          <MenuItem value="dark">Dark</MenuItem>
          <MenuItem value="custom">Custom</MenuItem>
          <MenuItem value="system">System</MenuItem>
        </Select>
        <Button
          variant="contained"
          color="primary"
          startIcon={<SaveIcon />}
          onClick={handleSavePreferences}
        >
          Save Preferences
        </Button>
      </Paper>

      {/* Subscriptions Section */}
      <Paper sx={{ padding: 4 }} elevation={3}>
        <Typography variant="h5" gutterBottom>
          Subscriptions
        </Typography>
        <List>
          {subscriptions.map((subscription) => (
            <ListItem
              key={subscription.id}
              secondaryAction={
                <Tooltip title="Remove Subscription">
                  <IconButton
                    edge="end"
                    color="error"
                    onClick={() => handleRemoveSubscription(subscription.id)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Tooltip>
              }
            >
              <ListItemText primary={subscription.name} />
            </ListItem>
          ))}
        </List>
        <Box sx={{ display: "flex", alignItems: "center", marginTop: 2 }}>
          <TextField
            label="Add New Subscription"
            value={newSubscription}
            onChange={(e) => setNewSubscription(e.target.value)}
            fullWidth
          />
          <Tooltip title="Add Subscription">
            <IconButton
              color="primary"
              onClick={handleAddSubscription}
              sx={{ marginLeft: 1 }}
            >
              <AddCircleOutlineIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>
    </Box>
  );
};

export default Settings;
