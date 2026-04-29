import React, { Component, ErrorInfo } from "react";
import { Button } from "@mui/material";

interface ErrorBoundaryState {
  hasError: boolean;
  error: string;
}

export default class ErrorBoundary extends Component<
  {
    children: React.ReactNode;
  },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "---" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Error caught in ErrorBoundary:", error, errorInfo);
  }

  // Define the resetError method to reset the error state
  resetError = () => {
    this.setState({ hasError: false, error: "" });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="info">
          <p>Oops! Something went wrong.</p>
          <pre>{this.state.error}</pre>
          <Button onClick={this.resetError}>Try again</Button>
        </div>
      );
    }
    return this.props.children;
  }
}
