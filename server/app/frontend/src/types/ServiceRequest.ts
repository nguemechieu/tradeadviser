// types/ServiceRequest.ts

import { Technician } from "./Technician";
import {Customer} from "./Customer";

export enum ServiceType {
    FURNITURE_ASSEMBLY = "FURNITURE_ASSEMBLY",
    TV_MOUNTING = "TV_MOUNTING",
    LIGHT_FIXTURE = "LIGHT_FIXTURE",
    OTHER = "OTHER",
}

export enum RequestStatus {
    PENDING = "PENDING",
    ASSIGNED = "ASSIGNED",
    COMPLETED = "COMPLETED",
    CANCELLED = "CANCELLED",
}


export interface ServiceRequest {
    id: number;
    customer: Customer;
    technician?: Technician;
    serviceType: ServiceType;
    description: string;
    status: RequestStatus;
    scheduledAt: string;
    createdAt: string;
    updatedAt: string;
}
