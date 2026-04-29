import  {useEffect, useState} from "react";
import { axiosPrivate } from "../api/axios";

interface SearchBarProps {
    onResults: (results: any[]) => void;
}

const SearchBar: React.FC<SearchBarProps> = ({ onResults }) => {
    const [query, setQuery] = useState("");

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        setQuery(value);

        // Optionally debounce here for performance
        if (value.trim()) {
            fetchResults(value).then(r => {});
        } else {
            onResults([]); // clear if empty
        }
    };

    const fetchResults = async (keyword: string) => {
        try {
            const res = await axiosPrivate.get(`/api/users?search=${keyword}`);
            onResults(res.data);
        } catch (error) {
            console.error("Search error:", error);
        }
    };
    useEffect(() => {
        fetchResults(query).then(r => {console.log(r)});
    });
    return (
        <div style={{ marginBottom: "20px" }}>
            <input
                type="text"
                value={query}
                placeholder="Search users..."
                onChange={handleSearchChange}
                style={{
                    padding: "10px",
                    width: "100%",
                    border: "1px solid #ddd",
                    borderRadius: "5px",
                    fontSize: "16px",
                    outline: "none",
                }}
            />
        </div>
    );
};

export default SearchBar;
