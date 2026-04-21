import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter as Router } from "react-router-dom";

import App from "./App.jsx";
import { AuthProvider } from "./context/AuthProvider.tsx";
import PersistLogin from "./components/PersistLogin.jsx";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Router>
      <AuthProvider>
        <PersistLogin>
          <App />
        </PersistLogin>
      </AuthProvider>
    </Router>
  </React.StrictMode>
);

