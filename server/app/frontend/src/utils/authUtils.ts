import { axiosPrivate } from "../api/axios";


export const refreshAccessToken = async (): Promise<string | null> => {
    try {
        const res = await axiosPrivate.post(
            "/api/auth/refresh"
        );
        return res.data.accessToken;
    } catch (error) {
        console.warn("Unable to refresh token. Logging out.");
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
        return null;
    }
};
