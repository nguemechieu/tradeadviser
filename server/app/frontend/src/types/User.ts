// types/User.ts
export enum Role {
    CUSTOMER = "CUSTOMER",
    TECHNICIAN = "TECHNICIAN",
    ADMIN = "ADMIN",
}

export interface User {
    id: number;
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    password?: string; // Optional on frontend for security
    role: Role;
    createdAt: string;
    updatedAt: string;
}
