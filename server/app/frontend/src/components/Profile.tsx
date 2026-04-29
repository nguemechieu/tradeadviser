import { useState, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Avatar,
  Button,
  TextField,
  Divider,
  Grid,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import { axiosPrivate } from "../api/axios";


const Profile = () => {
  const [isEditing, setIsEditing] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const handleEditToggle = () => setIsEditing((prev) => !prev);

  const handleInputChange = (e: { target: { name: any; value: any; }; }) => {
    const { name, value } = e.target;
    setUser((prevUser: any) => ({ ...prevUser, [name]: value }));
  };

  const handleSave = async () => {
    try {
      await axiosPrivate.put("/api/profile", user); // or `/profile`
      setIsEditing(false);
      alert("Profile updated successfully!");
    } catch (err) {
      console.error("Failed to update profile:", err);
      alert("Failed to update profile.");
    }
  };
const  [errors, setErrors] = useState('');
  const fetchUserProfile = async () => {
    try {
      const response = await axiosPrivate.get("/api/profile");
     if (response.status === 200)

      setUser(JSON.stringify(response.data));
    } catch (err) {
      console.error("Failed to load profile:", err);
      setLoading(false);
      setErrors(JSON.stringify(err.response.data));

    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserProfile().then(r => {});
  }, []);

  if (loading) {
    return <Typography>Loading profile...</Typography>;
  }

  if (!user) {
    return <Typography>Unable to load profile.
      {errors}</Typography>;


  }

  return (
      <Box sx={{ padding: 4 }}>
        <Typography variant="h4" gutterBottom>
          User Profile
        </Typography>
        <Paper sx={{ padding: 4 }} elevation={3}>
          <Box sx={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
            <Avatar
                src={user.profilePicture || "/default-avatar.png"}
                alt={user.name}
                sx={{ width: 100, height: 100, marginRight: 2 }}
            />
            <Box>
              <Typography variant="h5">{user.name}</Typography>

              <Typography variant="body1" color="text.secondary">
                          {user.email}

              </Typography>

            </Box>
          </Box>

          <Divider sx={{ marginBottom: 3 }} />

          <Grid container spacing={3}>
            <Grid>
              <TextField
                  label="Full Name"
                  fullWidth
                  value={user.name}
                  name="name"
                  onChange={handleInputChange}
                  disabled={!isEditing}
              />
            </Grid>
            <Grid >
              <TextField
                  label="Email"
                  fullWidth
                  value={user.email}
                  name="email"
                  onChange={handleInputChange}
                  disabled
              />
            </Grid>
            <Grid >
              <TextField
                  label="Phone"
                  fullWidth
                  value={user.phone || ""}
                  name="phone"
                  onChange={handleInputChange}
                  disabled={!isEditing}
              />
            </Grid>
            <Grid >
              <TextField
                  label="Address"
                  fullWidth
                  value={user.address || ""}
                  name="address"
                  onChange={handleInputChange}
                  disabled={!isEditing}
              />
            </Grid>
            <Grid >
              <TextField
                  label="Bio"
                  fullWidth
                  multiline
                  rows={4}
                  value={user.bio || ""}
                  name="bio"
                  onChange={handleInputChange}
                  disabled={!isEditing}
              />
            </Grid>
          </Grid>

          <Box sx={{ marginTop: 3, textAlign: "right" }}>
            {isEditing ? (
                <Button
                    variant="contained"
                    color="primary"
                    startIcon={<SaveIcon />}
                    onClick={handleSave}
                >
                  Save
                </Button>
            ) : (
                <Button
                    variant="outlined"
                    color="secondary"
                    startIcon={<EditIcon />}
                    onClick={handleEditToggle}
                >
                  Edit Profile
                </Button>
            )}
          </Box>
        </Paper>
      </Box>
  );
};

export default Profile;
