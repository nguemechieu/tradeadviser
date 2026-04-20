import axios from "../api/axios";
import useAuth from "./useAuth";

const useLogout = () => {
    const { setAuth } = useAuth();

    const logout = async () => {
        setAuth({});
        try {
            const response = await axios('/logout', {
                withCredentials: true
            });
            
            if (response.status === 200) {
                setAuth({});
                localStorage.clear();
                window.location.reload();
            }
            else {
                console.error(response);
               return false;
            }
        } catch (err) {
            console.error(err);
        }
    }

    return logout;
}

export default useLogout