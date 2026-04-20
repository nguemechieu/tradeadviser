# Super Admin & Role Management System

## Super Admin Account

A super admin user is automatically created when the backend starts for the first time.

### Default Super Admin Credentials
- **Email:** `admin@tradeadviser.local`
- **Username:** `superadmin`
- **Password:** `SuperAdmin@2026`
- **Role:** `admin`
- **Starting Balance:** 250,000

> ⚠️ **IMPORTANT:** Change the default password after your first login!

## Role System

The system has three role levels:

### 1. **Trader** (Default)
- Standard trading account
- Access to personal trading dashboard
- Can place and manage trades
- Can view personal portfolio
- Starting balance: 100,000
- **Auto-assigned to all public registrations**

### 2. **Editor**
- All trader permissions +
- Can edit trading strategies
- Can create and modify signals
- Can access community features
- Access to trading editor
- Starting balance: 100,000
- **Only admins can assign this role**

### 3. **Admin**
- All trader and editor permissions +
- **User Management:** Create users, assign roles, update roles
- System status and health monitoring
- Access to admin panel
- Multi-exchange trading access
- Agent network control
- Server control capabilities
- Starting balance: 250,000
- **Only admins can assign this role**

## User Management

### Creating Users (Admin Only)

**Via Admin Panel:**
1. Login as admin
2. Go to `/admin/users`
3. Click "+ Create New User"
4. Fill in user details
5. Select role (trader, editor, or admin)
6. Click "Create User"

**Via API:**
```bash
POST /api/auth/admin/create-user
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "username",
  "password": "SecurePassword123",
  "first_name": "John",
  "last_name": "Doe",
  "middle_name": "Optional",
  "phone_number": "+1-555-0000",
  "role": "trader|editor|admin"
}
```

### Updating User Roles (Admin Only)

**Via Admin Panel:**
1. Go to `/admin/users`
2. Find the user in the list
3. Use the dropdown in the "Actions" column
4. Select new role
5. Changes apply immediately

**Via API:**
```bash
PUT /api/auth/admin/users/{user_id}/role
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "role": "trader|editor|admin"
}
```

### Listing All Users (Admin Only)

**Via API:**
```bash
GET /api/auth/admin/users
Authorization: Bearer <admin_token>
```

## Access Routes by Role

### Public Routes (Everyone)
- `/` - Landing page
- `/login` - Login
- `/register` - Registration
- `/tradeadviser` - Trading prices
- `/docs` - Documentation

### Trader Routes (Trader+)
- `/home` - Dashboard home
- `/dashboard` - Trading dashboard
- `/account` - Account settings
- `/trading` - Trading interface

### Editor Routes (Editor+)
- `/trading-editor` - Strategy editor
- `/community` - Community forum

### Admin Routes (Admin Only)
- `/admin-panel` - Admin control center
- `/admin/users` - User management
- `/system-status` - System health monitoring

## Security Notes

1. **Default Password:** Must be changed immediately after first login
2. **Admin Privileges:** Only admins can create/manage other admins
3. **Role Assignment:** Done by admins only through the API or UI
4. **User Isolation:** Traders can only see their own data
5. **Token Security:** All admin operations require valid bearer token

## Troubleshooting

### Super Admin Not Found
If the super admin account doesn't exist:
1. Restart the backend service
2. Check backend logs for initialization messages
3. Verify database connectivity

### Can't Login as Admin
1. Verify username/email and password are correct
2. Check if account exists: Admin users should be visible in admin panel
3. Verify role is set to 'admin' in user list

### Permission Denied Errors
- Ensure you're logged in as an admin user
- Admin operations require admin role
- Check authorization token is valid

## First-Time Setup

1. **Start Backend:** Backend auto-creates super admin on first startup
2. **Login:** Use `superadmin` / `SuperAdmin@2026`
3. **Change Password:** Update password immediately
4. **Create Users:** Use admin panel to create other admin or editor accounts
5. **Assign Roles:** Manage user roles as needed

## API Endpoints Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/register` | POST | None | Public registration (creates trader) |
| `/api/auth/login` | POST | None | User login |
| `/api/auth/admin/create-user` | POST | Admin | Create user with custom role |
| `/api/auth/admin/users/{id}/role` | PUT | Admin | Update user role |
| `/api/auth/admin/users` | GET | Admin | List all users |
| `/api/auth/me` | GET | Bearer | Get current user info |

## Admin Panel Features

The admin panel (`/admin-panel`) provides:
- Quick access to user management
- System status monitoring
- User and license dashboard
- Admin shortcuts

The user management page (`/admin/users`) provides:
- View all users in the system
- Create new users with custom roles
- Update existing user roles
- Real-time role changes

---

**Last Updated:** 2026-04-20
**System Version:** 1.0.0
