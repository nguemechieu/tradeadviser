import { axiosPrivate } from "./axios";

export interface UserSettings {
  username: string;
  email: string;
  firstname?: string;
  lastname?: string;
  display_name?: string;
}

export interface SecuritySettings {
  twoFactor: boolean;
  password?: string;
}

export interface NotificationPreferences {
  emailNotifications: boolean;
  smsNotifications: boolean;
  pushNotifications: boolean;
}

export interface PreferencesSettings {
  theme: "light" | "dark" | "custom" | "system";
}

export interface WorkspaceSettings {
  notifications: NotificationPreferences;
  preferences: PreferencesSettings;
  subscriptions?: Array<{ id: string | number; name: string }>;
}

// Fetch user profile
export const fetchUserProfile = async (): Promise<UserSettings> => {
  try {
    const response = await axiosPrivate.get("/api/v3/auth/me");
    return {
      username: response.data.username,
      email: response.data.email,
      firstname: response.data.firstname,
      lastname: response.data.lastname,
      display_name: response.data.display_name,
    };
  } catch (error) {
    console.error("Failed to fetch user profile:", error);
    throw error;
  }
};

// Update user profile
export const updateUserProfile = async (
  settings: UserSettings
): Promise<UserSettings> => {
  try {
    const response = await axiosPrivate.put("/api/v3/auth/profile", {
      email: settings.email,
      display_name: settings.display_name,
      firstname: settings.firstname,
      lastname: settings.lastname,
    });
    return response.data;
  } catch (error) {
    console.error("Failed to update user profile:", error);
    throw error;
  }
};

// Update password
export const updatePassword = async (newPassword: string): Promise<void> => {
  try {
    await axiosPrivate.post("/api/v3/auth/change-password", {
      new_password: newPassword,
    });
  } catch (error) {
    console.error("Failed to update password:", error);
    throw error;
  }
};

// Fetch workspace settings (themes, notifications, preferences)
export const fetchWorkspaceSettings = async (): Promise<WorkspaceSettings> => {
  try {
    const response = await axiosPrivate.get("/api/v3/workspace/settings");
    return response.data;
  } catch (error) {
    console.error("Failed to fetch workspace settings:", error);
    throw error;
  }
};

// Update workspace settings
export const updateWorkspaceSettings = async (
  settings: Partial<WorkspaceSettings>
): Promise<WorkspaceSettings> => {
  try {
    const response = await axiosPrivate.put(
      "/api/v3/workspace/settings",
      settings
    );
    return response.data;
  } catch (error) {
    console.error("Failed to update workspace settings:", error);
    throw error;
  }
};

// Setup two-factor authentication
export const setupTwoFactor = async (): Promise<{
  secret: string;
  qr_code: string;
}> => {
  try {
    const response = await axiosPrivate.post("/api/v3/auth/2fa/setup");
    return response.data;
  } catch (error) {
    console.error("Failed to setup two-factor authentication:", error);
    throw error;
  }
};

// Verify two-factor authentication
export const verifyTwoFactor = async (code: string): Promise<void> => {
  try {
    await axiosPrivate.post("/api/v3/auth/2fa/verify", { code });
  } catch (error) {
    console.error("Failed to verify two-factor authentication:", error);
    throw error;
  }
};

// Disable two-factor authentication
export const disableTwoFactor = async (): Promise<void> => {
  try {
    await axiosPrivate.post("/api/v3/auth/2fa/disable");
  } catch (error) {
    console.error("Failed to disable two-factor authentication:", error);
    throw error;
  }
};
