import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        host: "localhost",
    },
    test: {
        environment: "jsdom",
        setupFiles: "./src/test/setup.ts",
        globals: true,
        env: {
            VITE_USE_MOCK_API: "true",
        },
    },
});
