
import { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import * as Sentry from "@sentry/react";

import { AuthProvider } from "./context/AuthProvider";
import LoadingSpinner from "./components/LoadingSpinner";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

// Lazy-load main app for performance
const LazyApp = lazy(() => import("./App"));

// Initialize Sentry
Sentry.init({
  dsn: "https://05f3db24103d140909fabe35afaab578@o4508501778169856.ingest.us.sentry.io/4508501779611648",
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
  tracesSampleRate: 1.0,
  tracePropagationTargets: ["localhost", /^http:\/\/localhost:3000\/login/],
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
});

// Optional breadcrumb for tracking
Sentry.addBreadcrumb({
  message: "User clicked on submit button",
  category: "ui",
  level: "info",
});

// Mount React app
const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(
      <Sentry.ErrorBoundary fallback={<p style={{ padding: 40 }}>Something went wrong. Please refresh the page.</p>}>

      <BrowserRouter>
          <ErrorBoundary >
            <AuthProvider>
              <Suspense fallback={<LoadingSpinner />}>
                <Routes>
                  <Route path="/*" element={<LazyApp />} />
                </Routes>
              </Suspense>
            </AuthProvider>
          </ErrorBoundary>
        </BrowserRouter>
      </Sentry.ErrorBoundary>
  );
} else {
  // In case a root element isn't found
  document.body.innerHTML = "<h2 style='color: #dda939;'>Failed to load application: Root element not found.</h2>";
}
