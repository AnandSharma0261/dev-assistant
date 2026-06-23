# AI Crew Report

## Requirement
Ek To-Do list web app banao jisme user task add, delete, aur 'complete' mark kar sake. User login/signup bhi hona chahiye.

## 📋 Plan (Tasks)

- **[High] Backend Project Setup** — NPM/Yarn project initialize karein, basic folder structure banayein (controllers, models, routes).
- **[High] Database Setup (MongoDB/PostgreSQL)** — Database choose karein (e.g., MongoDB with Mongoose) aur uska connection configure karein.
- **[High] User Model Creation** — User schema banayein jisme username, password (hashed), email fields ho.
- **[High] User Registration API** — Backend API endpoint banayein jisse naya user signup kar sake, password hash karna na bhoolein.
- **[High] User Login API & JWT Token** — Backend API endpoint banayein jisse user login kar sake aur JWT token generate karke return karein.
- **[High] JWT Authentication Middleware** — Ek middleware banayein jo protected routes ko access karne se pehle JWT token validate kare.
- **[High] To-Do Task Model Creation** — Task schema banayein jisme title, description, completed status, aur user reference ho.
- **[High] Create Task API** — Ek authenticated API endpoint banayein jisse logged-in user naya task add kar sake.
- **[High] Get All Tasks API for User** — Ek authenticated API endpoint banayein jisse logged-in user apne saare tasks retrieve kar sake.
- **[High] Update Task API (Mark Complete)** — Ek authenticated API endpoint banayein jisse user kisi task ko 'completed' mark kar sake.
- **[High] Delete Task API** — Ek authenticated API endpoint banayein jisse user kisi task ko delete kar sake.
- **[High] Frontend Project Setup** — React/Vue/Angular ka project initialize karein aur basic routing set up karein.
- **[Medium] Login Page UI** — Login form ka UI banayein jisme username/email aur password fields ho.
- **[Medium] Signup Page UI** — Signup form ka UI banayein jisme username, email aur password fields ho.
- **[High] To-Do List Page UI** — Tasks display karne, naya task add karne aur task options (complete/delete) ke liye UI banayein.
- **[High] Frontend User Registration Logic** — Signup form submit karne par backend registration API call karein aur response handle karein.
- **[High] Frontend User Login Logic** — Login form submit karne par backend login API call karein aur JWT token ko local storage mein save karein.
- **[High] Frontend Task Creation Logic** — Add task form se input lekar backend create task API ko call karein.
- **[High] Frontend Display Tasks Logic** — Component load hone par backend se user ke tasks fetch karein aur UI mein display karein.
- **[High] Frontend Mark Task Complete Logic** — Task ke 'complete' button/checkbox click par backend update task API ko call karein.
- **[High] Frontend Delete Task Logic** — Task ke 'delete' button click par backend delete task API ko call karein.
- **[Medium] Frontend Logout Functionality** — Logout button banayein jo JWT token ko local storage se clear kare aur user ko login page par redirect kare.
- **[Medium] Basic Error Handling and UI Feedback** — API calls mein errors ko gracefully handle karein aur user ko appropriate feedback (e.g., toasts) dikhayein.
- **[Medium] Backend API Testing (Postman/Insomnia)** — Saare backend API endpoints ki functionality Postman ya Insomnia se test karein.
- **[Medium] End-to-End Testing (Manual)** — Poore application ke user flow ko manually test karein, login se lekar task management tak.

## 🏛️ Architecture

- **frontend**: React (with TypeScript)
- **backend**: Node.js (Express.js with TypeScript)
- **database**: PostgreSQL
- **other**: ['JWT (JSON Web Tokens) for Authentication', 'Prisma (ORM for Node.js)', 'Docker (Containerization)', 'Nginx (Reverse Proxy/Load Balancer, optional but good practice)']

## 👨‍💻 Generated Code

### Backend Project Setup

Okay, yahan Node.js (Express.js with TypeScript) backend project ka complete setup hai.

**Assumptions:**
*   Aapke system par Node.js aur npm (ya Yarn) pehle se install hain.
*   Aapke paas ek terminal/command prompt accessible hai.

---

### Backend Project Setup Steps

1.  **NPM/Yarn Project Initialize Karein:**

    Apne project folder mein jayein aur yeh command chalayein:
    ```bash
    # Agar npm use kar rahe hain:
    npm init -y

    # Ya agar Yarn use kar rahe hain:
    yarn init -y
    ```
    Isse `package.json` file ban jayegi.

2.  **Zaroori Dependencies Install Karein:**

    ```bash
    # Production dependencies:
    npm install express dotenv

    # Ya Yarn ke saath:
    yarn add express dotenv

    # Development dependencies (TypeScript aur related tools):
    npm install --save-dev typescript ts-node nodemon @types/node @types/express

    # Ya Yarn ke saath:
    yarn add --dev typescript ts-node nodemon @types/node @types/express
    ```

3.  **TypeScript Configuration File Banayein:**

    ```bash
    npx tsc --init
    ```
    Isse `tsconfig.json` file ban jayegi. Is file ko open karke neeche diye gaye changes karein (ya pura content replace kar dein).

4.  **Folder Structure Banayein:**

    `src` folder ke andar yeh structure banayein:
    ```
    .
    ├── src/
    │   ├── controllers/
    │   │   └── homeController.ts
    │   ├── models/
    │   │   └── index.ts  (placeholder)
    │   ├── routes/
    │   │   ├── index.ts
    │   │   └── homeRoutes.ts
    │   ├── app.ts
    │   └── server.ts
    ├── .env
    ├── .gitignore
    ├── package.json
    └── tsconfig.json
    ```

---

### File Content

Ab har file mein neeche diya gaya code daalein:

**1. `package.json`**
Ismein `scripts` section update karein:

```json
{
  "name": "my-backend",
  "version": "1.0.0",
  "description": "Node.js Express TypeScript Backend",
  "main": "dist/server.js",
  "scripts": {
    "build": "npx tsc",
    "start": "node dist/server.js",
    "dev": "nodemon --exec ts-node src/server.ts",
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "dependencies": {
    "dotenv": "^16.4.5",
    "express": "^4.19.2"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.12.12",
    "nodemon": "^3.1.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.4.5"
  }
}
```

**2. `tsconfig.json`**
`npx tsc --init` se bani file ko isse replace kar dein:

```json
{
  "compilerOptions": {
    "target": "es2016",
    "module": "commonjs",
    "rootDir": "./src",
    "outDir": "./dist",
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "**/*.spec.ts"]
}
```

**3. `.env`**
Environment variables ke liye:

```
PORT=3000
DATABASE_URL="postgresql://user:password@localhost:5432/mydatabase" # Example for PostgreSQL
```

**4. `.gitignore`**
Version control se ignore karne ke liye:

```
node_modules/
dist/
.env
npm-debug.log*
yarn-debug.log*
.DS_Store
```

**5. `src/app.ts`**
Express application instance ko configure karein:

```typescript
// src/app.ts
import express from 'express';
import apiRoutes from './routes'; // Import all routes

const app = express();

// Middleware to parse JSON requests
app.use(express.json());

// Main API routes
app.use('/api', apiRoutes);

// Basic route for testing server
app.get('/', (req, res) => {
  res.send('Backend is running!');
});

export default app;
```

**6. `src/server.ts`**
Application entry point, server ko start karta hai:

```typescript
// src/server.ts
import dotenv from 'dotenv';
dotenv.config(); // Load environment variables from .env file

import app from './app'; // Import the configured Express app

const PORT = process.env.PORT || 3000; // Use port from .env or default to 3000

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
  console.log('Press CTRL+C to stop');
});
```

**7. `src/controllers/homeController.ts`**
Example controller function:

```typescript
// src/controllers/homeController.ts
import { Request, Response } from 'express';

/**
 * Handles the request for the home endpoint.
 * Returns a welcome message.
 */
export const getHome = (req: Request, res: Response) => {
  res.status(200).json({
    message: 'Welcome to the backend API!',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
};
```

**8. `src/models/index.ts`**
Models folder ke liye placeholder (database models ya interfaces yahan aayengi):

```typescript
// src/models/index.ts
// This file can be used to export all models from this directory,
// or serve as a placeholder for database connection setup with ORMs (e.g., TypeORM, Sequelize).

/**
 * Example of a simple TypeScript interface for a User model.
 * In a real application, this might be a more complex class
 * tied to an ORM or a database schema.
 */
export interface User {
  id: string;
  username: string;
  email: string;
  createdAt: Date;
  updatedAt: Date;
}

// ... other model interfaces or database setup ...
```

**9. `src/routes/homeRoutes.ts`**
Specific routes define karein:

```typescript
// src/routes/homeRoutes.ts
import { Router } from 'express';
import * as homeController from '../controllers/homeController'; // Import all functions from homeController

const router = Router();

// Define a GET route for the home endpoint
router.get('/', homeController.getHome);

export default router;
```

**10. `src/routes/index.ts`**
Sabhi routes ko ek jagah consolidate karein:

```typescript
// src/routes/index.ts
import { Router } from 'express';
import homeRoutes from './homeRoutes'; // Import specific route files

const router = Router();

// Use home routes under a specific path, e.g., /api/home
router.use('/home', homeRoutes);

// You can add other routes here as your application grows
// router.use('/users', userRoutes);
// router.use('/products', productRoutes);

export default router;
```

---

### Project Run Kaise Karein

1.  **Build the project:**
    ```bash
    npm run build
    # Ya: yarn build
    ```
    Isse `src` folder ka code compile hokar `dist` folder mein JavaScript files ban jayengi.

2.  **Start the server (production mode):**
    ```bash
    npm start
    # Ya: yarn start
    ```
    Yeh `dist/server.js` file ko run karega.

3.  **Start the server (development mode with hot-reload):**
    ```bash
    npm run dev
    # Ya: yarn dev
    ```
    Yeh `ts-node` aur `nodemon` ka use karke `src/server.ts` ko directly run karega aur file changes par server ko automatically restart karega.

Ab aap apne browser mein `http://localhost:3000` ya `http://localhost:3000/api/home` par jaakar output dekh sakte hain.

### Database Setup (MongoDB/PostgreSQL)

यहाँ Node.js (Express.js with TypeScript) backend के लिए PostgreSQL डेटाबेस कनेक्शन सेटअप का कोड है।

**Assumptions:**
1.  आपने `dotenv` लाइब्रेरी इंस्टॉल की है और `.env` फ़ाइल में डेटाबेस क्रेडेंशियल्स सेट किए हैं।
2.  `pg` लाइब्रेरी (PostgreSQL client for Node.js) और इसके TypeScript types (`@types/pg`) इंस्टॉल किए हुए हैं।
3.  आपके सिस्टम पर PostgreSQL सर्वर चल रहा है और आवश्यक डेटाबेस और यूजर मौजूद हैं।

---

सबसे पहले, ज़रूरी dependencies इंस्टॉल करें:
```bash
npm install express pg dotenv
npm install -D @types/express @types/node @types/pg typescript ts-node nodemon
```

इसके बाद, ये फ़ाइलें बनाएँ:

### `1. .env` (Environment variables)
अपनी डेटाबेस क्रेडेंशियल्स यहाँ सेट करें।

```env
# .env
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_database_name
```
**(Replace `your_db_user`, `your_db_password`, `your_database_name` with your actual PostgreSQL credentials.)**

### `2. tsconfig.json` (TypeScript configuration)
```json
{
  "compilerOptions": {
    "target": "es2020",
    "module": "commonjs",
    "rootDir": "./src",
    "outDir": "./dist",
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### `3. package.json` (Scripts)
```json
{
  "name": "express-ts-pg-backend",
  "version": "1.0.0",
  "description": "Node.js Express TypeScript backend with PostgreSQL",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "nodemon --exec ts-node src/index.ts"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "dependencies": {
    "dotenv": "^16.4.5",
    "express": "^4.18.2",
    "pg": "^8.11.3"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/node": "^20.11.20",
    "@types/pg": "^8.11.2",
    "nodemon": "^3.1.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

### `4. src/config/db.ts` (Database Connection)
यह फ़ाइल PostgreSQL कनेक्शन पूल को कॉन्फ़िगर और एक्सपोर्ट करती है।

```typescript
// src/config/db.ts
import { Pool } from 'pg';
import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

// PostgreSQL Connection Pool configuration
const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || '5432', 10), // Default PostgreSQL port 5432
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  // Optional: Connection pool settings
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
  connectionTimeoutMillis: 2000, // Return an error after 2 seconds if connection could not be established
});

// Function to test the database connection
const connectDB = async () => {
  try {
    // Attempt to connect and execute a simple query
    await pool.query('SELECT NOW()');
    console.log('✅ PostgreSQL DB connected successfully!');
  } catch (err) {
    console.error('❌ PostgreSQL DB connection error:', err);
    // Exit process with failure code if connection fails
    process.exit(1);
  }
};

export { pool, connectDB };
```

### `5. src/index.ts` (Express Application)
यह मुख्य एक्सप्रेस एप्लीकेशन फ़ाइल है जो डेटाबेस कनेक्शन का उपयोग करती है।

```typescript
// src/index.ts
import express from 'express';
import { connectDB, pool } from './config/db'; // Import DB connection logic

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware to parse JSON bodies
app.use(express.json());

// Connect to the database when the application starts
connectDB();

// Basic API route to test DB interaction
app.get('/', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW() AS current_time');
    res.json({
      message: 'Hello from Express with PostgreSQL!',
      currentTime: result.rows[0].current_time,
    });
  } catch (err) {
    console.error('Error executing query:', err);
    res.status(500).send('Server error accessing database.');
  }
});

// Start the Express server
app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
});
```

---

**कैसे चलायें:**
1.  ऊपर दिए गए निर्देशों के अनुसार `package.json`, `tsconfig.json`, `.env`, `src/config/db.ts`, और `src/index.ts` फ़ाइलें बनाएँ।
2.  `npm install` चलाकर सभी dependencies इंस्टॉल करें।
3.  डेवलपमेंट मोड में सर्वर शुरू करने के लिए: `npm run dev`
4.  प्रॉडक्शन बिल्ड बनाने के लिए: `npm run build` फिर `npm start`

आपका Node.js Express TypeScript बैकएंड PostgreSQL डेटाबेस से कनेक्ट होने के लिए तैयार है।

## 🔍 Code Review

- **[Low]** Inconsistent TypeScript 'target' compiler option → _The first setup guide uses `"target": "es2016"` in `tsconfig.json`, while the second (PostgreSQL) setup uses `"target": "es2020"`. It's best to be consistent throughout the project. `es2020` or a newer target is generally preferred for modern Node.js applications to leverage more recent JavaScript features and reduce transpilation overhead._
- **[Low]** Inconsistent main entry point file name → _The first setup guide designates `server.ts` (compiled to `dist/server.js`) as the main entry point, while the second (PostgreSQL) uses `index.ts` (compiled to `dist/index.js`). While both are functionally correct, choose one naming convention (`server.ts`/`index.ts`) and apply it consistently across `package.json` scripts and file paths for clarity._
- **[Low]** Basic test script placeholder → _The `test` script in `package.json` is a placeholder. For a robust application, implement actual unit and integration tests using frameworks like Jest or Mocha. Replace `echo "Error: no test specified" && exit 1` with commands to run your test suite._
- **[Medium]** Missing global error handling middleware → _The application lacks a global error handling middleware. Malformed JSON requests or other unexpected errors in routes/middleware could lead to unhandled exceptions. Implement a centralized error handling middleware (`app.use((err, req, res, next) => { ... })`) to catch errors gracefully and send standardized error responses._
- **[Medium]** No input validation in API routes → _While the current API has a single simple GET endpoint, real-world applications often require input validation (e.g., for POST/PUT requests, query parameters, or route params). Consider integrating a validation library like `joi` or `express-validator` to ensure data integrity and prevent common security vulnerabilities like injection attacks._
- **[Low]** Basic logging implementation → _The current setup uses `console.log` and `console.error` for logging. For production environments, consider using a more robust logging library (e.g., Winston, Pino) that offers features like log levels, different transports (file, external service), and structured logging for easier monitoring and debugging._
- **[Medium]** Potential for sensitive data exposure in production (DB password in .env) → _While `.env` is suitable for development, storing sensitive credentials like `DB_PASSWORD` directly in `.env` files is not ideal for production. For production deployments, leverage secrets management services (e.g., AWS Secrets Manager, Vault, Kubernetes Secrets) or environment variable injection from the deployment platform, rather than relying on `.env` files._

**Overall:** The provided setup offers a solid foundation for an Express.js and TypeScript backend with PostgreSQL integration. It demonstrates good practices for dependency management, TypeScript configuration, and modular routing. Key areas for improvement focus on enhancing error handling, input validation, and production-grade security for sensitive information.

## 🧪 Test Cases

- **User Signup - Valid Credentials** → Expected: User should be successfully registered and redirected to the Login page or directly to the To-Do list dashboard. A success message should be displayed.
- **User Signup - Missing Username** → Expected: An error message 'Username is required' or similar should be displayed. User should not be registered.
- **User Signup - Missing Password** → Expected: An error message 'Password is required' or similar should be displayed. User should not be registered.
- **User Signup - Password Mismatch** → Expected: An error message 'Passwords do not match' or similar should be displayed. User should not be registered.
- **User Signup - Existing Username** → Expected: An error message 'Username already exists' or similar should be displayed. User should not be registered.
- **User Login - Valid Credentials** → Expected: User should be successfully logged in and redirected to their To-Do list page. The task list should be visible.
- **User Login - Invalid Username** → Expected: An error message 'Invalid username or password' or similar should be displayed. User should not be logged in.
- **User Login - Invalid Password** → Expected: An error message 'Invalid username or password' or similar should be displayed. User should not be logged in.
- **User Login - Empty Username** → Expected: An error message 'Username is required' or similar should be displayed. User should not be logged in.
- **User Login - Empty Password** → Expected: An error message 'Password is required' or similar should be displayed. User should not be logged in.
- **Add Task - Valid Task Name** → Expected: The task 'Buy groceries' should appear in the To-Do list. It should be initially marked as incomplete.
- **Add Task - Empty Task Name** → Expected: An error message 'Task name cannot be empty' or similar should be displayed. No new task should be added to the list.
- **Add Task - Long Task Name (Boundary Test)** → Expected: The task should be added successfully. The full task name should be displayed without truncation or breaking the UI layout. (Alternatively, if a character limit exists, an error message should be shown).
- **Add Task - Task with Special Characters** → Expected: The task should be added successfully and displayed correctly with all special characters preserved.
- **Mark Task - From Incomplete to Complete** → Expected: The 'Finish report' task should be visually updated to reflect completion (e.g., strikethrough, changed color, moved to a 'Completed' section). Its status should update internally.
- **Mark Task - From Complete to Incomplete (Toggle)** → Expected: The 'Send email' task should revert to an incomplete state (e.g., strikethrough removed, color reverted). Its status should update internally.
- **Delete Task - Existing Incomplete Task** → Expected: The 'Walk the dog' task should be immediately removed from the To-Do list. (If a confirmation dialog exists, it should appear and then the task should be deleted upon confirmation).
- **Delete Task - Existing Complete Task** → Expected: The completed 'Pay bills' task should be immediately removed from the To-Do list.
- **Delete Task - The Only Task in the List** → Expected: The task 'The only task' should be removed. The To-Do list should now display an empty state message (e.g., 'No tasks yet!').
- **Task Persistence - After Page Refresh** → Expected: The 'Persistent Task' should still be present in the list and remain marked as complete.
- **Task Persistence - After Logout and Re-login** → Expected: All previously added tasks ('Task A' and 'Task B') should be visible in the To-Do list, and 'Task A' should still be marked as complete.
- **Empty State Display for Task List** → Expected: The To-Do list area should display a user-friendly message indicating no tasks are present (e.g., 'You have no tasks! Add one above to get started.') instead of just a blank space.
- **Logout Functionality** → Expected: User should be successfully logged out and redirected to the Login or Signup page. Access to the To-Do list should be restricted without logging in again.
