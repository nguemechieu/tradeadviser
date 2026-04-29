import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Button,
  TextField,
  Typography,
  Box,
  Alert,
  MenuItem,
} from "@mui/material";
import { axiosPublic } from "../api/axios";
import './Register.css'
// Regex validation patterns
const REGEX = {
  USER: /^[A-z][A-z0-9-_]{3,23}$/,
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PWD: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%]).{8,24}$/,
  ZIP: /^[0-9]{5}(?:-[0-9]{4})?$/,
  PHONE: /^\d{10,15}$/,
};

const genderOptions = ["Male", "Female", "Others"];
const securityQuestions = [
  "What was the name of your first pet?",
  "What is your mother's maiden name?",
  "What is your favorite book?",
  "What was the make and model of your first car?",
  "What is the name of the street you grew up on?",
  "In what city were you born?",
];

const initialFormData = {
  username: "",
  email: "",
  password: "",
  matchPwd: "",
  firstName: "",
  middleName: "",
  lastName: "",
  birthdate: "",
  phoneNumber: "",
  zipCode: "",
  address: "",
  city: "",
  state: "",
  country: "",
  gender: genderOptions[0],
  profilePictureUrl: "",
  bio: "",
  securityQuestion: securityQuestions[0],
  securityAnswer: "",
};

const Register = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState(initialFormData);
  const [errMsg, setErrMsg] = useState("");
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setErrMsg(""); // Clear error when form changes
  }, [formData]);

  const validateForm = () => {
    return (
        REGEX.USER.test(formData.username) &&
        REGEX.EMAIL.test(formData.email) &&
        REGEX.PWD.test(formData.password) &&
        formData.password === formData.matchPwd &&
        REGEX.PHONE.test(formData.phoneNumber) &&
        REGEX.ZIP.test(formData.zipCode)
    );
  };

  const handleInputChange = ({ target: { name, value } }) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      setErrMsg("Please fix validation errors.");
      return;
    }

    setIsLoading(true);
    try {
      const response = await axiosPublic.post("/api/v3/auth/signup", formData);
      if ([200, 201].includes(response.status)) {
        setSuccess(true);
        navigate("/", { replace: true });
      } else {
        setErrMsg(response?.data?.message || "Registration failed.");
      }
    } catch (error) {
      setErrMsg(error?.response?.data?.message || "Server error.");
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
        <Box className="register-success" textAlign="center" mt={4}>
          <Typography variant="h4" gutterBottom>
            🎉 Registration Successful!
          </Typography>
          <Link to="/" style={{ textDecoration: "none" }}>
            <Button variant="contained" color="primary">
              Sign In
            </Button>
          </Link>
        </Box>
    );
  }

  return (<div className={'register'}>

      <Box className="register-section" mt={4} px={2}>
        <Button onClick={() => navigate("/")}>← Back to Home</Button>

        <div className={'card'}>
        <Box className="register-card" mt={2}>
          <Typography variant="h4" align="center" gutterBottom>
            Create Your Account
          </Typography>

          {errMsg && <Alert severity="error">{errMsg}</Alert>}

          <form onSubmit={handleSubmit} className="register-form">
            <TextField label="Username" name="username" fullWidth required margin="normal" value={formData.username} onChange={handleInputChange} />
            <TextField label="Email" name="email" fullWidth required margin="normal" value={formData.email} onChange={handleInputChange} />
            <TextField label="Password" name="password" type="password" fullWidth required margin="normal" value={formData.password} onChange={handleInputChange} />
            <TextField label="Confirm Password" name="matchPwd" type="password" fullWidth required margin="normal" value={formData.matchPwd} onChange={handleInputChange} />

            <Box display="flex" gap={2} flexWrap="wrap">
              <TextField label="First Name" name="firstname" fullWidth required value={formData.firstName} onChange={handleInputChange} />
              <TextField label="Middle Name" name="middlename" fullWidth value={formData.middleName} onChange={handleInputChange} />
              <TextField label="Last Name" name="lastName" fullWidth required value={formData.lastName} onChange={handleInputChange} />
            </Box>

            <TextField label="Phone Number" name="phonenumber" fullWidth required margin="normal" value={formData.phoneNumber} onChange={handleInputChange} />
             <TextField label="Birthdate" name="birthdate" type="date" fullWidth required margin="normal"  value={formData.birthdate} onChange={handleInputChange} />

              <div className="gender">

            <TextField select label="Gender" name="gender" fullWidth margin="normal" value={formData.gender} onChange={handleInputChange}>
              {genderOptions.map((option) => (
                  <MenuItem key={option} value={option}>
                    {option}
                  </MenuItem>
              ))}
            </TextField>
              </div>
            <TextField select label="Security Question" name="securityQuestion" fullWidth margin="normal" value={formData.securityQuestion} onChange={handleInputChange}>
              {securityQuestions.map((q) => (
                  <MenuItem key={q} value={q}>
                    {q}
                  </MenuItem>
              ))}
            </TextField>

            <TextField label="Security Answer" name="securityAnswer" fullWidth required margin="normal" value={formData.securityAnswer} onChange={handleInputChange} />

            <Button type="submit" variant="contained" color="primary" disabled={isLoading} fullWidth sx={{ mt: 3 }}>
              {isLoading ? "Submitting..." : "Register"}
            </Button>
          </form>
        </Box>
        </div>
      </Box>
      </div>
  );
};

export default Register;
