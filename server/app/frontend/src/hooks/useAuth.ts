import { useContext, useDebugValue } from "react";
import AuthContext from "../context/AuthProvider";

interface AuthContextType {
  auth: Record<string, any>;
  setAuth: (auth: Record<string, any>) => void;
}

const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    const { auth } = context;
    useDebugValue(auth, (auth: any) => auth?.user ? "Logged In" : "Logged Out");
    return context;
};

export default useAuth;
