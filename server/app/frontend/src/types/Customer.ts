
import { User } from "./User";

export interface Customer extends User {
    address: string;
    city: string;
    zipcode: string;
}
