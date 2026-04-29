// types/Technician.ts
import { User } from "./User";

export interface Technician extends User {
    skills: string;
    availability: string;
    rating: number;
    serviceArea: string;
}
